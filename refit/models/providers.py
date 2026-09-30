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
