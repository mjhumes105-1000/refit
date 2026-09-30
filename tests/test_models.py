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
