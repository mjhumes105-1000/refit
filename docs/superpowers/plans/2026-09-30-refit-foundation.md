# REFIT Foundation Implementation Plan (Milestone 2 of 7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the stage-independent core of REFIT: the Card Record (claims with evidence), per-stage snapshots, human overrides, rule-check framework and acceptance policy, review queue, automation metrics, swappable AI model adapter with replay cache, Stage 0 intake with the Distribution A gate, the configuration gate, and a CLI tying them together.

**Architecture:** Every fact is a `Claim` (value + confidence + evidence + provenance + status). Stages produce a raw `CardRecord`; `finalize_stage` runs rule checks and the acceptance policy (recording the pure machine verdict once), re-applies human overrides from `overrides.json`, re-checks, syncs the review queue, and writes `cards/<id>/card.sNN.json`. AI is reached only through `ModelClient`, which validates replies against Pydantic schemas, retries once, and caches valid replies for deterministic replay.

**Tech Stack:** Python 3.12 (uv), Pydantic v2, PyMuPDF, httpx, Anthropic Python SDK, pytest.

**Spec:** `docs/superpowers/specs/2026-09-30-refit-design.md`

**Milestone map (separate plans):** 1 demo-card research + hand-built reference netlist (research, no code) · **2 Foundation (this plan)** · 3 parts list + schematic extraction + synthetic benchmark · 4 blocks, obsolescence, substitution · 5 equivalence harness (needs ngspice + Icarus Verilog installed) · 6 export (KiCad, report, PDF reference library) · 7 photo evidence.

## Global Constraints

- Python `>=3.12`; pin `3.12` in `.python-version`; all commands run through `uv run`.
- Pydantic v2 models; the Card Record is saved as JSON with `schema_version` (`"1"`).
- Must run on Windows and in folders whose paths contain spaces (e.g. `...\My Projects\REFIT`).
- **Distribution A only.** Any non-A distribution statement anywhere on the cover pages is a hard stop; missing statement is a hard stop (fail closed).
- Third-party photos and datasheets: `publishable=false`; `cache/` is gitignored and never committed.
- No stage calls an AI provider directly — only `ModelClient.ask`.
- Default model `claude-opus-5-5`, effort `high`, server-side refusal fallbacks `fallbacks="default"` with beta `server-side-fallback-2026-07-01`.
- Auto-accept: all applicable checks pass **and** confidence ≥ category threshold (default `0.9`); connections additionally need evidence from both `cv_trace` and `model_read`.
- Confidence is never the model's self-report.
- Snapshots: `cards/<card-id>/card.sNN.json`; human decisions: `cards/<card-id>/overrides.json`.
- Export (later milestone) is blocked until the configuration baseline is human-confirmed.
- Test suite runs fully offline: no network, no API key.
- Spec entity names mapped in code: TestPointSpec → `ExpectedReading`; LifecycleStatus → `Lifecycle` (avoids pytest collecting `Test*` classes).
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Distribution statement variants** — lowercase, split across lines, "approved for public release; distribution is unlimited" without a letter, and an A statement *plus* a C statement in the same document: the first three pass, the mixed one is rejected. (Task 10 tests.)
2. **Workspace paths with spaces** (`...\My Projects\...`) — snapshots, overrides, PDFs and CLI all work there. (Task 3 and Task 11 tests.)
3. **Pin-reference formats** — `U3-6`, `u3.6`, `U3 pin 6`, `U1A-3` normalize to one key everywhere: overrides, reference netlists, metrics. (Task 2, Task 4, Task 7 tests.)
4. **Messy model replies** — JSON wrapped in markdown fences or prose, or invalid twice: parsed when possible, retried once with the error, otherwise a clear `ModelOutputError`; invalid replies are never cached. (Task 8 tests.)
5. **Re-running a stage after human corrections** — corrections are re-applied, corrections that no longer match any claim are reported (not silently dropped), and metrics still score the original machine answer (a later-corrected false accept still counts as a false accept). (Task 4, Task 6, Task 7 tests.)

---

## File Structure

```
REFIT/
  pyproject.toml            # project, deps, `refit` console script, pytest config
  .python-version           # 3.12
  .gitignore
  refit/
    __init__.py             # __version__, SCHEMA_VERSION
    cli.py                  # argparse CLI: intake, review, resolve, accept, override, confirm-config, metrics, schema
    record/
      __init__.py
      claims.py             # Claim[T], Evidence, ProducedBy, ClaimStatus, aliases
      pins.py               # pin reference parsing/normalization
      model.py              # CardRecord and all entities
      netlist.py            # Net, net_id, build_nets
      walk.py               # iter_claims, claim_index
      snapshots.py          # per-stage snapshot I/O, JSON Schema export, atomic writes
      overrides.py          # Override, OverrideSet, add/load/apply overrides
      config_gate.py        # ConfigConsistencyCheck, confirm_configuration, require_confirmed
    checks/
      __init__.py
      base.py               # CheckFailure, Check protocol, run_checks
    review/
      __init__.py
      policy.py             # Thresholds, apply_policy
      queue.py              # review items: sync, open, resolve, accept
      finalize.py           # finalize_stage (checks → policy → overrides → policy → sync → save)
      metrics.py            # Reference, CategoryMetrics, compute_metrics
    models/
      __init__.py
      cache.py              # ResponseCache
      adapter.py            # ModelRequest, ModelClient, errors, default_client
      providers.py          # AnthropicProvider, ReplayOnlyProvider
    stages/
      __init__.py
      registry.py           # STAGE_CHECKS
      s00_intake.py         # Distribution A gate, source fetch, cover reading, baseline
  tests/
    conftest.py             # record builders, provider fakes, PDF maker, cover fixtures
    test_claims.py  test_model.py  test_snapshots.py  test_overrides.py
    test_policy.py  test_queue.py  test_metrics.py  test_models.py
    test_config_gate.py  test_intake.py  test_cli.py
```

---

### Task 1: Project scaffold and the Claim type

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `refit/__init__.py`, `refit/record/__init__.py`, `refit/record/claims.py`
- Test: `tests/test_claims.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `refit.SCHEMA_VERSION: str = "1"`; `refit.record.claims`: `ClaimStatus` (enum `PROPOSED/ACCEPTED/FLAGGED/OVERRIDDEN`), `Evidence(source_id: str, method: str, page: int|None, bbox: tuple[float,float,float,float]|None, excerpt: str|None)`, `ProducedBy(kind: "model"|"rule"|"human"|"deterministic", stage: str, detail: str)`, `Claim[T]` with fields `id, value, confidence, produced_by, evidence, status, flags, machine_status, machine_value` and property `category -> str`; aliases `StrClaim = Claim[str]`, `OptStrClaim = Claim[str | None]`, `StrListClaim = Claim[list[str]]`.

- [ ] **Step 1: Create project files**

`pyproject.toml`:
```toml
[project]
name = "refit"
version = "0.1.0"
description = "REFIT - Rapid Electronics Form-fit-function Integration Tool"
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.8",
  "pymupdf>=1.24",
  "httpx>=0.27",
  "anthropic>=0.60",
]

[project.scripts]
refit = "refit.cli:main"

