"""REFIT command line."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from refit.models.adapter import ModelClient, ModelOutputError, ModelRefusal, ReplayMiss, default_client
from refit.record.config_gate import ConfigurationNotConfirmed, confirm_configuration
from refit.record.model import CardRecord
from refit.record.overrides import Override, OverrideValueError, add_override
from refit.record.snapshots import export_json_schema, latest_snapshot
from refit.review.finalize import StageOutcome, finalize_stage
from refit.review.metrics import compute_metrics, load_reference
from refit.review.queue import ReviewError, accept_item, open_items, resolve_item
from refit.stages.registry import STAGE_CHECKS
from refit.stages.s00_intake import DistributionGateError, run_intake

EXPECTED_ERRORS = (
    DistributionGateError,
    ConfigurationNotConfirmed,
    ReviewError,
    OverrideValueError,
    ReplayMiss,
    ModelOutputError,
    ModelRefusal,
    FileNotFoundError,
)


def make_client(cache_root: Path, replay: bool) -> ModelClient:
    return default_client(cache_root / "models", replay_only=replay)


def _paths(args: argparse.Namespace) -> tuple[Path, Path]:
    workspace = Path(args.workspace).resolve()
    return workspace / "cards" / args.card_id, workspace / "cache"


def _parse_value(text: str) -> Any:
    if text == "null" or text.startswith(("[", "{")):
        return json.loads(text)
    return text


def _latest(card_dir: Path) -> tuple[str, CardRecord]:
    found = latest_snapshot(card_dir)
    if found is None:
        raise ReviewError(f"no snapshots in {card_dir}; run `refit intake` first")
    return found


def _refinalize(card_dir: Path) -> StageOutcome:
    stage, record = _latest(card_dir)
    outcome = finalize_stage(record, card_dir, stage, STAGE_CHECKS.get(stage, []))
    for orphan in outcome.orphans:
        print(f"warning: override for {orphan} matches no claim", file=sys.stderr)
    return outcome


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cmd_intake(args: argparse.Namespace) -> int:
    card_dir, cache_root = _paths(args)
    outcome = run_intake(
        card_id=args.card_id,
        manual_uri=args.manual,
        host_system=args.host_system,
        card_dir=card_dir,
        cache_root=cache_root,
        client=make_client(cache_root, args.replay),
        card_pn=args.card_pn,
        card_revision=args.card_rev,
        photo_uris=args.photo or (),
    )
    record = outcome.record
    print(f"distribution: {record.distribution.statement}  (read via {record.distribution.method})")
    print(f"snapshot: {outcome.snapshot}")
    print(f"open review items: {len(open_items(record))}")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    card_dir, _ = _paths(args)
    _, record = _latest(card_dir)
    items = open_items(record)
    if not items:
        print("no open review items")
        return 0
    for item in items:
        print(item.id)
        print(f"    reason:   {item.reason}")
        print(f"    proposed: {json.dumps(item.proposed)}")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    card_dir, _ = _paths(args)
    _, record = _latest(card_dir)
    resolve_item(card_dir, record, args.item_id, _parse_value(args.value), args.by, args.note)
    _refinalize(card_dir)
    print(f"resolved {args.item_id}")
    return 0


def cmd_accept(args: argparse.Namespace) -> int:
    card_dir, _ = _paths(args)
    _, record = _latest(card_dir)
    accept_item(card_dir, record, args.item_id, args.by)
    _refinalize(card_dir)
    print(f"accepted {args.item_id}")
    return 0


def cmd_override(args: argparse.Namespace) -> int:
    card_dir, _ = _paths(args)
    _latest(card_dir)
    add_override(
        card_dir,
        Override(claim_id=args.claim_id, value=_parse_value(args.value), by=args.by, at=_now(), note=args.note),
    )
    _refinalize(card_dir)
    print(f"overrode {args.claim_id}")
    return 0


def cmd_confirm_config(args: argparse.Namespace) -> int:
    card_dir, _ = _paths(args)
    _, record = _latest(card_dir)
    confirm_configuration(card_dir, record, args.by)
    _refinalize(card_dir)
    print(f"configuration confirmed by {args.by}")
    return 0


def _fmt(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate:.0%}"


def cmd_metrics(args: argparse.Namespace) -> int:
    card_dir, _ = _paths(args)
    _, record = _latest(card_dir)
    metrics = compute_metrics(record, load_reference(Path(args.reference)))
    print(f"{'category':<14}{'ref':>5}{'accepted':>10}{'correct':>9}{'wrong':>7}{'unscored':>10}{'automation':>12}{'false-accept':>14}")
    for m in metrics.values():
        print(
            f"{m.category:<14}{m.reference_facts:>5}{m.auto_accepted:>10}{m.auto_correct:>9}"
            f"{m.auto_wrong:>7}{m.unscored:>10}{_fmt(m.automation_rate):>12}{_fmt(m.false_accept_rate):>14}"
        )
    return 0


def cmd_schema(args: argparse.Namespace) -> int:
    path = export_json_schema(Path(args.out))
    print(f"wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--workspace", default=".", help="folder holding cards/ and cache/")

    parser = argparse.ArgumentParser(prog="refit", description="REFIT legacy CCA modernization pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("intake", parents=[common], help="stage 0: fetch manual, Distribution A gate, baseline")
    p.add_argument("card_id")
    p.add_argument("--manual", required=True, help="URL or path of the technical manual PDF")
    p.add_argument("--host-system", required=True, help="end item model + modification level")
    p.add_argument("--card-pn")
    p.add_argument("--card-rev")
    p.add_argument("--photo", action="append", help="URL or path of a board photo (repeatable)")
    p.add_argument("--replay", action="store_true", help="use cached model replies only")
    p.set_defaults(func=cmd_intake)

    p = sub.add_parser("review", parents=[common], help="list open review items")
    p.add_argument("card_id")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("resolve", parents=[common], help="resolve a review item with a value")
    p.add_argument("card_id")
    p.add_argument("item_id")
    p.add_argument("--value", required=True)
    p.add_argument("--by", required=True)
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("accept", parents=[common], help="accept a review item's proposed value")
    p.add_argument("card_id")
    p.add_argument("item_id")
    p.add_argument("--by", required=True)
    p.set_defaults(func=cmd_accept)

    p = sub.add_parser("override", parents=[common], help="correct any claim, including auto-accepted ones")
    p.add_argument("card_id")
    p.add_argument("claim_id")
    p.add_argument("--value", required=True)
    p.add_argument("--by", required=True)
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_override)

    p = sub.add_parser("confirm-config", parents=[common], help="human confirmation of the configuration baseline")
    p.add_argument("card_id")
    p.add_argument("--by", required=True)
    p.set_defaults(func=cmd_confirm_config)

    p = sub.add_parser("metrics", parents=[common], help="automation and false-accept rates vs a reference")
    p.add_argument("card_id")
    p.add_argument("--reference", required=True)
    p.set_defaults(func=cmd_metrics)

    p = sub.add_parser("schema", help="export the Card Record JSON Schema")
    p.add_argument("out")
    p.set_defaults(func=cmd_schema)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except EXPECTED_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
