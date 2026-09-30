from datetime import datetime, timezone

import pytest

from refit.record.claims import ClaimStatus
from refit.record.overrides import Override, add_override
from refit.review.finalize import finalize_stage
from refit.review.queue import ReviewError, accept_item, open_items, resolve_item

T0 = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def low_conf_record(mk):
    raw = mk.record()
    raw.connections["U1.2"] = mk.conn("U1.2", "_n1", confidence=0.5)
    return raw


def test_flagged_claims_become_open_review_items(mk, tmp_path):
    out = finalize_stage(low_conf_record(mk), tmp_path, "s03", [])
    items = open_items(out.record)
    assert [i.id for i in items] == ["rv:conn:U1.2"]
    assert items[0].reason == "low_confidence"
    assert items[0].proposed == "_n1"
    assert out.snapshot == tmp_path / "card.s03.json"


def test_resolving_writes_override_and_refinalizing_closes_item(mk, tmp_path):
    out = finalize_stage(low_conf_record(mk), tmp_path, "s03", [])
    resolve_item(tmp_path, out.record, "rv:conn:U1.2", "OUT", by="mh", now=T0)
    again = finalize_stage(out.record, tmp_path, "s03", [])
    claim = again.record.connections["U1.2"]
    assert (claim.status, claim.value) == (ClaimStatus.OVERRIDDEN, "OUT")
    assert (claim.machine_status, claim.machine_value) == (ClaimStatus.FLAGGED, "_n1")
    assert open_items(again.record) == []
    item = again.record.review_items["rv:conn:U1.2"]
    assert item.resolution.by == "mh" and item.resolution.at == T0
    assert item.proposed == "_n1"


def test_accept_item_keeps_proposed_value(mk, tmp_path):
    out = finalize_stage(low_conf_record(mk), tmp_path, "s03", [])
    accept_item(tmp_path, out.record, "rv:conn:U1.2", by="mh", now=T0)
    again = finalize_stage(out.record, tmp_path, "s03", [])
    assert again.record.connections["U1.2"].value == "_n1"
    assert again.record.connections["U1.2"].status is ClaimStatus.OVERRIDDEN


def test_correcting_an_auto_accepted_claim_is_recorded(mk, tmp_path):
    add_override(tmp_path, Override(claim_id="part:R1:value", value="4.7k", by="mh", at=T0))
    out = finalize_stage(mk.record(), tmp_path, "s02", [])
    claim = out.record.parts["R1"].attrs["value"]
    assert (claim.machine_status, claim.machine_value, claim.value) == (
        ClaimStatus.ACCEPTED, "10k", "4.7k",
    )
    item = out.record.review_items["rv:part:R1:value"]
    assert item.reason == "manual correction" and item.resolution.value == "4.7k"


def test_rerun_reapplies_corrections_and_reports_orphans(mk, tmp_path):
    out = finalize_stage(low_conf_record(mk), tmp_path, "s03", [])
    resolve_item(tmp_path, out.record, "rv:conn:U1.2", "OUT", by="mh", now=T0)
    add_override(tmp_path, Override(claim_id="part:R99:value", value="1k", by="mh", at=T0))
    rerun = finalize_stage(low_conf_record(mk), tmp_path, "s03", [])  # fresh machine output
    assert rerun.record.connections["U1.2"].value == "OUT"
    assert rerun.orphans == ["part:R99:value"]


def test_resolve_unknown_item_raises(mk, tmp_path):
    out = finalize_stage(mk.record(), tmp_path, "s03", [])
    with pytest.raises(ReviewError):
        resolve_item(tmp_path, out.record, "rv:conn:NOPE.1", "x", by="mh")