[dependency-groups]
dev = ["pytest>=8"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`.python-version`:
```
3.12
```

`.gitignore`:
```
cache/
.venv/
__pycache__/
*.pyc
.pytest_cache/
```

`refit/__init__.py`:
```python
"""REFIT - Rapid Electronics Form-fit-function Integration Tool."""

__version__ = "0.1.0"
SCHEMA_VERSION = "1"
```

`refit/record/__init__.py`: empty file.

Run: `uv sync`
Expected: uv installs Python 3.12 if needed, creates `.venv`, installs deps and `refit` in editable mode.

- [ ] **Step 2: Write the failing test** — `tests/test_claims.py`

```python
import pytest
from pydantic import ValidationError

from refit.record.claims import Claim, ClaimStatus, Evidence, OptStrClaim, ProducedBy


def by_model() -> ProducedBy:
    return ProducedBy(kind="model", stage="s02", detail="test-model:v1")


def test_category_is_id_prefix():
    c = OptStrClaim(id="part:R12:value", value="10k", confidence=0.95, produced_by=by_model())
    assert c.category == "part"
    assert c.status is ClaimStatus.PROPOSED
    assert c.machine_status is None


def test_confidence_must_be_between_0_and_1():
    with pytest.raises(ValidationError):
        OptStrClaim(id="part:R1:value", value="1k", confidence=1.5, produced_by=by_model())


def test_assignment_is_validated_against_value_type():
    c = Claim[int](id="x:1", value=3, confidence=1.0, produced_by=by_model())
    with pytest.raises(ValidationError):
        c.value = "not a number"


def test_json_round_trip_keeps_evidence():
    c = OptStrClaim(
        id="part:C3:value",
        value=None,
        confidence=0.5,
        produced_by=by_model(),
        evidence=[Evidence(source_id="manual", method="model_read", page=4, bbox=(1, 2, 3, 4))],
    )
    assert OptStrClaim.model_validate_json(c.model_dump_json()) == c
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_claims.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refit.record.claims'`

- [ ] **Step 4: Write minimal implementation** — `refit/record/claims.py`

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_claims.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .python-version .gitignore uv.lock refit tests
git commit -m "feat: project scaffold and Claim type" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Card Record entities, pin references, nets

**Files:**
- Create: `refit/record/pins.py`, `refit/record/model.py`, `refit/record/netlist.py`, `tests/conftest.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Consumes: Task 1 claims.
- Produces:
  - `refit.record.pins`: `parse_pin_ref(text: str) -> tuple[str, str]`, `pin_key(refdes: str, pin: str) -> str` (format `"U3.6"`), `normalize_pin(text: str) -> str`.
  - `refit.record.model`: `PART_ATTRS`, `PinDef`, `Part(refdes, attrs: dict[str, OptStrClaim], pins)` with `attr(name) -> str|None`, `Block`, `ExpectedReading`, `LifecycleState`, `Lifecycle`, `ParamRow`, `Candidate`, `Substitution`, `Verdict`, `EquivalenceResult`, `Resolution(value, by, at, note)`, `ReviewItem(id, claim_id, reason, proposed, resolution)`, `Source(id, kind, uri, sha256, publishable, cache_path, distribution)`, `DistributionInfo(letter="A", statement, source_id, method)`, `ConfigurationBaseline` (claims `card_pn, card_revision, tm_number, tm_edition, tm_changes, effectivity, field_changes, host_system, confirmation`, list `observed_revisions`), `CardRecord` (fields `schema_version, card_id, title, distribution, sources, config, parts, connections: dict[str, StrClaim], blocks, test_points, lifecycle, substitutions, equivalence, review_items`).
  - Claim id conventions: `part:<refdes>:<attr>`, `conn:<pin_key>`, `block:<id>:<field>`, `config:<field>`, `config:observed_revision:<source>`, `substitution:<refdes>:selected`.
  - `refit.record.netlist`: `Net(id, key, label, members)`, `net_id(members) -> str`, `build_nets(connections, *, machine=False) -> list[Net]`. Net keys beginning with `_` are anonymous; others are labels.
  - `tests/conftest.py` fixture `mk` with `mk.conn(pin, net, confidence=0.95, evidence=None)`, `mk.part(refdes, **attrs)`, `mk.baseline(**values)`, `mk.record()`.

- [ ] **Step 1: Write the shared test builders** — `tests/conftest.py`

```python
from types import SimpleNamespace

import pytest

from refit.record.claims import (
    ClaimStatus,
    Evidence,
    OptStrClaim,
    ProducedBy,
    StrClaim,
    StrListClaim,
)
from refit.record.model import CardRecord, ConfigurationBaseline, Part

MODEL_S03 = ProducedBy(kind="model", stage="s03", detail="fake:v1")
MODEL_S02 = ProducedBy(kind="model", stage="s02", detail="fake:v1")
MODEL_S00 = ProducedBy(kind="model", stage="s00", detail="fake:v1")
HUMAN_S00 = ProducedBy(kind="human", stage="s00", detail="intake arguments")
BOTH_METHODS = [
    Evidence(source_id="manual", method="cv_trace", page=5),
    Evidence(source_id="manual", method="model_read", page=5),
]


def conn(pin: str, net: str, confidence: float = 0.95, evidence=None) -> StrClaim:
    return StrClaim(
        id=f"conn:{pin}",
        value=net,
        confidence=confidence,
        produced_by=MODEL_S03,
        evidence=list(BOTH_METHODS if evidence is None else evidence),
    )


def part(refdes: str, **attrs: str) -> Part:
    return Part(
        refdes=refdes,
        attrs={
            name: OptStrClaim(
                id=f"part:{refdes}:{name}",
                value=value,
                confidence=0.95,
                produced_by=MODEL_S02,
                evidence=[Evidence(source_id="manual", method="model_read", page=3)],
            )
            for name, value in attrs.items()
        },
    )


def baseline(**values) -> ConfigurationBaseline:
    v = dict(
        card_pn="SM-C-555123",
        card_revision="C",
        tm_number="TM 11-5840-000-34",
        tm_edition="1 June 1985",
        effectivity="Serial 100 and up",
        host_system="AN/XXX-1",
    )
    v.update(values)
    cover = [Evidence(source_id="manual", method="cover_read", page=1)]

    def given(field: str) -> OptStrClaim:
        return OptStrClaim(
            id=f"config:{field}", value=v[field], confidence=1.0,
            produced_by=HUMAN_S00, status=ClaimStatus.ACCEPTED,
        )

    def read(field: str) -> OptStrClaim:
        return OptStrClaim(
            id=f"config:{field}", value=v[field], confidence=0.95,
            produced_by=MODEL_S00, evidence=cover,
        )

    return ConfigurationBaseline(
        card_pn=given("card_pn"),
        card_revision=given("card_revision"),
        tm_number=read("tm_number"),
        tm_edition=read("tm_edition"),
        tm_changes=StrListClaim(
            id="config:tm_changes", value=[], confidence=0.95,
            produced_by=MODEL_S00, evidence=cover,
        ),
        effectivity=read("effectivity"),
        field_changes=StrListClaim(
            id="config:field_changes", value=[], confidence=1.0,
            produced_by=HUMAN_S00, status=ClaimStatus.ACCEPTED,
        ),
        host_system=given("host_system"),
        confirmation=OptStrClaim(
            id="config:confirmation", value=None, confidence=1.0,
            produced_by=ProducedBy(kind="deterministic", stage="s00"),
        ),
    )


def sample_record() -> CardRecord:
    return CardRecord(
        card_id="demo",
        parts={"R1": part("R1", value="10k"), "U1": part("U1", commercial_pn="LM741")},
        connections={
            "R1.1": conn("R1.1", "_n1"),
            "U1.2": conn("U1.2", "_n1"),
            "R1.2": conn("R1.2", "OUT"),
            "U1.6": conn("U1.6", "OUT"),
        },
        config=baseline(),
    )


@pytest.fixture
def mk():
    return SimpleNamespace(conn=conn, part=part, baseline=baseline, record=sample_record)
```

- [ ] **Step 2: Write the failing test** — `tests/test_model.py`

```python
import pytest

from refit.record.claims import ClaimStatus
from refit.record.model import CardRecord
from refit.record.netlist import build_nets, net_id
from refit.record.pins import normalize_pin, parse_pin_ref


@pytest.mark.parametrize(
    "text, expected",
    [
        ("U3.6", ("U3", "6")),
        ("u3.6", ("U3", "6")),
        ("U3-6", ("U3", "6")),
        ("U3 pin 6", ("U3", "6")),
        ("U3:6", ("U3", "6")),
        ("U1A-3", ("U1A", "3")),
        ("Q2.E", ("Q2", "E")),
        ("  CR12 . 1 ", ("CR12", "1")),
    ],
)
def test_pin_refs_normalize(text, expected):
    assert parse_pin_ref(text) == expected
    assert normalize_pin(text) == f"{expected[0]}.{expected[1]}"


@pytest.mark.parametrize("text", ["U36", "", "pin 6", "U3."])
def test_bad_pin_refs_raise(text):
    with pytest.raises(ValueError):
        parse_pin_ref(text)


def test_card_record_json_round_trip(mk):
    rec = mk.record()
    again = CardRecord.model_validate_json(rec.model_dump_json())
    assert again == rec
    assert again.parts["R1"].attr("value") == "10k"
    assert again.parts["R1"].attr("missing") is None


def test_net_id_is_order_invariant():
    assert net_id(["U1.2", "R1.1"]) == net_id(["R1.1", "U1.2"])
    assert net_id(["R1.1"]) != net_id(["R1.2"])


def test_build_nets_groups_pins_and_labels(mk):
    nets = build_nets(mk.record().connections)
    assert [n.members for n in nets] == [["R1.1", "U1.2"], ["R1.2", "U1.6"]]
    assert nets[0].label is None
    assert nets[1].label == "OUT"


def test_build_nets_machine_view_uses_first_verdict_and_skips_human_pins(mk):
    rec = mk.record()
    for claim in rec.connections.values():
        claim.machine_status = ClaimStatus.ACCEPTED
        claim.machine_value = claim.value
    rec.connections["U1.6"].value = "_n1"  # later human correction
    human = mk.conn("R9.1", "OUT")          # human-added pin, never machine-evaluated
    rec.connections["R9.1"] = human
    nets = build_nets(rec.connections, machine=True)
    assert [n.members for n in nets] == [["R1.1", "U1.2"], ["R1.2", "U1.6"]]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refit.record.model'`

- [ ] **Step 4: Write the implementation**

`refit/record/pins.py`:
```python
"""Pin references: one canonical key ("U3.6") for every way people write a pin."""

import re

_PIN_RE = re.compile(
    r"^\s*([A-Z]+\d+[A-Z]?)\s*(?:\.|-|:|\s+PIN\s+|\s+)\s*([A-Z0-9]+)\s*$",
    re.IGNORECASE,
)


def parse_pin_ref(text: str) -> tuple[str, str]:
    match = _PIN_RE.match(text)
    if match is None:
        raise ValueError(f"not a pin reference: {text!r}")
    return match.group(1).upper(), match.group(2).upper()


def pin_key(refdes: str, pin: str) -> str:
    r, p = refdes.strip().upper(), pin.strip().upper()
    if not r or not p:
        raise ValueError(f"empty refdes or pin: {refdes!r}, {pin!r}")
    return f"{r}.{p}"


def normalize_pin(text: str) -> str:
    return pin_key(*parse_pin_ref(text))
```

`refit/record/model.py`:
```python
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
```

`refit/record/netlist.py`:
```python
"""Nets are derived from per-pin net assignments; net IDs are stable for stable membership."""

import hashlib
from collections import defaultdict

from pydantic import BaseModel

from refit.record.claims import StrClaim


class Net(BaseModel):
    id: str
    key: str
    label: str | None
    members: list[str]


def net_id(members: list[str]) -> str:
    joined = ",".join(sorted(members))
    return "N" + hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]


def build_nets(connections: dict[str, StrClaim], *, machine: bool = False) -> list[Net]:
    """Group pins by assigned net key.

    machine=True uses each pin's first automated verdict and skips pins that no
    automated stage produced (e.g. pins a human added).
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for pin, claim in connections.items():
        if machine:
            if claim.machine_status is None:
                continue
            key = claim.machine_value
        else:
            key = claim.value
        groups[key].append(pin)
    nets = [
        Net(
            id=net_id(pins),
            key=key,
            label=None if key.startswith("_") else key,
            members=sorted(pins),
        )
        for key, pins in groups.items()
    ]
    return sorted(nets, key=lambda n: n.members[0])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_model.py tests/test_claims.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add refit/record tests/conftest.py tests/test_model.py
git commit -m "feat: Card Record entities, pin references and nets" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Claim walking and per-stage snapshots

**Files:**
- Create: `refit/record/walk.py`, `refit/record/snapshots.py`
- Test: `tests/test_snapshots.py`

**Interfaces:**
- Consumes: `CardRecord`, `Claim` (Tasks 1–2).
- Produces:
  - `refit.record.walk`: `iter_claims(obj) -> Iterator[Claim]`, `claim_index(obj) -> dict[str, Claim]`, `DuplicateClaimId(ValueError)`.
  - `refit.record.snapshots`: `STAGE_IDS = ("s00", ..., "s09")`, `snapshot_path(card_dir: Path, stage: str) -> Path`, `save_snapshot(record, card_dir, stage) -> Path`, `load_snapshot(card_dir, stage) -> CardRecord`, `latest_snapshot(card_dir) -> tuple[str, CardRecord] | None`, `export_json_schema(path: Path) -> Path`, `write_text_atomic(path: Path, text: str) -> None`, errors `SnapshotNotFound(FileNotFoundError)`, `SchemaVersionError(ValueError)`.

- [ ] **Step 1: Write the failing test** — `tests/test_snapshots.py`

```python
import json

import pytest

from refit.record.snapshots import (
    SchemaVersionError,
    SnapshotNotFound,
    export_json_schema,
    latest_snapshot,
    load_snapshot,
    save_snapshot,
    snapshot_path,
)
from refit.record.walk import DuplicateClaimId, claim_index, iter_claims


def test_iter_claims_finds_every_claim(mk):
    ids = {c.id for c in iter_claims(mk.record())}
    assert {"part:R1:value", "part:U1:commercial_pn", "conn:R1.1", "conn:U1.6"} <= ids
    assert {"config:card_pn", "config:tm_changes", "config:confirmation"} <= ids


def test_claim_index_rejects_duplicate_ids(mk):
    rec = mk.record()
    rec.parts["R1-copy"] = mk.part("R1", value="22k")
    with pytest.raises(DuplicateClaimId):
        claim_index(rec)


def test_snapshot_round_trip_in_path_with_spaces(mk, tmp_path):
    card_dir = tmp_path / "My Projects" / "cards" / "demo card"
    path = save_snapshot(mk.record(), card_dir, "s03")
    assert path == card_dir / "card.s03.json"
    assert load_snapshot(card_dir, "s03") == mk.record()


def test_saving_one_stage_leaves_others_untouched(mk, tmp_path):
    save_snapshot(mk.record(), tmp_path, "s02")
    before = (tmp_path / "card.s02.json").read_text(encoding="utf-8")
    changed = mk.record()
    changed.title = "changed"
    save_snapshot(changed, tmp_path, "s03")
    assert (tmp_path / "card.s02.json").read_text(encoding="utf-8") == before
    assert not list(tmp_path.glob("*.tmp"))


def test_latest_snapshot_picks_highest_stage(mk, tmp_path):
    assert latest_snapshot(tmp_path) is None
    save_snapshot(mk.record(), tmp_path, "s00")
    later = mk.record()
    later.title = "later"
    save_snapshot(later, tmp_path, "s02")
    stage, rec = latest_snapshot(tmp_path)
    assert stage == "s02" and rec.title == "later"


def test_missing_snapshot_and_bad_stage(tmp_path):
    with pytest.raises(SnapshotNotFound):
        load_snapshot(tmp_path, "s05")
    with pytest.raises(ValueError):
        snapshot_path(tmp_path, "s10")


def test_schema_version_mismatch_is_refused(mk, tmp_path):
    path = save_snapshot(mk.record(), tmp_path, "s00")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = "999"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SchemaVersionError):
        load_snapshot(tmp_path, "s00")


