import json
from datetime import datetime, timezone

import pytest

from refit.record.claims import ClaimStatus
from refit.record.overrides import (
    Override,
    OverrideSet,
    OverrideValueError,
    add_override,
    apply_overrides,
    load_overrides,
)

T0 = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def ov(claim_id, value, by="mh"):
    return Override(claim_id=claim_id, value=value, by=by, at=T0)


def test_override_replaces_value_and_marks_human(mk):
    result = apply_overrides(mk.record(), OverrideSet(overrides={"part:R1:value": ov("part:R1:value", "4.7k")}))
    claim = result.record.parts["R1"].attrs["value"]
    assert claim.value == "4.7k"
    assert claim.status is ClaimStatus.OVERRIDDEN
    assert claim.confidence == 1.0
    assert claim.produced_by.kind == "human" and claim.produced_by.detail == "mh"
    assert result.orphans == []


def test_override_keeps_machine_verdict_and_is_idempotent(mk):
    rec = mk.record()
    claim = rec.parts["R1"].attrs["value"]
    claim.machine_status = ClaimStatus.ACCEPTED
    claim.machine_value = "10k"
    claim.flags = ["low_confidence"]
    overrides = OverrideSet(overrides={"part:R1:value": ov("part:R1:value", "4.7k")})
    once = apply_overrides(rec, overrides).record
    twice = apply_overrides(once, overrides).record
    for r in (once, twice):
        c = r.parts["R1"].attrs["value"]
        assert (c.value, c.machine_status, c.machine_value, c.flags) == (
            "4.7k", ClaimStatus.ACCEPTED, "10k", ["low_confidence"],
        )
    assert rec.parts["R1"].attrs["value"].value == "10k"  # input not mutated


def test_orphan_override_is_reported_not_dropped(mk):
    result = apply_overrides(mk.record(), OverrideSet(overrides={"part:R99:value": ov("part:R99:value", "1k")}))
    assert result.orphans == ["part:R99:value"]


def test_connection_override_creates_missing_pin_with_normalized_id(mk, tmp_path):
    add_override(tmp_path, ov("conn:u9-3", "OUT"))
    overrides = load_overrides(tmp_path)
    assert list(overrides.overrides) == ["conn:U9.3"]
    rec = apply_overrides(mk.record(), overrides).record
    added = rec.connections["U9.3"]
    assert added.value == "OUT"
    assert added.status is ClaimStatus.OVERRIDDEN
    assert added.machine_status is None


def test_wrong_value_type_raises(mk):
    with pytest.raises(OverrideValueError):
        apply_overrides(mk.record(), OverrideSet(overrides={"config:tm_changes": ov("config:tm_changes", 5)}))


def test_overrides_file_round_trip_latest_wins(tmp_path):
    assert load_overrides(tmp_path).overrides == {}
    add_override(tmp_path, ov("part:R1:value", "1k"))
    add_override(tmp_path, ov("part:R1:value", "2k", by="reviewer2"))
    loaded = load_overrides(tmp_path)
    assert loaded.overrides["part:R1:value"].value == "2k"
    assert loaded.overrides["part:R1:value"].by == "reviewer2"
    assert loaded.overrides["part:R1:value"].at == T0


def test_connection_override_is_orphan_when_no_stage_has_produced_connections(mk):
    # review finding 6: a snapshot must not gain connections before any stage produced them
    rec = mk.record()
    rec.connections = {}
    result = apply_overrides(rec, OverrideSet(overrides={"conn:U7.3": ov("conn:U7.3", "+5V")}))
    assert result.record.connections == {}
    assert result.orphans == ["conn:U7.3"]


def test_hand_edited_overrides_file_is_normalized_on_load(tmp_path):
    # review finding 7: overrides.json is human-edited; pin ids must normalize on load
    entry = ov("conn:u1-2", "OUT").model_dump(mode="json")
    (tmp_path / "overrides.json").write_text(
        json.dumps({"overrides": {"conn:u1-2": entry}}), encoding="utf-8"
    )
    loaded = load_overrides(tmp_path)
    assert list(loaded.overrides) == ["conn:U1.2"]
    assert loaded.overrides["conn:U1.2"].claim_id == "conn:U1.2"


def test_overrides_file_with_duplicate_pins_after_normalizing_is_rejected(tmp_path):
    a, b = ov("conn:u1-2", "OUT").model_dump(mode="json"), ov("conn:U1.2", "_n1").model_dump(mode="json")
    (tmp_path / "overrides.json").write_text(
        json.dumps({"overrides": {"conn:u1-2": a, "conn:U1.2": b}}), encoding="utf-8"
    )
    with pytest.raises(OverrideValueError, match="U1.2"):
        load_overrides(tmp_path)
