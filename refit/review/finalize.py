"""The one way a stage saves its result: checks, policy, overrides, review queue, snapshot."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from refit.checks.base import Check, run_checks
from refit.record.model import CardRecord
from refit.record.overrides import apply_overrides, load_overrides
from refit.record.snapshots import save_snapshot
from refit.review.policy import Thresholds, apply_policy
from refit.review.queue import sync_review_items


@dataclass
class StageOutcome:
    record: CardRecord
    orphans: list[str]
    snapshot: Path


def finalize_stage(
    raw: CardRecord,
    card_dir: Path,
    stage: str,
    checks: Sequence[Check],
    thresholds: Thresholds | None = None,
) -> StageOutcome:
    thresholds = thresholds or Thresholds()
    overrides = load_overrides(card_dir)
    machine = apply_policy(raw, run_checks(raw, checks), thresholds)
    applied = apply_overrides(machine, overrides)
    working = apply_policy(applied.record, run_checks(applied.record, checks), thresholds)
    final = sync_review_items(working, overrides)
    snapshot = save_snapshot(final, card_dir, stage)
    return StageOutcome(record=final, orphans=applied.orphans, snapshot=snapshot)
