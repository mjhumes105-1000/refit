import pytest
from pydantic import ValidationError

from refit.record.claims import Claim, ClaimStatus, Evidence, OptStrClaim, ProducedBy


def by_model() -> ProducedBy:
    return ProducedBy(kind="model", stage="s02", detail="test-model:v1")


def test_category_is_id_prefix():
    c = OptStrClaim(id="part:R12:value", value="10k", confidence=0.95, produced_by=by_model())
    assert c.category == "part"
    assert c.status is ClaimStatus.PROPOSED
    assert c.machine_status is None


def test_confidence_must_be_between_0_and_1():
    with pytest.raises(ValidationError):
        OptStrClaim(id="part:R1:value", value="1k", confidence=1.5, produced_by=by_model())


def test_assignment_is_validated_against_value_type():
    c = Claim[int](id="x:1", value=3, confidence=1.0, produced_by=by_model())
    with pytest.raises(ValidationError):
        c.value = "not a number"


def test_json_round_trip_keeps_evidence():
    c = OptStrClaim(
        id="part:C3:value",
        value=None,
        confidence=0.5,
        produced_by=by_model(),
        evidence=[Evidence(source_id="manual", method="model_read", page=4, bbox=(1, 2, 3, 4))],
    )
    assert OptStrClaim.model_validate_json(c.model_dump_json()) == c
