"""Human decisions live in overrides.json and are re-applied after every stage run."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from refit.record.claims import ClaimStatus, ProducedBy, StrClaim
from refit.record.model import CardRecord
from refit.record.pins import normalize_pin
from refit.record.snapshots import write_text_atomic
from refit.record.walk import claim_index

OVERRIDES_FILE = "overrides.json"


class OverrideValueError(ValueError):
    pass


class Override(BaseModel):
    claim_id: str
    value: Any
    by: str
    at: datetime
    note: str = ""


class OverrideSet(BaseModel):
    overrides: dict[str, Override] = Field(default_factory=dict)


@dataclass
class ApplyResult:
    record: CardRecord
    orphans: list[str]


def normalize_claim_id(claim_id: str) -> str:
    if claim_id.startswith("conn:"):
        return "conn:" + normalize_pin(claim_id.removeprefix("conn:"))
    return claim_id


def load_overrides(card_dir: Path) -> OverrideSet:
    path = card_dir / OVERRIDES_FILE
    if not path.exists():
        return OverrideSet()
    return OverrideSet.model_validate_json(path.read_text(encoding="utf-8"))


def save_overrides(card_dir: Path, overrides: OverrideSet) -> Path:
    path = card_dir / OVERRIDES_FILE
    write_text_atomic(path, overrides.model_dump_json(indent=2))
    return path


def add_override(card_dir: Path, override: Override) -> OverrideSet:
    override = override.model_copy(update={"claim_id": normalize_claim_id(override.claim_id)})
    current = load_overrides(card_dir)
    current.overrides[override.claim_id] = override
    save_overrides(card_dir, current)
    return current


def apply_overrides(record: CardRecord, overrides: OverrideSet) -> ApplyResult:
    rec = record.model_copy(deep=True)
    index = claim_index(rec)
    orphans: list[str] = []
    for override in overrides.overrides.values():
        human = ProducedBy(kind="human", stage="review", detail=override.by)
        claim = index.get(override.claim_id)
        try:
            if claim is None:
                if override.claim_id.startswith("conn:"):
                    pin = override.claim_id.removeprefix("conn:")
                    rec.connections[pin] = StrClaim(
                        id=override.claim_id,
                        value=override.value,
                        confidence=1.0,
                        produced_by=human,
                        status=ClaimStatus.OVERRIDDEN,
                    )
                else:
                    orphans.append(override.claim_id)
                continue
            claim.value = override.value
        except ValidationError as exc:
            raise OverrideValueError(
                f"override for {override.claim_id} has the wrong type: {exc}"
            ) from exc
        claim.status = ClaimStatus.OVERRIDDEN
        claim.confidence = 1.0
        claim.produced_by = human
    return ApplyResult(record=rec, orphans=sorted(orphans))
