"""Automation and false-accept metrics against a hand-built reference.

Only the first automated verdict (machine_status / machine_value) is scored, so a
false accept that a human later corrected still counts against the machine.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from refit.record.claims import ClaimStatus
from refit.record.model import CardRecord
from refit.record.pins import normalize_pin
from refit.record.walk import iter_claims

METRIC_CATEGORIES = ("part", "conn", "block", "substitution")


class Reference(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    nets: list[list[str]] = Field(default_factory=list)


class CategoryMetrics(BaseModel):
    category: str
    reference_facts: int
    auto_accepted: int
    auto_correct: int
    auto_wrong: int
    unscored: int
    automation_rate: float | None
    false_accept_rate: float | None


def load_reference(path: Path) -> Reference:
    return Reference.model_validate_json(path.read_text(encoding="utf-8"))


def _norm(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    if isinstance(value, list):
        return sorted(_norm(v) for v in value)
    return value


def _rates(
    category: str, reference_facts: int, correct: int, wrong: int, unscored: int
) -> CategoryMetrics:
    accepted = correct + wrong
    return CategoryMetrics(
        category=category,
        reference_facts=reference_facts,
        auto_accepted=accepted,
        auto_correct=correct,
        auto_wrong=wrong,
        unscored=unscored,
        automation_rate=correct / reference_facts if reference_facts else None,
        false_accept_rate=wrong / accepted if accepted else None,
    )


def _reference_nets(reference: Reference) -> dict[str, frozenset[str]]:
    net_of: dict[str, frozenset[str]] = {}
    for net in reference.nets:
        members = frozenset(normalize_pin(p) for p in net)
        for pin in members:
            if pin in net_of:
                raise ValueError(f"reference lists pin {pin} in more than one net")
            net_of[pin] = members
    return net_of


def _connection_metrics(record: CardRecord, reference: Reference) -> CategoryMetrics:
    machine = {
        normalize_pin(pin): claim
        for pin, claim in record.connections.items()
        if claim.machine_status is not None
    }
    accepted = [p for p, c in machine.items() if c.machine_status is ClaimStatus.ACCEPTED]
    if not reference.nets:
        return _rates("conn", 0, 0, 0, len(accepted))
    ref = _reference_nets(reference)
    groups: dict[Any, set[str]] = {}
    for pin, claim in machine.items():
        groups.setdefault(claim.machine_value, set()).add(pin)
    correct = wrong = 0
    for pin in accepted:
        if ref.get(pin) == frozenset(groups[machine[pin].machine_value]):
            correct += 1
        else:
            wrong += 1
    return _rates("conn", len(ref), correct, wrong, 0)


def _value_metrics(record: CardRecord, reference: Reference, category: str) -> CategoryMetrics:
    reference_facts = sum(1 for k in reference.values if k.split(":", 1)[0] == category)
    correct = wrong = unscored = 0
    for claim in iter_claims(record):
        if claim.category != category or claim.machine_status is not ClaimStatus.ACCEPTED:
            continue
        if claim.id not in reference.values:
            unscored += 1
        elif _norm(claim.machine_value) == _norm(reference.values[claim.id]):
            correct += 1
        else:
            wrong += 1
    return _rates(category, reference_facts, correct, wrong, unscored)


def compute_metrics(record: CardRecord, reference: Reference) -> dict[str, CategoryMetrics]:
    return {
        category: (
            _connection_metrics(record, reference)
            if category == "conn"
            else _value_metrics(record, reference, category)
        )
        for category in METRIC_CATEGORIES
    }
