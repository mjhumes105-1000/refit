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
