"""Card Record: the single structured record every REFIT stage reads and writes."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from refit import SCHEMA_VERSION
from refit.record.claims import Claim, Evidence, OptStrClaim, StrClaim, StrListClaim

PART_ATTRS = (
    "description", "mil_pn", "commercial_pn", "nsn", "cage",
    "value", "tolerance", "rating", "package", "domain",
)


class PinDef(BaseModel):
    number: str
    name: str = ""
    role: Literal[
        "input", "output", "bidirectional", "power", "ground", "passive", "nc", "unknown"
    ] = "unknown"


class Part(BaseModel):
    refdes: str
    attrs: dict[str, OptStrClaim] = Field(default_factory=dict)
    pins: list[PinDef] = Field(default_factory=list)

    def attr(self, name: str) -> str | None:
        claim = self.attrs.get(name)
        return None if claim is None else claim.value


class Block(BaseModel):
    id: str
    name: StrClaim
    function: StrClaim
    parts: StrListClaim
    domain: StrClaim  # analog | digital | mixed | power
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    theory_excerpt: str | None = None


class ExpectedReading(BaseModel):
    """A test-point spec from the TM troubleshooting tables (spec: TestPointSpec)."""

    net_label: str
    condition: str
    expected: str
    unit: str = ""
    tolerance: str = ""


class LifecycleState(str, Enum):
    ACTIVE = "active"
    NRND = "nrnd"
    EOL = "eol"
    OBSOLETE = "obsolete"
    UNKNOWN = "unknown"


class Lifecycle(BaseModel):
    state: LifecycleState
    source: str
    checked_on: date


class ParamRow(BaseModel):
    name: str
    original: str
    candidate: str


class Candidate(BaseModel):
    part_number: str
    manufacturer: str
    tier: Literal[1, 2, 3]
    pin_compatible: bool
    parameters: list[ParamRow] = Field(default_factory=list)
    circuit_changes: list[str] = Field(default_factory=list)
    rationale: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    sim_model: Literal["vendor", "behavioral", "none"] = "none"


class Substitution(BaseModel):
    refdes: str
    original_part_number: str
    candidates: list[Candidate] = Field(default_factory=list)
    selected: OptStrClaim


class Verdict(str, Enum):
    PASS = "pass"
    PASS_WITH_DEVIATIONS = "pass_with_deviations"
    FAIL = "fail"
    UNVERIFIED = "unverified"


class EquivalenceResult(BaseModel):
    block_id: str
    sim_type: Literal["spice", "logic", "timing", "boundary"]
    conditions: list[str] = Field(default_factory=list)
    measurements: dict[str, float] = Field(default_factory=dict)
    thresholds: dict[str, float] = Field(default_factory=dict)
    verdict: Verdict
    plots: list[str] = Field(default_factory=list)
    model_quality: Literal["vendor", "behavioral", "mixed"]


class Resolution(BaseModel):
    value: Any
    by: str
    at: datetime
    note: str = ""


class ReviewItem(BaseModel):
    id: str
    claim_id: str
    reason: str
    proposed: Any = None
    resolution: Resolution | None = None


class Source(BaseModel):
    id: str
    kind: Literal["manual", "photo", "datasheet", "api_response"]
    uri: str
    sha256: str
    publishable: bool
    cache_path: str | None = None
    distribution: str | None = None


class DistributionInfo(BaseModel):
    letter: Literal["A"]
    statement: str
    source_id: str
    method: Literal["text_layer", "model_transcription"]


class ConfigurationBaseline(BaseModel):
    card_pn: OptStrClaim
    card_revision: OptStrClaim
    tm_number: OptStrClaim
    tm_edition: OptStrClaim
    tm_changes: StrListClaim
    effectivity: OptStrClaim
    field_changes: StrListClaim
    host_system: OptStrClaim
    confirmation: OptStrClaim
    observed_revisions: list[StrClaim] = Field(default_factory=list)


class CardRecord(BaseModel):
    schema_version: str = SCHEMA_VERSION
    card_id: str
    title: str = ""
    distribution: DistributionInfo | None = None
    sources: dict[str, Source] = Field(default_factory=dict)
    config: ConfigurationBaseline | None = None
    parts: dict[str, Part] = Field(default_factory=dict)
    connections: dict[str, StrClaim] = Field(default_factory=dict)
    blocks: dict[str, Block] = Field(default_factory=dict)
    test_points: dict[str, Claim[ExpectedReading]] = Field(default_factory=dict)
    lifecycle: dict[str, Claim[Lifecycle]] = Field(default_factory=dict)
    substitutions: dict[str, Substitution] = Field(default_factory=dict)
    equivalence: list[EquivalenceResult] = Field(default_factory=list)
    review_items: dict[str, ReviewItem] = Field(default_factory=dict)
