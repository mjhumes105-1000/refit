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