def test_export_json_schema(tmp_path):
    out = export_json_schema(tmp_path / "schema" / "card-record.schema.json")
    schema = json.loads(out.read_text(encoding="utf-8"))
    assert schema["title"] == "CardRecord"
    assert "connections" in schema["properties"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_snapshots.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refit.record.snapshots'`

- [ ] **Step 3: Write the implementation**

`refit/record/walk.py`:
```python
"""Find every Claim inside a record (or any part of one)."""

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel

from refit.record.claims import Claim


class DuplicateClaimId(ValueError):
    pass


def iter_claims(obj: Any) -> Iterator[Claim]:
    if isinstance(obj, Claim):
        yield obj
    elif isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            yield from iter_claims(getattr(obj, name))
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from iter_claims(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            yield from iter_claims(value)


def claim_index(obj: Any) -> dict[str, Claim]:
    index: dict[str, Claim] = {}
    for claim in iter_claims(obj):
        if claim.id in index:
            raise DuplicateClaimId(claim.id)
        index[claim.id] = claim
    return index
```

`refit/record/snapshots.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_snapshots.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add refit/record/walk.py refit/record/snapshots.py tests/test_snapshots.py
git commit -m "feat: claim walking and per-stage snapshots" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Human overrides

**Files:**
- Create: `refit/record/overrides.py`
- Test: `tests/test_overrides.py`

**Interfaces:**
- Consumes: `claim_index` (Task 3), `write_text_atomic` (Task 3), `normalize_pin` (Task 2), `StrClaim`, `ProducedBy`, `ClaimStatus` (Task 1).
- Produces: `OVERRIDES_FILE = "overrides.json"`, `Override(claim_id, value, by, at: datetime, note="")`, `OverrideSet(overrides: dict[str, Override])`, `normalize_claim_id(claim_id) -> str`, `load_overrides(card_dir) -> OverrideSet`, `save_overrides(card_dir, overrides) -> Path`, `add_override(card_dir, override) -> OverrideSet`, `ApplyResult(record, orphans: list[str])`, `apply_overrides(record, overrides) -> ApplyResult`, `OverrideValueError(ValueError)`.
- Behavior: overriding sets `value`, `status=OVERRIDDEN`, `confidence=1.0`, `produced_by=human`; it keeps `flags`, `machine_status`, `machine_value`. An override for a missing `conn:` claim creates that connection; any other missing claim is an orphan.

- [ ] **Step 1: Write the failing test** — `tests/test_overrides.py`

```python
from datetime import datetime, timezone

import pytest

from refit.record.claims import ClaimStatus
from refit.record.overrides import (
    Override,
    OverrideSet,
    OverrideValueError,
    add_override,
    apply_overrides,
    load_overrides,
)

T0 = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def ov(claim_id, value, by="mh"):
    return Override(claim_id=claim_id, value=value, by=by, at=T0)


def test_override_replaces_value_and_marks_human(mk):
    result = apply_overrides(mk.record(), OverrideSet(overrides={"part:R1:value": ov("part:R1:value", "4.7k")}))
    claim = result.record.parts["R1"].attrs["value"]
    assert claim.value == "4.7k"
    assert claim.status is ClaimStatus.OVERRIDDEN
    assert claim.confidence == 1.0
    assert claim.produced_by.kind == "human" and claim.produced_by.detail == "mh"
    assert result.orphans == []


def test_override_keeps_machine_verdict_and_is_idempotent(mk):
    rec = mk.record()
    claim = rec.parts["R1"].attrs["value"]
    claim.machine_status = ClaimStatus.ACCEPTED
    claim.machine_value = "10k"
    claim.flags = ["low_confidence"]
    overrides = OverrideSet(overrides={"part:R1:value": ov("part:R1:value", "4.7k")})
    once = apply_overrides(rec, overrides).record
    twice = apply_overrides(once, overrides).record
    for r in (once, twice):
        c = r.parts["R1"].attrs["value"]
        assert (c.value, c.machine_status, c.machine_value, c.flags) == (
            "4.7k", ClaimStatus.ACCEPTED, "10k", ["low_confidence"],
        )
    assert rec.parts["R1"].attrs["value"].value == "10k"  # input not mutated


def test_orphan_override_is_reported_not_dropped(mk):
    result = apply_overrides(mk.record(), OverrideSet(overrides={"part:R99:value": ov("part:R99:value", "1k")}))
    assert result.orphans == ["part:R99:value"]


def test_connection_override_creates_missing_pin_with_normalized_id(mk, tmp_path):
    add_override(tmp_path, ov("conn:u9-3", "OUT"))
    overrides = load_overrides(tmp_path)
    assert list(overrides.overrides) == ["conn:U9.3"]
    rec = apply_overrides(mk.record(), overrides).record
    added = rec.connections["U9.3"]
    assert added.value == "OUT"
    assert added.status is ClaimStatus.OVERRIDDEN
    assert added.machine_status is None


def test_wrong_value_type_raises(mk):
    with pytest.raises(OverrideValueError):
        apply_overrides(mk.record(), OverrideSet(overrides={"config:tm_changes": ov("config:tm_changes", 5)}))


def test_overrides_file_round_trip_latest_wins(tmp_path):
    assert load_overrides(tmp_path).overrides == {}
    add_override(tmp_path, ov("part:R1:value", "1k"))
    add_override(tmp_path, ov("part:R1:value", "2k", by="reviewer2"))
    loaded = load_overrides(tmp_path)
    assert loaded.overrides["part:R1:value"].value == "2k"
    assert loaded.overrides["part:R1:value"].by == "reviewer2"
    assert loaded.overrides["part:R1:value"].at == T0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_overrides.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refit.record.overrides'`

- [ ] **Step 3: Write the implementation** — `refit/record/overrides.py`

```python
"""Human decisions live in overrides.json and are re-applied after every stage run."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from refit.record.claims import ClaimStatus, ProducedBy, StrClaim
from refit.record.model import CardRecord
from refit.record.pins import normalize_pin
from refit.record.snapshots import write_text_atomic
from refit.record.walk import claim_index

OVERRIDES_FILE = "overrides.json"


class OverrideValueError(ValueError):
    pass


class Override(BaseModel):
    claim_id: str
    value: Any
    by: str
    at: datetime
    note: str = ""


class OverrideSet(BaseModel):
    overrides: dict[str, Override] = Field(default_factory=dict)


@dataclass
class ApplyResult:
    record: CardRecord
    orphans: list[str]


def normalize_claim_id(claim_id: str) -> str:
    if claim_id.startswith("conn:"):
        return "conn:" + normalize_pin(claim_id.removeprefix("conn:"))
    return claim_id


def load_overrides(card_dir: Path) -> OverrideSet:
    path = card_dir / OVERRIDES_FILE
    if not path.exists():
        return OverrideSet()
    return OverrideSet.model_validate_json(path.read_text(encoding="utf-8"))


def save_overrides(card_dir: Path, overrides: OverrideSet) -> Path:
    path = card_dir / OVERRIDES_FILE
    write_text_atomic(path, overrides.model_dump_json(indent=2))
    return path


def add_override(card_dir: Path, override: Override) -> OverrideSet:
    override = override.model_copy(update={"claim_id": normalize_claim_id(override.claim_id)})
    current = load_overrides(card_dir)
    current.overrides[override.claim_id] = override
    save_overrides(card_dir, current)
    return current


def apply_overrides(record: CardRecord, overrides: OverrideSet) -> ApplyResult:
    rec = record.model_copy(deep=True)
    index = claim_index(rec)
    orphans: list[str] = []
    for override in overrides.overrides.values():
        human = ProducedBy(kind="human", stage="review", detail=override.by)
        claim = index.get(override.claim_id)
        try:
            if claim is None:
                if override.claim_id.startswith("conn:"):
                    pin = override.claim_id.removeprefix("conn:")
                    rec.connections[pin] = StrClaim(
                        id=override.claim_id,
                        value=override.value,
                        confidence=1.0,
                        produced_by=human,
                        status=ClaimStatus.OVERRIDDEN,
                    )
                else:
                    orphans.append(override.claim_id)
                continue
            claim.value = override.value
        except ValidationError as exc:
            raise OverrideValueError(
                f"override for {override.claim_id} has the wrong type: {exc}"
            ) from exc
        claim.status = ClaimStatus.OVERRIDDEN
        claim.confidence = 1.0
        claim.produced_by = human
    return ApplyResult(record=rec, orphans=sorted(orphans))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_overrides.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add refit/record/overrides.py tests/test_overrides.py
git commit -m "feat: human overrides file and re-application" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Rule-check framework and acceptance policy

**Files:**
- Create: `refit/checks/__init__.py` (empty), `refit/checks/base.py`, `refit/review/__init__.py` (empty), `refit/review/policy.py`
- Test: `tests/test_policy.py`

**Interfaces:**
- Consumes: `iter_claims`, `claim_index` (Task 3), `CardRecord`, `ClaimStatus`.
- Produces:
  - `refit.checks.base`: `CheckFailure(check: str, claim_ids: tuple[str, ...], message: str)` (frozen dataclass), `Check` protocol (`name: str`, `run(record) -> list[CheckFailure]`), `run_checks(record, checks) -> list[CheckFailure]`.
  - `refit.review.policy`: `REQUIRED_CONN_METHODS = frozenset({"cv_trace", "model_read"})`, `Thresholds(default=0.9, per_category={})` with `for_category(cat) -> float`, `apply_policy(record, failures, thresholds) -> CardRecord`.
- Behavior: skips claims that are `OVERRIDDEN` or human-produced. Flags = sorted failed check names, then `no_independent_agreement` (conn only), then `low_confidence`. Status `FLAGGED` if any flag else `ACCEPTED`. Records `machine_status`/`machine_value` only when `machine_status is None`. A failure naming an unknown claim id raises `ValueError`.

- [ ] **Step 1: Write the failing test** — `tests/test_policy.py`

```python
import pytest

from refit.checks.base import CheckFailure, run_checks
from refit.record.claims import ClaimStatus, Evidence
from refit.review.policy import Thresholds, apply_policy


class FailClaim:
    name = "fail_claim"

    def __init__(self, claim_id):
        self.claim_id = claim_id

    def run(self, record):
        return [CheckFailure(self.name, (self.claim_id,), "forced failure")]


def test_confident_claim_with_no_failures_is_accepted(mk):
    rec = apply_policy(mk.record(), [], Thresholds())
    claim = rec.connections["R1.1"]
    assert claim.status is ClaimStatus.ACCEPTED
    assert claim.machine_status is ClaimStatus.ACCEPTED
    assert claim.machine_value == "_n1"
    assert claim.flags == []


def test_failed_check_flags_even_a_confident_claim(mk):
    raw = mk.record()
    rec = apply_policy(raw, run_checks(raw, [FailClaim("conn:R1.1")]), Thresholds())
    claim = rec.connections["R1.1"]
    assert claim.confidence == 0.95
    assert claim.status is ClaimStatus.FLAGGED
    assert claim.flags == ["fail_claim"]


def test_low_confidence_is_flagged(mk):
    raw = mk.record()
    raw.connections["U1.2"] = mk.conn("U1.2", "_n1", confidence=0.5)
    rec = apply_policy(raw, [], Thresholds())
    assert rec.connections["U1.2"].flags == ["low_confidence"]


def test_connection_needs_cv_and_model_agreement(mk):
    raw = mk.record()
    raw.connections["U1.2"] = mk.conn(
        "U1.2", "_n1", evidence=[Evidence(source_id="manual", method="model_read")]
    )
    rec = apply_policy(raw, [], Thresholds())
    assert rec.connections["U1.2"].flags == ["no_independent_agreement"]


def test_per_category_threshold(mk):
    rec = apply_policy(mk.record(), [], Thresholds(per_category={"part": 0.99}))
    assert rec.parts["R1"].attrs["value"].status is ClaimStatus.FLAGGED
    assert rec.connections["R1.1"].status is ClaimStatus.ACCEPTED


def test_human_claims_are_left_alone(mk):
    rec = apply_policy(mk.record(), [], Thresholds())
    assert rec.config.card_pn.status is ClaimStatus.ACCEPTED
    assert rec.config.card_pn.machine_status is None


def test_machine_verdict_is_recorded_only_once(mk):
    raw = mk.record()
    first = apply_policy(raw, run_checks(raw, [FailClaim("conn:R1.1")]), Thresholds())
    second = apply_policy(first, [], Thresholds())
    claim = second.connections["R1.1"]
    assert claim.status is ClaimStatus.ACCEPTED
    assert claim.machine_status is ClaimStatus.FLAGGED


def test_failure_for_unknown_claim_raises(mk):
    with pytest.raises(ValueError):
        apply_policy(mk.record(), [CheckFailure("x", ("conn:NOPE.1",), "")], Thresholds())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_policy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refit.checks'`

- [ ] **Step 3: Write the implementation**

`refit/checks/base.py`:
```python
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
```

`refit/review/policy.py`:
```python
"""Acceptance policy: AI proposes, rules check, and only clean confident claims are auto-accepted."""

from collections import defaultdict

from pydantic import BaseModel, Field

from refit.checks.base import CheckFailure
from refit.record.claims import ClaimStatus
from refit.record.model import CardRecord
from refit.record.walk import claim_index

REQUIRED_CONN_METHODS = frozenset({"cv_trace", "model_read"})


class Thresholds(BaseModel):
    default: float = 0.9
    per_category: dict[str, float] = Field(default_factory=dict)

    def for_category(self, category: str) -> float:
        return self.per_category.get(category, self.default)


def apply_policy(
    record: CardRecord, failures: list[CheckFailure], thresholds: Thresholds
) -> CardRecord:
    rec = record.model_copy(deep=True)
    index = claim_index(rec)
    failed: dict[str, set[str]] = defaultdict(set)
    for failure in failures:
        for claim_id in failure.claim_ids:
            if claim_id not in index:
                raise ValueError(f"check {failure.check!r} names unknown claim {claim_id!r}")
            failed[claim_id].add(failure.check)

    for claim in index.values():
        if claim.status is ClaimStatus.OVERRIDDEN or claim.produced_by.kind == "human":
            continue
        flags = sorted(failed.get(claim.id, set()))
        if claim.category == "conn":
            methods = {e.method for e in claim.evidence}
            if not REQUIRED_CONN_METHODS <= methods:
                flags.append("no_independent_agreement")
        if claim.confidence < thresholds.for_category(claim.category):
            flags.append("low_confidence")
        claim.flags = flags
        claim.status = ClaimStatus.FLAGGED if flags else ClaimStatus.ACCEPTED
        if claim.machine_status is None:
            claim.machine_status = claim.status
            claim.machine_value = claim.value
    return rec
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_policy.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add refit/checks refit/review tests/test_policy.py
git commit -m "feat: rule-check framework and acceptance policy" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Review queue and stage finalization

**Files:**
- Create: `refit/review/queue.py`, `refit/review/finalize.py`
- Test: `tests/test_queue.py`

**Interfaces:**
- Consumes: `apply_policy`, `Thresholds` (Task 5); `run_checks`, `Check` (Task 5); `load_overrides`, `apply_overrides`, `add_override`, `Override`, `OverrideSet` (Task 4); `save_snapshot` (Task 3); `iter_claims`.
- Produces:
  - `refit.review.queue`: `ReviewError(ValueError)`, `review_item_id(claim_id) -> str` (`"rv:" + claim_id`), `sync_review_items(record, overrides) -> CardRecord`, `open_items(record) -> list[ReviewItem]`, `resolve_item(card_dir, record, item_id, value, by, note="", now=None) -> Override`, `accept_item(card_dir, record, item_id, by, now=None) -> Override`.
  - `refit.review.finalize`: `StageOutcome(record, orphans, snapshot)`, `finalize_stage(raw, card_dir, stage, checks, thresholds=None) -> StageOutcome`. Order: checks → policy (records machine verdict) → apply overrides → checks → policy → sync review items → save snapshot.
- Behavior: open item for every `FLAGGED` claim (`reason` = flags joined by `", "`, `proposed` = JSON value). Resolved item for every `OVERRIDDEN` claim that has an override (`reason` = flags or `"manual correction"`, `proposed` = machine value, `resolution` from the override).

- [ ] **Step 1: Write the failing test** — `tests/test_queue.py`

```python
from datetime import datetime, timezone

import pytest

from refit.record.claims import ClaimStatus
from refit.record.overrides import Override, add_override
from refit.review.finalize import finalize_stage
from refit.review.queue import ReviewError, accept_item, open_items, resolve_item

T0 = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def low_conf_record(mk):
    raw = mk.record()
    raw.connections["U1.2"] = mk.conn("U1.2", "_n1", confidence=0.5)
    return raw


def test_flagged_claims_become_open_review_items(mk, tmp_path):
    out = finalize_stage(low_conf_record(mk), tmp_path, "s03", [])
    items = open_items(out.record)
    assert [i.id for i in items] == ["rv:conn:U1.2"]
    assert items[0].reason == "low_confidence"
    assert items[0].proposed == "_n1"
    assert out.snapshot == tmp_path / "card.s03.json"


def test_resolving_writes_override_and_refinalizing_closes_item(mk, tmp_path):
    out = finalize_stage(low_conf_record(mk), tmp_path, "s03", [])
    resolve_item(tmp_path, out.record, "rv:conn:U1.2", "OUT", by="mh", now=T0)
    again = finalize_stage(out.record, tmp_path, "s03", [])
    claim = again.record.connections["U1.2"]
    assert (claim.status, claim.value) == (ClaimStatus.OVERRIDDEN, "OUT")
    assert (claim.machine_status, claim.machine_value) == (ClaimStatus.FLAGGED, "_n1")
    assert open_items(again.record) == []
    item = again.record.review_items["rv:conn:U1.2"]
    assert item.resolution.by == "mh" and item.resolution.at == T0
    assert item.proposed == "_n1"


def test_accept_item_keeps_proposed_value(mk, tmp_path):
    out = finalize_stage(low_conf_record(mk), tmp_path, "s03", [])
    accept_item(tmp_path, out.record, "rv:conn:U1.2", by="mh", now=T0)
    again = finalize_stage(out.record, tmp_path, "s03", [])
    assert again.record.connections["U1.2"].value == "_n1"
    assert again.record.connections["U1.2"].status is ClaimStatus.OVERRIDDEN


def test_correcting_an_auto_accepted_claim_is_recorded(mk, tmp_path):
    add_override(tmp_path, Override(claim_id="part:R1:value", value="4.7k", by="mh", at=T0))
    out = finalize_stage(mk.record(), tmp_path, "s02", [])
    claim = out.record.parts["R1"].attrs["value"]
    assert (claim.machine_status, claim.machine_value, claim.value) == (
        ClaimStatus.ACCEPTED, "10k", "4.7k",
    )
    item = out.record.review_items["rv:part:R1:value"]
    assert item.reason == "manual correction" and item.resolution.value == "4.7k"


def test_rerun_reapplies_corrections_and_reports_orphans(mk, tmp_path):
    out = finalize_stage(low_conf_record(mk), tmp_path, "s03", [])
    resolve_item(tmp_path, out.record, "rv:conn:U1.2", "OUT", by="mh", now=T0)
    add_override(tmp_path, Override(claim_id="part:R99:value", value="1k", by="mh", at=T0))
    rerun = finalize_stage(low_conf_record(mk), tmp_path, "s03", [])  # fresh machine output
    assert rerun.record.connections["U1.2"].value == "OUT"
    assert rerun.orphans == ["part:R99:value"]


def test_resolve_unknown_item_raises(mk, tmp_path):
    out = finalize_stage(mk.record(), tmp_path, "s03", [])
    with pytest.raises(ReviewError):
        resolve_item(tmp_path, out.record, "rv:conn:NOPE.1", "x", by="mh")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_queue.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refit.review.finalize'`

- [ ] **Step 3: Write the implementation**

`refit/review/queue.py`:
```python
"""Review queue: flagged claims become items; resolutions are written as overrides."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from refit.record.claims import ClaimStatus
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
```

`refit/review/finalize.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_queue.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add refit/review/queue.py refit/review/finalize.py tests/test_queue.py
git commit -m "feat: review queue and stage finalization" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Automation and false-accept metrics

**Files:**
- Create: `refit/review/metrics.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: `iter_claims`, `normalize_pin`, `ClaimStatus`, `CardRecord`; tests also use `apply_policy`, `finalize_stage`, `add_override`.
- Produces: `METRIC_CATEGORIES = ("part", "conn", "block", "substitution")`, `Reference(values: dict[str, Any], nets: list[list[str]])`, `CategoryMetrics(category, reference_facts, auto_accepted, auto_correct, auto_wrong, unscored, automation_rate: float|None, false_accept_rate: float|None)`, `load_reference(path) -> Reference`, `compute_metrics(record, reference) -> dict[str, CategoryMetrics]`.
- Definitions: scoring uses `machine_status`/`machine_value` only. `automation_rate = auto_correct / reference_facts`; `false_accept_rate = auto_wrong / (auto_correct + auto_wrong)`; either is `None` when its denominator is 0. A connection is correct when its machine net has exactly the same pins as its reference net; an accepted pin absent from the reference is wrong. If the reference has no nets, accepted connections are counted as `unscored`. Value comparison ignores case and repeated whitespace.

- [ ] **Step 1: Write the failing test** — `tests/test_metrics.py`

```python
from datetime import datetime, timezone

import pytest

from refit.record.overrides import Override, add_override
from refit.review.finalize import finalize_stage
from refit.review.metrics import Reference, compute_metrics, load_reference
from refit.review.policy import Thresholds, apply_policy

T0 = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def accepted(record):
    return apply_policy(record, [], Thresholds())


def test_perfect_connections_with_mixed_pin_formats(mk):
    ref = Reference(nets=[["R1-1", "u1.2"], ["R1 pin 2", "U1:6"]])
    m = compute_metrics(accepted(mk.record()), ref)["conn"]
    assert (m.reference_facts, m.auto_accepted, m.auto_correct, m.auto_wrong) == (4, 4, 4, 0)
    assert (m.automation_rate, m.false_accept_rate) == (1.0, 0.0)


def test_wrong_net_membership_is_a_false_accept(mk):
    ref = Reference(nets=[["R1.1", "U1.2"], ["R1.2"], ["U1.6"]])
    m = compute_metrics(accepted(mk.record()), ref)["conn"]
    assert (m.auto_correct, m.auto_wrong) == (2, 2)
    assert (m.automation_rate, m.false_accept_rate) == (0.5, 0.5)


def test_flagged_claims_do_not_count_as_automated(mk):
    raw = mk.record()
    raw.connections["U1.2"] = mk.conn("U1.2", "_n1", confidence=0.5)
    ref = Reference(nets=[["R1.1", "U1.2"], ["R1.2", "U1.6"]])
    m = compute_metrics(accepted(raw), ref)["conn"]
    assert (m.auto_accepted, m.auto_correct) == (3, 3)
    assert m.automation_rate == 0.75


def test_later_human_correction_still_counts_machine_answer(mk, tmp_path):
    add_override(tmp_path, Override(claim_id="part:R1:value", value="4.7k", by="mh", at=T0))
    rec = finalize_stage(mk.record(), tmp_path, "s02", []).record
    m = compute_metrics(rec, Reference(values={"part:R1:value": "4.7k"}))["part"]
    assert (m.reference_facts, m.auto_correct, m.auto_wrong) == (1, 0, 1)
    assert m.false_accept_rate == 1.0


def test_values_normalized_and_unscored_counted(mk):
    m = compute_metrics(accepted(mk.record()), Reference(values={"part:R1:value": " 10K "}))["part"]
    assert (m.auto_correct, m.auto_wrong, m.unscored) == (1, 0, 1)


def test_empty_reference_reports_none_not_zero_division(mk):
    metrics = compute_metrics(accepted(mk.record()), Reference())
    assert metrics["block"].automation_rate is None
    assert metrics["block"].false_accept_rate is None
    assert metrics["conn"].unscored == 4
    assert metrics["conn"].false_accept_rate is None
    assert list(metrics) == ["part", "conn", "block", "substitution"]


def test_pin_listed_in_two_reference_nets_is_rejected(mk):
    with pytest.raises(ValueError):
        compute_metrics(accepted(mk.record()), Reference(nets=[["R1.1"], ["r1-1"]]))


def test_load_reference(tmp_path):
    path = tmp_path / "reference.json"
    path.write_text('{"values": {"part:R1:value": "10k"}, "nets": [["R1.1", "U1.2"]]}', encoding="utf-8")
    ref = load_reference(path)
    assert ref.nets == [["R1.1", "U1.2"]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refit.review.metrics'`

- [ ] **Step 3: Write the implementation** — `refit/review/metrics.py`

```python
"""Automation and false-accept metrics against a hand-built reference.

Only the first automated verdict (machine_status / machine_value) is scored, so a
false accept that a human later corrected still counts against the machine.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from refit.record.claims import ClaimStatus
from refit.record.model import CardRecord
from refit.record.pins import normalize_pin
from refit.record.walk import iter_claims

METRIC_CATEGORIES = ("part", "conn", "block", "substitution")


class Reference(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    nets: list[list[str]] = Field(default_factory=list)


class CategoryMetrics(BaseModel):
    category: str
    reference_facts: int
    auto_accepted: int
    auto_correct: int
    auto_wrong: int
    unscored: int
    automation_rate: float | None
    false_accept_rate: float | None


def load_reference(path: Path) -> Reference:
    return Reference.model_validate_json(path.read_text(encoding="utf-8"))


def _norm(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    if isinstance(value, list):
        return sorted(_norm(v) for v in value)
    return value


def _rates(
    category: str, reference_facts: int, correct: int, wrong: int, unscored: int
) -> CategoryMetrics:
    accepted = correct + wrong
    return CategoryMetrics(
        category=category,
        reference_facts=reference_facts,
        auto_accepted=accepted,
        auto_correct=correct,
        auto_wrong=wrong,
        unscored=unscored,
        automation_rate=correct / reference_facts if reference_facts else None,
        false_accept_rate=wrong / accepted if accepted else None,
    )


def _reference_nets(reference: Reference) -> dict[str, frozenset[str]]:
    net_of: dict[str, frozenset[str]] = {}
    for net in reference.nets:
        members = frozenset(normalize_pin(p) for p in net)
        for pin in members:
            if pin in net_of:
                raise ValueError(f"reference lists pin {pin} in more than one net")
            net_of[pin] = members
    return net_of


def _connection_metrics(record: CardRecord, reference: Reference) -> CategoryMetrics:
    machine = {
        normalize_pin(pin): claim
        for pin, claim in record.connections.items()
        if claim.machine_status is not None
    }
    accepted = [p for p, c in machine.items() if c.machine_status is ClaimStatus.ACCEPTED]
    if not reference.nets:
        return _rates("conn", 0, 0, 0, len(accepted))
    ref = _reference_nets(reference)
    groups: dict[Any, set[str]] = {}
    for pin, claim in machine.items():
        groups.setdefault(claim.machine_value, set()).add(pin)
    correct = wrong = 0
    for pin in accepted:
        if ref.get(pin) == frozenset(groups[machine[pin].machine_value]):
            correct += 1
        else:
            wrong += 1
    return _rates("conn", len(ref), correct, wrong, 0)


def _value_metrics(record: CardRecord, reference: Reference, category: str) -> CategoryMetrics:
    reference_facts = sum(1 for k in reference.values if k.split(":", 1)[0] == category)
    correct = wrong = unscored = 0
    for claim in iter_claims(record):
        if claim.category != category or claim.machine_status is not ClaimStatus.ACCEPTED:
            continue
        if claim.id not in reference.values:
            unscored += 1
        elif _norm(claim.machine_value) == _norm(reference.values[claim.id]):
            correct += 1
        else:
            wrong += 1
    return _rates(category, reference_facts, correct, wrong, unscored)


def compute_metrics(record: CardRecord, reference: Reference) -> dict[str, CategoryMetrics]:
    return {
        category: (
            _connection_metrics(record, reference)
            if category == "conn"
            else _value_metrics(record, reference, category)
        )
        for category in METRIC_CATEGORIES
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add refit/review/metrics.py tests/test_metrics.py
git commit -m "feat: automation and false-accept metrics" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Model adapter, response cache, Anthropic provider

**Files:**
- Create: `refit/models/__init__.py` (empty), `refit/models/cache.py`, `refit/models/adapter.py`, `refit/models/providers.py`
- Modify: `tests/conftest.py` (append provider fakes)
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: Pydantic only.
- Produces:
  - `refit.models.cache.ResponseCache(root: Path)` with `get(key) -> str | None`, `put(key, text) -> None`.
  - `refit.models.adapter`: `ModelProvider` protocol (`name: str`, `complete(*, system: str, prompt: str, images: Sequence[bytes]) -> str`), `ModelRequest(stage, prompt_id, prompt_version, system, prompt, images: tuple[bytes, ...] = ())` (frozen dataclass), `request_key(provider_name, request, schema) -> str`, `extract_json(text) -> str`, `ModelClient(provider, cache, *, replay_only=False)` with `ask(request, schema: type[M]) -> M`, errors `ModelOutputError(RuntimeError)` (attribute `raw`), `ReplayMiss(LookupError)`, `ModelRefusal(RuntimeError)`, factory `default_client(cache_root: Path, *, replay_only=False) -> ModelClient`.
  - `refit.models.providers`: `DEFAULT_MODEL = "claude-opus-5-5"`, `DEFAULT_EFFORT = "high"`, `provider_name(model, effort) -> str` (`"anthropic:<model>:<effort>"`), `AnthropicProvider(model=DEFAULT_MODEL, effort=DEFAULT_EFFORT, client=None)`, `ReplayOnlyProvider(name)`.
  - `tests/conftest.py` fixture `routing_provider` → class `RoutingProvider(routes: dict[str, str])` that answers by exact `system` prompt and records `calls: list[tuple[system, prompt, n_images]]`.
- Behavior: the cache key covers provider name, prompt id and version, system, prompt, the schema's JSON Schema, and each image's SHA-256. Only schema-valid replies are cached, re-serialized as `model_dump_json()`. One retry, with the validation error appended to the prompt. The Anthropic provider sends images first and text last, `fallbacks="default"`, `betas=["server-side-fallback-2026-07-01"]`, and `output_config={"effort": effort}`. It raises `ModelRefusal` on `stop_reason == "refusal"` and `ModelOutputError` on `stop_reason == "max_tokens"`.

- [ ] **Step 1: Append provider fakes to `tests/conftest.py`**

```python
class RoutingProvider:
    """Answers each request by exact system prompt; records every call."""

    name = "routing"

    def __init__(self, routes: dict[str, str]):
        self.routes = routes
        self.calls: list[tuple[str, str, int]] = []

    def complete(self, *, system, prompt, images):
        self.calls.append((system, prompt, len(images)))
        if system not in self.routes:
            raise AssertionError(f"unexpected request with system prompt: {system[:60]!r}")
        return self.routes[system]


@pytest.fixture
def routing_provider():
    return RoutingProvider
```

- [ ] **Step 2: Write the failing test** — `tests/test_models.py`

```python
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from refit.models.adapter import (
    ModelClient,
    ModelOutputError,
    ModelRefusal,
    ModelRequest,
    ReplayMiss,
    request_key,
)
from refit.models.cache import ResponseCache
from refit.models.providers import AnthropicProvider

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16
GOOD = '{"refdes": "R1", "value": "10k"}'


class Reading(BaseModel):
    refdes: str
    value: str


class FakeProvider:
    name = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, *, system, prompt, images):
        self.calls.append(prompt)
        return self.replies.pop(0)


