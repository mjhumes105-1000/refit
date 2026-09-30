from datetime import datetime, timezone

import pytest

from refit.record.overrides import Override, add_override
from refit.review.finalize import finalize_stage
from refit.review.metrics import Reference, compute_metrics, load_reference
from refit.review.policy import Thresholds, apply_policy

T0 = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def accepted(record):
    return apply_policy(record, [], Thresholds())


def test_perfect_connections_with_mixed_pin_formats(mk):
    ref = Reference(nets=[["R1-1", "u1.2"], ["R1 pin 2", "U1:6"]])
    m = compute_metrics(accepted(mk.record()), ref)["conn"]
    assert (m.reference_facts, m.auto_accepted, m.auto_correct, m.auto_wrong) == (4, 4, 4, 0)
    assert (m.automation_rate, m.false_accept_rate) == (1.0, 0.0)


def test_wrong_net_membership_is_a_false_accept(mk):
    ref = Reference(nets=[["R1.1", "U1.2"], ["R1.2"], ["U1.6"]])
    m = compute_metrics(accepted(mk.record()), ref)["conn"]
    assert (m.auto_correct, m.auto_wrong) == (2, 2)
    assert (m.automation_rate, m.false_accept_rate) == (0.5, 0.5)


def test_flagged_claims_do_not_count_as_automated(mk):
    raw = mk.record()
    raw.connections["U1.2"] = mk.conn("U1.2", "_n1", confidence=0.5)
    ref = Reference(nets=[["R1.1", "U1.2"], ["R1.2", "U1.6"]])
    m = compute_metrics(accepted(raw), ref)["conn"]
    assert (m.auto_accepted, m.auto_correct) == (3, 3)
    assert m.automation_rate == 0.75


def test_later_human_correction_still_counts_machine_answer(mk, tmp_path):
    add_override(tmp_path, Override(claim_id="part:R1:value", value="4.7k", by="mh", at=T0))
    rec = finalize_stage(mk.record(), tmp_path, "s02", []).record
    m = compute_metrics(rec, Reference(values={"part:R1:value": "4.7k"}))["part"]
    assert (m.reference_facts, m.auto_correct, m.auto_wrong) == (1, 0, 1)
    assert m.false_accept_rate == 1.0


def test_values_normalized_and_unscored_counted(mk):
    m = compute_metrics(accepted(mk.record()), Reference(values={"part:R1:value": " 10K "}))["part"]
    assert (m.auto_correct, m.auto_wrong, m.unscored) == (1, 0, 1)


def test_empty_reference_reports_none_not_zero_division(mk):
    metrics = compute_metrics(accepted(mk.record()), Reference())
    assert metrics["block"].automation_rate is None
    assert metrics["block"].false_accept_rate is None
    assert metrics["conn"].unscored == 4
    assert metrics["conn"].false_accept_rate is None
    assert list(metrics) == ["part", "conn", "block", "substitution"]


def test_pin_listed_in_two_reference_nets_is_rejected(mk):
    with pytest.raises(ValueError):
        compute_metrics(accepted(mk.record()), Reference(nets=[["R1.1"], ["r1-1"]]))


def test_load_reference(tmp_path):
    path = tmp_path / "reference.json"
    path.write_text('{"values": {"part:R1:value": "10k"}, "nets": [["R1.1", "U1.2"]]}', encoding="utf-8")
    ref = load_reference(path)
    assert ref.nets == [["R1.1", "U1.2"]]
