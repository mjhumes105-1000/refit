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