def req(**overrides):
    base = dict(stage="s02", prompt_id="parts", prompt_version="1", system="sys", prompt="read R1")
    base.update(overrides)
    return ModelRequest(**base)


def test_valid_reply_is_parsed_and_cached(tmp_path):
    provider = FakeProvider([GOOD])
    client = ModelClient(provider, ResponseCache(tmp_path))
    assert client.ask(req(), Reading) == Reading(refdes="R1", value="10k")
    assert client.ask(req(), Reading).value == "10k"
    assert len(provider.calls) == 1


def test_prompt_carries_the_json_schema(tmp_path):
    provider = FakeProvider([GOOD])
    ModelClient(provider, ResponseCache(tmp_path)).ask(req(), Reading)
    assert "JSON Schema" in provider.calls[0] and '"refdes"' in provider.calls[0]


@pytest.mark.parametrize(
    "reply",
    [
        f"```json\n{GOOD}\n```",
        f"```\n{GOOD}\n```",
        f"Here is the reading:\n{GOOD}\nLet me know if you need more.",
    ],
)
def test_fenced_or_wrapped_json_is_accepted(tmp_path, reply):
    client = ModelClient(FakeProvider([reply]), ResponseCache(tmp_path))
    assert client.ask(req(), Reading).refdes == "R1"


