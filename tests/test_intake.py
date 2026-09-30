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
