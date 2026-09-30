"""Which rule checks run after each stage. Later milestones add their stages here."""

from refit.checks.base import Check
from refit.record.config_gate import ConfigConsistencyCheck

STAGE_CHECKS: dict[str, list[Check]] = {
    "s00": [ConfigConsistencyCheck()],
}
