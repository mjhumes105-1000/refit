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