def test_invalid_reply_is_retried_once_with_the_error(tmp_path):
    provider = FakeProvider(['{"refdes": "R1"}', GOOD])
    assert ModelClient(provider, ResponseCache(tmp_path)).ask(req(), Reading).value == "10k"
    assert len(provider.calls) == 2
    assert "previous reply was invalid" in provider.calls[1]


def test_two_invalid_replies_raise_and_cache_nothing(tmp_path):
    cache = ResponseCache(tmp_path)
    with pytest.raises(ModelOutputError) as err:
        ModelClient(FakeProvider(["nope", "still nope"]), cache).ask(req(), Reading)
    assert err.value.raw == "still nope"
    with pytest.raises(ReplayMiss):
        ModelClient(FakeProvider([]), cache, replay_only=True).ask(req(), Reading)


def test_replay_only_miss_never_calls_provider(tmp_path):
    provider = FakeProvider([GOOD])
    with pytest.raises(ReplayMiss):
        ModelClient(provider, ResponseCache(tmp_path), replay_only=True).ask(req(), Reading)
    assert provider.calls == []


def test_cache_key_changes_with_prompt_version_and_images():
    base = request_key("p", req(), Reading)
    assert request_key("p", req(prompt_version="2"), Reading) != base
    assert request_key("p", req(images=(PNG,)), Reading) != base
    assert request_key("other", req(), Reading) != base
    assert request_key("p", req(), Reading) == base


def fake_anthropic(stop_reason="end_turn", text=GOOD):
    response = SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=None,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
    )
    messages = SimpleNamespace(kwargs=None)

    def create(**kwargs):
        messages.kwargs = kwargs
        return response

    messages.create = create
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def test_anthropic_provider_builds_request_and_reads_text():
    client, messages = fake_anthropic()
    provider = AnthropicProvider(client=client)
    assert provider.complete(system="be exact", prompt="read", images=[PNG]) == GOOD
    kw = messages.kwargs
    assert kw["model"] == "claude-opus-5-5"
    assert kw["fallbacks"] == "default"
    assert kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["output_config"] == {"effort": "high"}
    assert kw["system"] == "be exact"
    content = kw["messages"][0]["content"]
    assert content[0]["type"] == "image" and content[0]["source"]["media_type"] == "image/png"
    assert content[-1] == {"type": "text", "text": "read"}
    assert provider.name == "anthropic:claude-opus-5-5:high"


def test_anthropic_provider_raises_on_refusal_and_truncation():
    with pytest.raises(ModelRefusal):
        AnthropicProvider(client=fake_anthropic("refusal")[0]).complete(system="", prompt="x", images=[])
    with pytest.raises(ModelOutputError):
        AnthropicProvider(client=fake_anthropic("max_tokens")[0]).complete(system="", prompt="x", images=[])


def test_anthropic_provider_rejects_unknown_image_format():
    with pytest.raises(ValueError):
        AnthropicProvider(client=fake_anthropic()[0]).complete(system="", prompt="x", images=[b"GIF89a"])
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refit.models'`

- [ ] **Step 4: Write the implementation**

`refit/models/cache.py`:
```python
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
```

