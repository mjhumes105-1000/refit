"""Acceptance policy: AI proposes, rules check, and only clean confident claims are auto-accepted."""

from collections import defaultdict

from pydantic import BaseModel, Field

from refit.checks.base import CheckFailure
from refit.record.claims import ClaimStatus
from refit.record.model import CardRecord
from refit.record.walk import claim_index

REQUIRED_CONN_METHODS = frozenset({"cv_trace", "model_read"})


class Thresholds(BaseModel):
    default: float = 0.9
    per_category: dict[str, float] = Field(default_factory=dict)

    def for_category(self, category: str) -> float:
        return self.per_category.get(category, self.default)


def apply_policy(
    record: CardRecord, failures: list[CheckFailure], thresholds: Thresholds
) -> CardRecord:
    rec = record.model_copy(deep=True)
    index = claim_index(rec)
    failed: dict[str, set[str]] = defaultdict(set)
    for failure in failures:
        for claim_id in failure.claim_ids:
            if claim_id not in index:
                raise ValueError(f"check {failure.check!r} names unknown claim {claim_id!r}")
            failed[claim_id].add(failure.check)

    for claim in index.values():
        if claim.status is ClaimStatus.OVERRIDDEN or claim.produced_by.kind == "human":
            continue
        flags = sorted(failed.get(claim.id, set()))
        if claim.category == "conn":
            methods = {e.method for e in claim.evidence}
            if not REQUIRED_CONN_METHODS <= methods:
                flags.append("no_independent_agreement")
        if claim.confidence < thresholds.for_category(claim.category):
            flags.append("low_confidence")
        claim.flags = flags
        claim.status = ClaimStatus.FLAGGED if flags else ClaimStatus.ACCEPTED
        if claim.machine_status is None:
            claim.machine_status = claim.status
            claim.machine_value = claim.value
    return rec
