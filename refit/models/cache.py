"""Content-addressed cache of validated model replies (enables deterministic replay)."""

from pathlib import Path

from refit.record.snapshots import write_text_atomic


class ResponseCache:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> str | None:
        path = self._path(key)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def put(self, key: str, text: str) -> None:
        write_text_atomic(self._path(key), text)
