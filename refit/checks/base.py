"""Rule checks: deterministic verification that runs after every stage."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from refit.record.model import CardRecord


@dataclass(frozen=True)
class CheckFailure:
    check: str
    claim_ids: tuple[str, ...]
    message: str


class Check(Protocol):
    name: str

    def run(self, record: CardRecord) -> list[CheckFailure]: ...


def run_checks(record: CardRecord, checks: Iterable[Check]) -> list[CheckFailure]:
    failures: list[CheckFailure] = []
    for check in checks:
        failures.extend(check.run(record))
    return failures