`refit/models/adapter.py`:
```python
"""The only door to AI models: validate, retry once, cache, replay."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from refit.models.cache import ResponseCache

M = TypeVar("M", bound=BaseModel)


class ModelOutputError(RuntimeError):
    def __init__(self, message: str, raw: str):
        super().__init__(message)
        self.raw = raw


class ReplayMiss(LookupError):
    pass


class ModelRefusal(RuntimeError):
    pass


class ModelProvider(Protocol):
    name: str

    def complete(self, *, system: str, prompt: str, images: Sequence[bytes]) -> str: ...


@dataclass(frozen=True)
class ModelRequest:
    stage: str
    prompt_id: str
    prompt_version: str
    system: str
    prompt: str
    images: tuple[bytes, ...] = ()


def request_key(provider_name: str, request: ModelRequest, schema: type[BaseModel]) -> str:
    h = hashlib.sha256()
    for part in (
        provider_name,
        request.prompt_id,
        request.prompt_version,
        request.system,
        request.prompt,
        json.dumps(schema.model_json_schema(), sort_keys=True),
    ):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    for image in request.images:
        h.update(hashlib.sha256(image).digest())
    return h.hexdigest()


def extract_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if not stripped.startswith(("{", "[")):
        start, end = stripped.find("{"), stripped.rfind("}")
        if start != -1 and end > start:
            stripped = stripped[start : end + 1]
    return stripped


def _schema_instruction(schema: type[BaseModel]) -> str:
    return (
        "\n\nRespond with only a JSON object that matches this JSON Schema:\n"
        + json.dumps(schema.model_json_schema(), indent=2)
    )


class ModelClient:
    def __init__(self, provider: ModelProvider, cache: ResponseCache, *, replay_only: bool = False):
        self.provider = provider
        self.cache = cache
        self.replay_only = replay_only

    def ask(self, request: ModelRequest, schema: type[M]) -> M:
        key = request_key(self.provider.name, request, schema)
        cached = self.cache.get(key)
        if cached is not None:
            return schema.model_validate_json(cached)
        if self.replay_only:
            raise ReplayMiss(
                f"{request.stage}/{request.prompt_id}: no cached reply (key {key[:12]}) in replay-only mode"
            )
        prompt = request.prompt + _schema_instruction(schema)
        raw, error = "", ""
        for attempt in range(2):
            text = prompt if attempt == 0 else (
                f"{prompt}\n\nYour previous reply was invalid: {error}\n"
                "Reply again with only the JSON object."
            )
            raw = self.provider.complete(system=request.system, prompt=text, images=request.images)
            try:
                parsed = schema.model_validate_json(extract_json(raw))
            except ValidationError as exc:
                error = str(exc)[:2000]
                continue
            self.cache.put(key, parsed.model_dump_json())
            return parsed
        raise ModelOutputError(
            f"{request.stage}/{request.prompt_id}: reply failed validation twice", raw
        )


def default_client(cache_root: Path, *, replay_only: bool = False) -> ModelClient:
    from refit.models.providers import (
        DEFAULT_EFFORT,
        DEFAULT_MODEL,
        AnthropicProvider,
        ReplayOnlyProvider,
        provider_name,
    )

    provider: ModelProvider
    if replay_only:
        provider = ReplayOnlyProvider(provider_name(DEFAULT_MODEL, DEFAULT_EFFORT))
    else:
        provider = AnthropicProvider()
    return ModelClient(provider, ResponseCache(cache_root), replay_only=replay_only)
```

`refit/models/providers.py`:
```python
"""Model providers. Swap these (per stage, later) for local or accredited-cloud models."""

import base64
from collections.abc import Sequence
from typing import Any

from refit.models.adapter import ModelOutputError, ModelRefusal, ReplayMiss

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def provider_name(model: str, effort: str) -> str:
    return f"anthropic:{model}:{effort}"


def _media_type(image: bytes) -> str:
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image.startswith(b"\xff\xd8"):
        return "image/jpeg"
    raise ValueError("unsupported image format; send PNG or JPEG")


class AnthropicProvider:
    def __init__(self, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT, client: Any = None):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self._client = client
        self.model = model
        self.effort = effort
        self.name = provider_name(model, effort)

    def complete(self, *, system: str, prompt: str, images: Sequence[bytes]) -> str:
        content: list[dict] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": _media_type(image),
                    "data": base64.standard_b64encode(image).decode("ascii"),
                },
            }
            for image in images
        ]
        content.append({"type": "text", "text": prompt})
        kwargs: dict[str, Any] = dict(
            model=self.model,
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": self.effort},
            messages=[{"role": "user", "content": content}],
        )
        if system:
            kwargs["system"] = system
        response = self._client.beta.messages.create(**kwargs)
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise ModelRefusal(f"model declined the request: {details}")
        if response.stop_reason == "max_tokens":
            raise ModelOutputError("reply truncated at max_tokens", raw="")
        return "".join(block.text for block in response.content if block.type == "text")


class ReplayOnlyProvider:
    """Carries the real provider's name (so cache keys match) but never calls out."""

    def __init__(self, name: str):
        self.name = name

    def complete(self, *, system: str, prompt: str, images: Sequence[bytes]) -> str:
        raise ReplayMiss("replay-only mode: live model calls are disabled")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: 12 passed

- [ ] **Step 6: Commit**

```bash
git add refit/models tests/conftest.py tests/test_models.py
git commit -m "feat: model adapter with validation, retry and replay cache" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Configuration gate

**Files:**
- Create: `refit/record/config_gate.py`, `refit/stages/__init__.py` (empty), `refit/stages/registry.py`
- Test: `tests/test_config_gate.py`

**Interfaces:**
- Consumes: `CheckFailure` (Task 5), `iter_claims` (Task 3), `add_override`, `Override` (Task 4), `ClaimStatus`, `CardRecord`, `finalize_stage` and `open_items` in tests.
- Produces:
  - `refit.record.config_gate`: `REQUIRED_CONFIG_FIELDS = ("card_pn", "card_revision", "tm_number", "host_system")`, `ConfigConsistencyCheck` (`name = "config_consistency"`), which emits failures named `config_consistency.missing`, `config_consistency.revision_mismatch` and `config_consistency.awaiting_confirmation`. Also `ConfigurationNotConfirmed(RuntimeError)`, `confirm_configuration(card_dir, record, by, now=None) -> Override` and `require_confirmed(record) -> None`.
  - `refit.stages.registry.STAGE_CHECKS: dict[str, list[Check]]`, with `"s00": [ConfigConsistencyCheck()]`.
- Behavior: confirmation is itself the claim `config:confirmation`; confirming writes an override whose value is the reviewer's name. `confirm_configuration` refuses while any other config claim is `FLAGGED`. `require_confirmed` (used by Stage 9 later) raises unless the confirmation claim is `OVERRIDDEN` with a value and no config claim is `FLAGGED`.

- [ ] **Step 1: Write the failing test** — `tests/test_config_gate.py`

```python
from datetime import datetime, timezone

import pytest

from refit.record.claims import ProducedBy, StrClaim
from refit.record.config_gate import (
    ConfigConsistencyCheck,
    ConfigurationNotConfirmed,
    confirm_configuration,
    require_confirmed,
)
from refit.review.finalize import finalize_stage
from refit.review.queue import accept_item, open_items

T0 = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
CHECKS = [ConfigConsistencyCheck()]


def finalize(record, card_dir):
    return finalize_stage(record, card_dir, "s00", CHECKS).record


def test_missing_required_field_is_flagged(mk, tmp_path):
    raw = mk.record()
    raw.config = mk.baseline(tm_number=None)
    items = {i.claim_id: i.reason for i in open_items(finalize(raw, tmp_path))}
    assert items["config:tm_number"] == "config_consistency.missing"


def test_awaiting_confirmation_is_an_open_item(mk, tmp_path):
    items = {i.claim_id: i.reason for i in open_items(finalize(mk.record(), tmp_path))}
    assert items == {"config:confirmation": "config_consistency.awaiting_confirmation"}


def test_confirm_refuses_while_config_items_are_open(mk, tmp_path):
    raw = mk.record()
    raw.config = mk.baseline(tm_number=None)
    rec = finalize(raw, tmp_path)
    with pytest.raises(ConfigurationNotConfirmed, match="config:tm_number"):
        confirm_configuration(tmp_path, rec, by="mh", now=T0)


def test_confirm_then_require_confirmed_passes(mk, tmp_path):
    rec = finalize(mk.record(), tmp_path)
    with pytest.raises(ConfigurationNotConfirmed):
        require_confirmed(rec)
    confirm_configuration(tmp_path, rec, by="mh", now=T0)
    rec = finalize(rec, tmp_path)
    require_confirmed(rec)
    assert rec.config.confirmation.value == "mh"
    assert open_items(rec) == []


def test_photo_revision_mismatch_blocks_after_confirmation(mk, tmp_path):
    rec = finalize(mk.record(), tmp_path)
    confirm_configuration(tmp_path, rec, by="mh", now=T0)
    rec = finalize(rec, tmp_path)
    rec.config.observed_revisions.append(
        StrClaim(
            id="config:observed_revision:photo1",
            value="D",
            confidence=0.95,
            produced_by=ProducedBy(kind="model", stage="s04", detail="fake:v1"),
        )
    )
    rec = finalize(rec, tmp_path)
    items = {i.claim_id: i.reason for i in open_items(rec)}
    assert items["config:observed_revision:photo1"] == "config_consistency.revision_mismatch"
    with pytest.raises(ConfigurationNotConfirmed, match="observed_revision"):
        require_confirmed(rec)
    accept_item(tmp_path, rec, "rv:config:observed_revision:photo1", by="mh", now=T0)
    require_confirmed(finalize(rec, tmp_path))


def test_require_confirmed_without_baseline_raises(mk):
    rec = mk.record()
    rec.config = None
    with pytest.raises(ConfigurationNotConfirmed):
        require_confirmed(rec)
```

Note on the last mismatch test: accepting the mismatched photo reading overrides that claim, which is the human saying "yes, the photo shows D and that's fine". A human who disagrees should instead correct the baseline's revision with `refit override`. Either way, a human resolves it.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config_gate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refit.record.config_gate'`

- [ ] **Step 3: Write the implementation**

`refit/record/config_gate.py`:
```python
"""Configuration gate: a redesign of the wrong revision is worse than none."""

from datetime import datetime, timezone
from pathlib import Path

from refit.checks.base import CheckFailure
from refit.record.claims import ClaimStatus
from refit.record.model import CardRecord
from refit.record.overrides import Override, add_override
from refit.record.walk import iter_claims

REQUIRED_CONFIG_FIELDS = ("card_pn", "card_revision", "tm_number", "host_system")


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


def confirm_configuration(
    card_dir: Path, record: CardRecord, by: str, now: datetime | None = None
) -> Override:
    if record.config is None:
        raise ConfigurationNotConfirmed("record has no configuration baseline; run intake first")
    blocking = [c for c in _flagged_config_ids(record) if c != record.config.confirmation.id]
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
    flagged = _flagged_config_ids(record)
    if flagged:
        raise ConfigurationNotConfirmed("open configuration issues: " + ", ".join(flagged))
```

`refit/stages/registry.py`:
```python
"""Which rule checks run after each stage. Later milestones add their stages here."""

from refit.checks.base import Check
from refit.record.config_gate import ConfigConsistencyCheck

