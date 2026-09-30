import pytest

from refit.checks.base import CheckFailure, run_checks
from refit.record.claims import ClaimStatus, Evidence
from refit.review.policy import Thresholds, apply_policy


class FailClaim:
    name = "fail_claim"

    def __init__(self, claim_id):
        self.claim_id = claim_id

    def run(self, record):
        return [CheckFailure(self.name, (self.claim_id,), "forced failure")]


def test_confident_claim_with_no_failures_is_accepted(mk):
    rec = apply_policy(mk.record(), [], Thresholds())
    claim = rec.connections["R1.1"]
    assert claim.status is ClaimStatus.ACCEPTED
    assert claim.machine_status is ClaimStatus.ACCEPTED
    assert claim.machine_value == "_n1"
    assert claim.flags == []


def test_failed_check_flags_even_a_confident_claim(mk):
    raw = mk.record()
    rec = apply_policy(raw, run_checks(raw, [FailClaim("conn:R1.1")]), Thresholds())
    claim = rec.connections["R1.1"]
    assert claim.confidence == 0.95
    assert claim.status is ClaimStatus.FLAGGED
    assert claim.flags == ["fail_claim"]


def test_low_confidence_is_flagged(mk):
    raw = mk.record()
    raw.connections["U1.2"] = mk.conn("U1.2", "_n1", confidence=0.5)
    rec = apply_policy(raw, [], Thresholds())
    assert rec.connections["U1.2"].flags == ["low_confidence"]


def test_connection_needs_cv_and_model_agreement(mk):
    raw = mk.record()
    raw.connections["U1.2"] = mk.conn(
        "U1.2", "_n1", evidence=[Evidence(source_id="manual", method="model_read")]
    )
    rec = apply_policy(raw, [], Thresholds())
    assert rec.connections["U1.2"].flags == ["no_independent_agreement"]


def test_per_category_threshold(mk):
    rec = apply_policy(mk.record(), [], Thresholds(per_category={"part": 0.99}))
    assert rec.parts["R1"].attrs["value"].status is ClaimStatus.FLAGGED
    assert rec.connections["R1.1"].status is ClaimStatus.ACCEPTED


def test_human_claims_are_left_alone(mk):
    rec = apply_policy(mk.record(), [], Thresholds())
    assert rec.config.card_pn.status is ClaimStatus.ACCEPTED
    assert rec.config.card_pn.machine_status is None


def test_machine_verdict_is_recorded_only_once(mk):
    raw = mk.record()
    first = apply_policy(raw, run_checks(raw, [FailClaim("conn:R1.1")]), Thresholds())
    second = apply_policy(first, [], Thresholds())
    claim = second.connections["R1.1"]
    assert claim.status is ClaimStatus.ACCEPTED
    assert claim.machine_status is ClaimStatus.FLAGGED


def test_failure_for_unknown_claim_raises(mk):
    with pytest.raises(ValueError):
        apply_policy(mk.record(), [CheckFailure("x", ("conn:NOPE.1",), "")], Thresholds())
