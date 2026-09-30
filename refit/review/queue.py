"""Review queue: flagged claims become items; resolutions are written as overrides."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from refit.record.claims import ClaimStatus
from refit.record.config_gate import CONFIRMATION_ID, REQUIRED_CONFIG_IDS
from refit.record.model import CardRecord, Resolution, ReviewItem
from refit.record.overrides import Override, OverrideSet, add_override
from refit.record.walk import iter_claims


class ReviewError(ValueError):
    pass


def review_item_id(claim_id: str) -> str:
    return f"rv:{claim_id}"


def sync_review_items(record: CardRecord, overrides: OverrideSet) -> CardRecord:
    rec = record.model_copy(deep=True)
    items: dict[str, ReviewItem] = {}
    for claim in iter_claims(rec):
        item_id = review_item_id(claim.id)
        dumped = claim.model_dump(mode="json")
        if claim.status is ClaimStatus.FLAGGED:
            items[item_id] = ReviewItem(
                id=item_id,
                claim_id=claim.id,
                reason=", ".join(claim.flags),
                proposed=dumped["value"],
            )
        elif claim.status is ClaimStatus.OVERRIDDEN and claim.id in overrides.overrides:
            override = overrides.overrides[claim.id]
            items[item_id] = ReviewItem(
                id=item_id,
                claim_id=claim.id,
                reason=", ".join(claim.flags) or "manual correction",
                proposed=dumped["machine_value"],
                resolution=Resolution(
                    value=override.value, by=override.by, at=override.at, note=override.note
                ),
            )
    rec.review_items = dict(sorted(items.items()))
    return rec


def open_items(record: CardRecord) -> list[ReviewItem]:
    return [item for item in record.review_items.values() if item.resolution is None]


def resolve_item(
    card_dir: Path,
    record: CardRecord,
    item_id: str,
    value: Any,
    by: str,
    note: str = "",
    now: datetime | None = None,
) -> Override:
    item = record.review_items.get(item_id)
    if item is None:
        raise ReviewError(f"no review item {item_id!r}")
    if item.claim_id == CONFIRMATION_ID:
        raise ReviewError("the configuration baseline is confirmed with `refit confirm-config`, not accept/resolve")
    if value in (None, "") and item.claim_id in REQUIRED_CONFIG_IDS:
        raise ReviewError(f"{item.claim_id} is a required configuration field and cannot be empty")
    override = Override(
        claim_id=item.claim_id,
        value=value,
        by=by,
        at=now or datetime.now(timezone.utc),
        note=note,
    )
    add_override(card_dir, override)
    return override


def accept_item(
    card_dir: Path, record: CardRecord, item_id: str, by: str, now: datetime | None = None
) -> Override:
    item = record.review_items.get(item_id)
    if item is None:
        raise ReviewError(f"no review item {item_id!r}")
    return resolve_item(card_dir, record, item_id, item.proposed, by, "accepted as proposed", now)
