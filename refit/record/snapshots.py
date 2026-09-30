"""Per-stage snapshots: each stage writes cards/<id>/card.sNN.json and never edits earlier ones."""

import json
import os
from pathlib import Path

from refit import SCHEMA_VERSION
from refit.record.model import CardRecord

STAGE_IDS = tuple(f"s{i:02d}" for i in range(10))


class SnapshotNotFound(FileNotFoundError):
    pass


class SchemaVersionError(ValueError):
    pass


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def snapshot_path(card_dir: Path, stage: str) -> Path:
    if stage not in STAGE_IDS:
        raise ValueError(f"unknown stage {stage!r}; expected one of {STAGE_IDS}")
    return card_dir / f"card.{stage}.json"


def save_snapshot(record: CardRecord, card_dir: Path, stage: str) -> Path:
    path = snapshot_path(card_dir, stage)
    write_text_atomic(path, record.model_dump_json(indent=2))
    return path


def load_snapshot(card_dir: Path, stage: str) -> CardRecord:
    path = snapshot_path(card_dir, stage)
    if not path.exists():
        raise SnapshotNotFound(f"no snapshot for {stage} at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise SchemaVersionError(
            f"{path} has schema_version {version!r}; this REFIT reads {SCHEMA_VERSION!r}"
        )
    return CardRecord.model_validate(data)


def latest_snapshot(card_dir: Path) -> tuple[str, CardRecord] | None:
    for stage in reversed(STAGE_IDS):
        if snapshot_path(card_dir, stage).exists():
            return stage, load_snapshot(card_dir, stage)
    return None


def export_json_schema(path: Path) -> Path:
    write_text_atomic(path, json.dumps(CardRecord.model_json_schema(), indent=2))
    return path
