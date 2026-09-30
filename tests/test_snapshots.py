import json

import pytest

from refit.record.snapshots import (
    SchemaVersionError,
    SnapshotNotFound,
    export_json_schema,
    latest_snapshot,
    load_snapshot,
    save_snapshot,
    snapshot_path,
)
from refit.record.walk import DuplicateClaimId, claim_index, iter_claims


def test_iter_claims_finds_every_claim(mk):
    ids = {c.id for c in iter_claims(mk.record())}
    assert {"part:R1:value", "part:U1:commercial_pn", "conn:R1.1", "conn:U1.6"} <= ids
    assert {"config:card_pn", "config:tm_changes", "config:confirmation"} <= ids


def test_claim_index_rejects_duplicate_ids(mk):
    rec = mk.record()
    rec.parts["R1-copy"] = mk.part("R1", value="22k")
    with pytest.raises(DuplicateClaimId):
        claim_index(rec)


def test_snapshot_round_trip_in_path_with_spaces(mk, tmp_path):
    card_dir = tmp_path / "My Projects" / "cards" / "demo card"
    path = save_snapshot(mk.record(), card_dir, "s03")
    assert path == card_dir / "card.s03.json"
    assert load_snapshot(card_dir, "s03") == mk.record()


def test_saving_one_stage_leaves_others_untouched(mk, tmp_path):
    save_snapshot(mk.record(), tmp_path, "s02")
    before = (tmp_path / "card.s02.json").read_text(encoding="utf-8")
    changed = mk.record()
    changed.title = "changed"
    save_snapshot(changed, tmp_path, "s03")
    assert (tmp_path / "card.s02.json").read_text(encoding="utf-8") == before
    assert not list(tmp_path.glob("*.tmp"))


def test_latest_snapshot_picks_highest_stage(mk, tmp_path):
    assert latest_snapshot(tmp_path) is None
    save_snapshot(mk.record(), tmp_path, "s00")
    later = mk.record()
    later.title = "later"
    save_snapshot(later, tmp_path, "s02")
    stage, rec = latest_snapshot(tmp_path)
    assert stage == "s02" and rec.title == "later"


def test_missing_snapshot_and_bad_stage(tmp_path):
    with pytest.raises(SnapshotNotFound):
        load_snapshot(tmp_path, "s05")
    with pytest.raises(ValueError):
        snapshot_path(tmp_path, "s10")


def test_schema_version_mismatch_is_refused(mk, tmp_path):
    path = save_snapshot(mk.record(), tmp_path, "s00")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = "999"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SchemaVersionError):
        load_snapshot(tmp_path, "s00")


def test_export_json_schema(tmp_path):
    out = export_json_schema(tmp_path / "schema" / "card-record.schema.json")
    schema = json.loads(out.read_text(encoding="utf-8"))
    assert schema["title"] == "CardRecord"
    assert "connections" in schema["properties"]
