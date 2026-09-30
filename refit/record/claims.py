"""Claims: every fact in a Card Record carries value, confidence, evidence and provenance."""

from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ClaimStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    FLAGGED = "flagged"
    OVERRIDDEN = "overridden"


class Evidence(BaseModel):
    source_id: str
    method: str
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    excerpt: str | None = None


class ProducedBy(BaseModel):
    kind: Literal["model", "rule", "human", "deterministic"]
    stage: str
    detail: str = ""


class Claim(BaseModel, Generic[T]):
    """One fact.

    `machine_status` / `machine_value` freeze the first automated verdict, so metrics
    can score the machine even after a human overrides the value.
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str
    value: T
    confidence: float = Field(ge=0.0, le=1.0)
    produced_by: ProducedBy
    evidence: list[Evidence] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.PROPOSED
    flags: list[str] = Field(default_factory=list)
    machine_status: ClaimStatus | None = None
    machine_value: Any = None

    @property
    def category(self) -> str:
        return self.id.split(":", 1)[0]


StrClaim = Claim[str]
OptStrClaim = Claim[str | None]
StrListClaim = Claim[list[str]]
