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
