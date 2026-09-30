"""Configuration gate: a redesign of the wrong revision is worse than none."""

from datetime import datetime, timezone
from pathlib import Path

from refit.checks.base import CheckFailure
from refit.record.claims import ClaimStatus
from refit.record.model import CardRecord
from refit.record.overrides import Override, add_override
from refit.record.walk import iter_claims

REQUIRED_CONFIG_FIELDS = (
    "card_pn", "card_revision", "tm_number", "host_system", "distribution_statement",
)
REQUIRED_CONFIG_IDS = frozenset(f"config:{field}" for field in REQUIRED_CONFIG_FIELDS)
CONFIRMATION_ID = "config:confirmation"
_AWAITING = "config_consistency.awaiting_confirmation"


class ConfigurationNotConfirmed(RuntimeError):
    pass


def _norm(value: str | None) -> str:
    return "".join((value or "").split()).upper()


class ConfigConsistencyCheck:
    name = "config_consistency"

    def run(self, record: CardRecord) -> list[CheckFailure]:
        cfg = record.config
        if cfg is None:
            return []
        failures: list[CheckFailure] = []
        for field in REQUIRED_CONFIG_FIELDS:
            claim = getattr(cfg, field)
            if not claim.value:
                failures.append(
                    CheckFailure(f"{self.name}.missing", (claim.id,), f"{field} is missing")
                )
        revision = _norm(cfg.card_revision.value)
        for observed in cfg.observed_revisions:
            if revision and _norm(observed.value) != revision:
                failures.append(
                    CheckFailure(
                        f"{self.name}.revision_mismatch",
                        (observed.id,),
                        f"source shows revision {observed.value!r}; baseline says "
                        f"{cfg.card_revision.value!r}",
                    )
                )
        if not cfg.confirmation.value:
            failures.append(
                CheckFailure(
                    f"{self.name}.awaiting_confirmation",
                    (cfg.confirmation.id,),
                    "a human must confirm the configuration baseline",
                )
            )
        return failures


def _flagged_config_ids(record: CardRecord) -> list[str]:
    return sorted(c.id for c in iter_claims(record.config) if c.status is ClaimStatus.FLAGGED)


def _failing_config_ids(record: CardRecord) -> list[str]:
    """Re-run the consistency check on current values, whatever the claim status,
    so a human override (e.g. accepting a null) can never satisfy the gate."""
    failures = ConfigConsistencyCheck().run(record)
    return sorted({cid for f in failures if f.check != _AWAITING for cid in f.claim_ids})


def confirm_configuration(
    card_dir: Path, record: CardRecord, by: str, now: datetime | None = None
) -> Override:
    if record.config is None:
        raise ConfigurationNotConfirmed("record has no configuration baseline; run intake first")
    flagged = [c for c in _flagged_config_ids(record) if c != record.config.confirmation.id]
    blocking = sorted(set(flagged) | set(_failing_config_ids(record)))
    if blocking:
        raise ConfigurationNotConfirmed(
            "resolve these configuration items first: " + ", ".join(blocking)
        )
    override = Override(
        claim_id=record.config.confirmation.id,
        value=by,
        by=by,
        at=now or datetime.now(timezone.utc),
        note="configuration baseline confirmed",
    )
    add_override(card_dir, override)
    return override


def require_confirmed(record: CardRecord) -> None:
    cfg = record.config
    if cfg is None:
        raise ConfigurationNotConfirmed("record has no configuration baseline")
    confirmation = cfg.confirmation
    if confirmation.status is not ClaimStatus.OVERRIDDEN or not confirmation.value:
        raise ConfigurationNotConfirmed("configuration baseline has not been confirmed by a human")
    flagged = sorted(set(_flagged_config_ids(record)) | set(_failing_config_ids(record)))
    if flagged:
        raise ConfigurationNotConfirmed("open configuration issues: " + ", ".join(flagged))