STAGE_CHECKS: dict[str, list[Check]] = {
    "s00": [ConfigConsistencyCheck()],
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config_gate.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add refit/record/config_gate.py refit/stages tests/test_config_gate.py
git commit -m "feat: configuration gate with human confirmation" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Stage 0 intake with the Distribution A gate

**Files:**
- Create: `refit/stages/s00_intake.py`
- Modify: `tests/conftest.py` (append PDF and cover fixtures)
- Test: `tests/test_intake.py`

**Interfaces:**
- Consumes: `ModelClient`, `ModelRequest` (Task 8); `finalize_stage`, `StageOutcome` (Task 6); `STAGE_CHECKS` (Task 9); model entities (Task 2).
- Produces (`refit.stages.s00_intake`): `STAGE = "s00"`, `PROMPT_VERSION = "1"`, `MODEL_COVER_CONFIDENCE = 0.8`, `TRANSCRIBE_SYSTEM: str`, `COVER_INFO_SYSTEM: str`, `DistributionGateError(RuntimeError)`, `distribution_gate(text) -> str` (returns the statement excerpt), `sha256_file(path) -> str`, `fetch_to_cache(uri, cache_root, *, http=None) -> Path`, `cover_text(pdf_path) -> str`, `cover_images(pdf_path, dpi=200) -> tuple[bytes, ...]`, `CoverTranscription(text)`, `CoverInfo(title, tm_number, edition, changes, effectivity, card_part_numbers)`, `read_cover(pdf_path, client) -> tuple[str, str]`, `run_intake(*, card_id, manual_uri, host_system, card_dir, cache_root, client, card_pn=None, card_revision=None, photo_uris=(), http=None) -> StageOutcome`.
- Behavior:
  - The gate runs before anything is written. Model-read cover facts get confidence `0.8`: there is no cross-check at intake, so they go to review by design.
  - Downloaded files are cached under `cache/downloads/`, and `cache_path` is stored relative to `cache_root` for downloads.
  - Photos are sources with `publishable=False`.
  - The AI only transcribes; the regex decides.

- [ ] **Step 1: Add fixtures to `tests/conftest.py`** — put `import fitz  # PyMuPDF` with the other imports at the top of the file, then append:

```python
COVER_TEXT_A = (
    "TECHNICAL MANUAL TM 11-5840-000-34\n"
    "DIRECT SUPPORT MAINTENANCE MANUAL - SERVO AMPLIFIER CARD\n"
    "DISTRIBUTION STATEMENT A: Approved for public release;\n"
    "distribution is unlimited.\n"
    "HEADQUARTERS, DEPARTMENT OF THE ARMY  1 JUNE 1985"
)
COVER_TEXT_C = COVER_TEXT_A.replace(
    "DISTRIBUTION STATEMENT A: Approved for public release;\ndistribution is unlimited.",
    "DISTRIBUTION STATEMENT C: Distribution authorized to U.S. Government agencies and their contractors.",
)
COVER_INFO_REPLY = (
    '{"title": "Servo Amplifier Card", "tm_number": "TM 11-5840-000-34", '
    '"edition": "1 June 1985", "changes": ["C1", "C2"], '
    '"effectivity": "Serial 100 and up", "card_part_numbers": ["SM-C-555123"]}'
)


def make_pdf_file(path, pages):
    """pages: list of page texts; an empty string makes an image-only (scanned-like) page."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text, fontsize=10)
        else:
            page.draw_rect(fitz.Rect(72, 72, 300, 300))
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def make_pdf():
    return make_pdf_file


@pytest.fixture
def cover():
    return SimpleNamespace(text_a=COVER_TEXT_A, text_c=COVER_TEXT_C, info_reply=COVER_INFO_REPLY)
```

- [ ] **Step 2: Write the failing test** — `tests/test_intake.py`

```python
import json

import httpx
import pytest

from refit.models.adapter import ModelClient
from refit.models.cache import ResponseCache
from refit.record.claims import ClaimStatus
from refit.record.snapshots import snapshot_path
from refit.review.queue import open_items
from refit.stages.s00_intake import (
    COVER_INFO_SYSTEM,
    TRANSCRIBE_SYSTEM,
    DistributionGateError,
    distribution_gate,
    fetch_to_cache,
    run_intake,
)


@pytest.mark.parametrize(
    "text",
    [
        "DISTRIBUTION STATEMENT A: Approved for public release; distribution is unlimited.",
        "distribution\nstatement a.  approved for public release",
        "DISTRIBUTION STATEMENT: A",
        "APPROVED FOR PUBLIC RELEASE; DISTRIBUTION IS UNLIMITED",
        "Approved for public release,\ndistribution unlimited",
    ],
)
def test_gate_accepts_distribution_a_variants(text):
    assert distribution_gate(text)


@pytest.mark.parametrize(
    "text, message",
    [
        ("DISTRIBUTION STATEMENT C: U.S. Government agencies only.", "non-A"),
        ("DISTRIBUTION STATEMENT A: public release.\nChange 2 ... DISTRIBUTION STATEMENT D", "non-A"),
        ("TECHNICAL MANUAL TM 11-5840-000-34", "no Distribution A"),
        ("DISTRIBUTION STATEMENT Applies to all users", "no Distribution A"),
    ],
)
def test_gate_rejects_everything_else(text, message):
    with pytest.raises(DistributionGateError, match=message):
        distribution_gate(text)


def workspace(tmp_path):
    ws = tmp_path / "My Projects" / "ws"
    return ws / "cards" / "servo", ws / "cache"


def client_for(provider, cache_root):
    return ModelClient(provider, ResponseCache(cache_root / "models"))


def test_text_layer_manual_builds_baseline_and_review_items(tmp_path, make_pdf, cover, routing_provider):
    card_dir, cache_root = workspace(tmp_path)
    manual = make_pdf(tmp_path / "My Projects" / "tm 11-5840.pdf", [cover.text_a, "page two"])
    provider = routing_provider({COVER_INFO_SYSTEM: cover.info_reply})
    out = run_intake(
        card_id="servo", manual_uri=str(manual), host_system="AN/XXX-1",
        card_dir=card_dir, cache_root=cache_root, client=client_for(provider, cache_root),
        card_revision="C",
    )
    rec = out.record
    assert out.snapshot == snapshot_path(card_dir, "s00")
    assert rec.distribution.method == "text_layer"
    assert "DISTRIBUTION STATEMENT A" in rec.distribution.statement.upper()
    assert rec.title == "Servo Amplifier Card"
    assert rec.sources["manual"].publishable is True and len(rec.sources["manual"].sha256) == 64
    assert rec.config.card_pn.value == "SM-C-555123"
    assert rec.config.card_revision.status is ClaimStatus.ACCEPTED
    assert rec.config.tm_changes.value == ["C1", "C2"]
    assert [call[0] for call in provider.calls] == [COVER_INFO_SYSTEM]
    assert {i.claim_id for i in open_items(rec)} == {
        "config:card_pn", "config:tm_number", "config:tm_edition",
        "config:tm_changes", "config:effectivity", "config:confirmation",
    }


def test_scanned_manual_is_transcribed_then_gated(tmp_path, make_pdf, cover, routing_provider):
    card_dir, cache_root = workspace(tmp_path)
    manual = make_pdf(tmp_path / "scan.pdf", [""])
    transcription = json.dumps({"text": cover.text_a})
    provider = routing_provider({TRANSCRIBE_SYSTEM: transcription, COVER_INFO_SYSTEM: cover.info_reply})
    out = run_intake(
        card_id="servo", manual_uri=str(manual), host_system="AN/XXX-1",
        card_dir=card_dir, cache_root=cache_root, client=client_for(provider, cache_root),
    )
    assert out.record.distribution.method == "model_transcription"
    assert provider.calls[0][0] == TRANSCRIBE_SYSTEM and provider.calls[0][2] == 1
    assert out.record.config.card_revision.value is None  # not given, not on cover -> review


def test_non_a_manual_stops_before_anything_is_written(tmp_path, make_pdf, cover, routing_provider):
    card_dir, cache_root = workspace(tmp_path)
    manual = make_pdf(tmp_path / "tm-c.pdf", [cover.text_c])
    provider = routing_provider({COVER_INFO_SYSTEM: cover.info_reply})
    with pytest.raises(DistributionGateError):
        run_intake(
            card_id="servo", manual_uri=str(manual), host_system="AN/XXX-1",
            card_dir=card_dir, cache_root=cache_root, client=client_for(provider, cache_root),
        )
    assert not snapshot_path(card_dir, "s00").exists()
    assert provider.calls == []


def test_url_sources_are_downloaded_once_and_photos_are_not_publishable(
    tmp_path, make_pdf, cover, routing_provider
):
    card_dir, cache_root = workspace(tmp_path)
    pdf_bytes = make_pdf(tmp_path / "remote.pdf", [cover.text_a]).read_bytes()
    hits = []

    def handler(request):
        hits.append(str(request.url))
        if request.url.path.endswith(".pdf"):
            return httpx.Response(200, content=pdf_bytes)
        return httpx.Response(200, content=b"\xff\xd8photo")

    http = httpx.Client(transport=httpx.MockTransport(handler))
    url = "https://example.org/manuals/tm-11-5840.pdf"
    assert fetch_to_cache(url, cache_root, http=http) == fetch_to_cache(url, cache_root, http=http)
    assert hits == [url]

    provider = routing_provider({COVER_INFO_SYSTEM: cover.info_reply})
    out = run_intake(
        card_id="servo", manual_uri=url, host_system="AN/XXX-1",
        card_dir=card_dir, cache_root=cache_root, client=client_for(provider, cache_root),
        photo_uris=["https://example.org/photos/card.jpg"], http=http,
    )
    photo = out.record.sources["photo1"]
    assert photo.kind == "photo" and photo.publishable is False
    assert out.record.sources["manual"].cache_path.startswith("downloads")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_intake.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'refit.stages.s00_intake'`

- [ ] **Step 4: Write the implementation** — `refit/stages/s00_intake.py`

```python
"""Stage 0 - Intake: fetch sources, enforce Distribution A, build the configuration baseline."""

import hashlib
import re
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

import fitz  # PyMuPDF
import httpx
from pydantic import BaseModel, Field

from refit.models.adapter import ModelClient, ModelRequest
from refit.record.claims import ClaimStatus, Evidence, OptStrClaim, ProducedBy, StrListClaim
from refit.record.model import CardRecord, ConfigurationBaseline, DistributionInfo, Source
from refit.review.finalize import StageOutcome, finalize_stage
from refit.stages.registry import STAGE_CHECKS

STAGE = "s00"
PROMPT_VERSION = "1"
COVER_PAGES = 3
MIN_TEXT_LAYER_CHARS = 40
MODEL_COVER_CONFIDENCE = 0.8  # no cross-check exists at intake, so cover facts go to review

TRANSCRIBE_SYSTEM = (
    "You transcribe scanned pages of military technical manuals. Copy the text exactly "
    "as printed, including any distribution statement, word for word. Never add, infer "
    "or correct text."
)
COVER_INFO_SYSTEM = (
    "You extract configuration identity from the cover and title pages of a military "
    "technical manual: manual number, title, edition date, change numbers, effectivity "
    "(which serial numbers or models it covers) and circuit card assembly part numbers. "
    "Use null or an empty list when a field is not printed. Never guess."
)

_STATEMENT_RE = re.compile(r"DISTRIBUTION\s+STATEMENT\s*[:\-]?\s*([A-F])\b", re.IGNORECASE)
_PUBLIC_RE = re.compile(
    r"APPROVED\s+FOR\s+PUBLIC\s+RELEASE\s*[;:,.]?\s*DISTRIBUTION\s+(?:IS\s+)?UNLIMITED",
    re.IGNORECASE,
)


class DistributionGateError(RuntimeError):
    pass


class CoverTranscription(BaseModel):
    text: str


class CoverInfo(BaseModel):
    title: str | None = None
    tm_number: str | None = None
    edition: str | None = None
    changes: list[str] = Field(default_factory=list)
    effectivity: str | None = None
    card_part_numbers: list[str] = Field(default_factory=list)


def distribution_gate(text: str) -> str:
    """Return the Distribution A statement excerpt, or raise. Fails closed."""
    flat = " ".join(text.split())
    letters = {m.group(1).upper() for m in _STATEMENT_RE.finditer(flat)}
    non_a = sorted(letters - {"A"})
    if non_a:
        raise DistributionGateError(
            f"document carries non-A distribution statement(s): {', '.join(non_a)}; "
            "REFIT only processes Distribution A"
        )
    match = _STATEMENT_RE.search(flat) or _PUBLIC_RE.search(flat)
    if match is None:
        raise DistributionGateError(
            "no Distribution A statement found on the cover pages; REFIT only processes Distribution A"
        )
    return flat[match.start() : match.end() + 80].strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_to_cache(uri: str, cache_root: Path, *, http: httpx.Client | None = None) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme in ("http", "https"):
        suffix = Path(parsed.path).suffix or ".bin"
        target = cache_root / "downloads" / (hashlib.sha256(uri.encode("utf-8")).hexdigest()[:16] + suffix)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            client = http or httpx.Client(follow_redirects=True, timeout=60)
            try:
                response = client.get(uri)
                response.raise_for_status()
            finally:
                if http is None:
                    client.close()
            target.write_bytes(response.content)
        return target
    path = Path(uri)
    if not path.is_file():
        raise FileNotFoundError(f"source not found: {uri}")
    return path


def _cache_path(path: Path, cache_root: Path) -> str:
    try:
        return path.relative_to(cache_root).as_posix()
    except ValueError:
        return str(path)


def cover_text(pdf_path: Path) -> str:
    with fitz.open(str(pdf_path)) as doc:
        return "\n".join(doc[i].get_text() for i in range(min(COVER_PAGES, doc.page_count)))


def cover_images(pdf_path: Path, dpi: int = 200) -> tuple[bytes, ...]:
    with fitz.open(str(pdf_path)) as doc:
        return tuple(
            doc[i].get_pixmap(dpi=dpi).tobytes("png")
            for i in range(min(COVER_PAGES, doc.page_count))
        )


def read_cover(pdf_path: Path, client: ModelClient) -> tuple[str, str]:
    text = cover_text(pdf_path)
    if len(text.strip()) >= MIN_TEXT_LAYER_CHARS:
        return text, "text_layer"
    reply = client.ask(
        ModelRequest(
            stage=STAGE,
            prompt_id="cover_transcribe",
            prompt_version=PROMPT_VERSION,
            system=TRANSCRIBE_SYSTEM,
            prompt="Transcribe every page image exactly, in order.",
            images=cover_images(pdf_path),
        ),
        CoverTranscription,
    )
    return reply.text, "model_transcription"


def _baseline(
    info: CoverInfo, host_system: str, card_pn: str | None, card_revision: str | None
) -> ConfigurationBaseline:
    human = ProducedBy(kind="human", stage=STAGE, detail="intake arguments")
    model = ProducedBy(kind="model", stage=STAGE, detail=f"cover_info:v{PROMPT_VERSION}")
    cover = [Evidence(source_id="manual", method="cover_read", page=1)]

    def given(field: str, value: str | None) -> OptStrClaim:
        return OptStrClaim(
            id=f"config:{field}", value=value, confidence=1.0,
            produced_by=human, status=ClaimStatus.ACCEPTED,
        )

    def read(field: str, value: str | None) -> OptStrClaim:
        return OptStrClaim(
            id=f"config:{field}", value=value, confidence=MODEL_COVER_CONFIDENCE,
            produced_by=model, evidence=cover,
        )

    single_pn = info.card_part_numbers[0] if len(info.card_part_numbers) == 1 else None
    return ConfigurationBaseline(
        card_pn=given("card_pn", card_pn) if card_pn else read("card_pn", single_pn),
        card_revision=given("card_revision", card_revision) if card_revision else read("card_revision", None),
        tm_number=read("tm_number", info.tm_number),
        tm_edition=read("tm_edition", info.edition),
        tm_changes=StrListClaim(
            id="config:tm_changes", value=info.changes, confidence=MODEL_COVER_CONFIDENCE,
            produced_by=model, evidence=cover,
        ),
        effectivity=read("effectivity", info.effectivity),
        field_changes=StrListClaim(
            id="config:field_changes", value=[], confidence=1.0,
            produced_by=human, status=ClaimStatus.ACCEPTED,
        ),
        host_system=given("host_system", host_system),
        confirmation=OptStrClaim(
            id="config:confirmation", value=None, confidence=1.0,
            produced_by=ProducedBy(kind="deterministic", stage=STAGE),
        ),
    )


def run_intake(
    *,
    card_id: str,
    manual_uri: str,
    host_system: str,
    card_dir: Path,
    cache_root: Path,
    client: ModelClient,
    card_pn: str | None = None,
    card_revision: str | None = None,
    photo_uris: Sequence[str] = (),
    http: httpx.Client | None = None,
) -> StageOutcome:
    manual_path = fetch_to_cache(manual_uri, cache_root, http=http)
    text, method = read_cover(manual_path, client)
    statement = distribution_gate(text)  # hard stop before anything is written

    sources = {
        "manual": Source(
            id="manual", kind="manual", uri=manual_uri, sha256=sha256_file(manual_path),
            publishable=True, cache_path=_cache_path(manual_path, cache_root), distribution="A",
        )
    }
    for n, uri in enumerate(photo_uris, start=1):
        photo_path = fetch_to_cache(uri, cache_root, http=http)
        sources[f"photo{n}"] = Source(
            id=f"photo{n}", kind="photo", uri=uri, sha256=sha256_file(photo_path),
            publishable=False, cache_path=_cache_path(photo_path, cache_root),
        )

    info = client.ask(
        ModelRequest(
            stage=STAGE,
            prompt_id="cover_info",
            prompt_version=PROMPT_VERSION,
            system=COVER_INFO_SYSTEM,
            prompt=f"Cover and title pages of the technical manual:\n\n{text}",
        ),
        CoverInfo,
    )
    record = CardRecord(
        card_id=card_id,
        title=info.title or "",
        distribution=DistributionInfo(letter="A", statement=statement, source_id="manual", method=method),
        sources=sources,
        config=_baseline(info, host_system, card_pn, card_revision),
    )
    return finalize_stage(record, card_dir, STAGE, STAGE_CHECKS[STAGE])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_intake.py -v`
Expected: 13 passed

- [ ] **Step 6: Commit**

```bash
git add refit/stages/s00_intake.py tests/conftest.py tests/test_intake.py
git commit -m "feat: stage 0 intake with Distribution A gate" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Command-line interface

**Files:**
- Create: `refit/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above. `run_intake`, `DistributionGateError`; `latest_snapshot`, `export_json_schema`; `finalize_stage`; `open_items`, `resolve_item`, `accept_item`, `ReviewError`; `add_override`, `Override`, `OverrideValueError`; `confirm_configuration`, `ConfigurationNotConfirmed`; `compute_metrics`, `load_reference`; `default_client`, `ReplayMiss`, `ModelOutputError`, `ModelRefusal`; `STAGE_CHECKS`.
- Produces: `refit.cli.main(argv: list[str] | None = None) -> int` (0 = ok, 2 = expected error printed as `error: ...` on stderr), `refit.cli.make_client(cache_root: Path, replay: bool) -> ModelClient` (tests monkeypatch this). Subcommands, all taking `--workspace DIR` (default `.`; card dir `<ws>/cards/<card_id>`, cache `<ws>/cache`):
  - `intake CARD_ID --manual URI --host-system TEXT [--card-pn PN] [--card-rev REV] [--photo URI]... [--replay]`
  - `review CARD_ID`
  - `resolve CARD_ID ITEM_ID --value V --by NAME [--note TEXT]`
  - `accept CARD_ID ITEM_ID --by NAME`
  - `override CARD_ID CLAIM_ID --value V --by NAME [--note TEXT]`
  - `confirm-config CARD_ID --by NAME`
  - `metrics CARD_ID --reference PATH`
  - `schema OUT_PATH`
- `--value` parsing: a value starting with `[` or `{`, or exactly `null`, is parsed as JSON; everything else is kept as a string, so `100` stays the string `"100"`. After `resolve`, `accept`, `override` and `confirm-config`, the latest snapshot is re-finalized, and orphaned overrides are printed as warnings.

- [ ] **Step 1: Write the failing test** — `tests/test_cli.py`

```python
import json
from types import SimpleNamespace

import pytest

from refit import cli
from refit.models.adapter import ModelClient
from refit.models.cache import ResponseCache
from refit.stages.s00_intake import COVER_INFO_SYSTEM


@pytest.fixture
def env(tmp_path, monkeypatch, make_pdf, cover, routing_provider):
    ws = tmp_path / "My Projects" / "workspace"
    ws.mkdir(parents=True)
    manual_a = make_pdf(ws / "tm 11-5840 A.pdf", [cover.text_a])
    manual_c = make_pdf(ws / "tm 11-5840 C.pdf", [cover.text_c])
    provider = routing_provider({COVER_INFO_SYSTEM: cover.info_reply})
    monkeypatch.setattr(
        cli, "make_client",
        lambda cache_root, replay: ModelClient(provider, ResponseCache(cache_root / "models"), replay_only=replay),
    )
    return SimpleNamespace(ws=ws, manual_a=manual_a, manual_c=manual_c)


def run(env, *args):
    return cli.main([*args, "--workspace", str(env.ws)])


def intake(env):
    return run(
        env, "intake", "servo", "--manual", str(env.manual_a), "--host-system", "AN/XXX-1",
        "--card-pn", "SM-C-555123", "--card-rev", "C",
    )


CONFIG_ITEMS = ["rv:config:tm_number", "rv:config:tm_edition", "rv:config:tm_changes", "rv:config:effectivity"]


def test_intake_then_review(env, capsys):
    assert intake(env) == 0
    out = capsys.readouterr().out
    assert "DISTRIBUTION STATEMENT A" in out.upper() and "open review items: 5" in out
    assert (env.ws / "cards" / "servo" / "card.s00.json").exists()
    assert run(env, "review", "servo") == 0
    out = capsys.readouterr().out
    for item in CONFIG_ITEMS + ["rv:config:confirmation"]:
        assert item in out


def test_non_a_manual_exits_2(env, capsys):
    code = run(env, "intake", "servo", "--manual", str(env.manual_c), "--host-system", "AN/XXX-1")
    assert code == 2
    assert "non-A" in capsys.readouterr().err


def test_confirm_requires_resolving_config_items_first(env, capsys):
    intake(env)
    assert run(env, "confirm-config", "servo", "--by", "mh") == 2
    assert "resolve these configuration items first" in capsys.readouterr().err
    for item in CONFIG_ITEMS:
        assert run(env, "accept", "servo", item, "--by", "mh") == 0
    assert run(env, "confirm-config", "servo", "--by", "mh") == 0
    capsys.readouterr()
    assert run(env, "review", "servo") == 0
    assert "no open review items" in capsys.readouterr().out


def test_resolve_keeps_numbers_as_strings(env):
    intake(env)
    assert run(env, "resolve", "servo", "rv:config:tm_edition", "--value", "1985", "--by", "mh") == 0
    snap = json.loads((env.ws / "cards" / "servo" / "card.s00.json").read_text(encoding="utf-8"))
    assert snap["config"]["tm_edition"]["value"] == "1985"


def test_override_unknown_claim_warns_orphan(env, capsys):
    intake(env)
    capsys.readouterr()
    assert run(env, "override", "servo", "part:R99:value", "--value", "1k", "--by", "mh") == 0
    assert "part:R99:value" in capsys.readouterr().err


def test_metrics_and_schema(env, capsys, tmp_path):
    intake(env)
    reference = env.ws / "reference.json"
    reference.write_text('{"values": {"part:R1:value": "10k"}}', encoding="utf-8")
    capsys.readouterr()
    assert run(env, "metrics", "servo", "--reference", str(reference)) == 0
    out = capsys.readouterr().out
    assert "part" in out and "conn" in out and "n/a" in out
    schema_path = env.ws / "schema" / "card-record.schema.json"
    assert cli.main(["schema", str(schema_path)]) == 0
    assert json.loads(schema_path.read_text(encoding="utf-8"))["title"] == "CardRecord"


def test_review_before_intake_exits_2(env, capsys):
    assert run(env, "review", "servo") == 2
    assert "run `refit intake` first" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'cli' from 'refit'`

- [ ] **Step 3: Write the implementation** — `refit/cli.py`

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 7 passed

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: all tests pass, with no network access and no API key.

- [ ] **Step 6: Commit**

```bash
git add refit/cli.py tests/test_cli.py
git commit -m "feat: refit command line" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Out of scope for this plan (later milestones)

- Stages 1–9 beyond intake: page triage, parts list, schematic extraction, photo evidence, blocks, obsolescence, substitution, equivalence and export. Each gets its own plan and registers its checks in `refit/stages/registry.py`.
- `require_confirmed` is built and tested here; Stage 9 export (Milestone 6) is where it gets called.
- Installing ngspice and Icarus Verilog (Milestone 5).
- A live-model smoke run of intake against a real Distribution A manual. That happens with Milestone 1's chosen card; it needs `ANTHROPIC_API_KEY` or `ant auth login`.
