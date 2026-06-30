"""Tests for the concrete AnthropicProvider.

Exercised with a fake client (no SDK, no network): the adapter must build a
correct streaming Messages call, return the assembled text, and turn a safety
refusal or an empty reply into a domain error rather than silent output. Also
checks that constructing it without the SDK fails loudly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

import kathai_chithiram.wegofwd_llm.anthropic_provider as provider_mod
from kathai_chithiram.errors import ProviderResponseError, ProviderUnavailableError
from kathai_chithiram.wegofwd_llm.anthropic_provider import AnthropicProvider
from kathai_chithiram.wegofwd_llm.provider import LLMProvider, LLMRequest, ProviderConfig

CONFIG = ProviderConfig(provider_id="anthropic:no-train-zdr", no_training=True, zero_retention=True)


@dataclass
class FakeBlock:
    type: str
    text: str = ""


@dataclass
class FakeMessage:
    content: list[FakeBlock]
    stop_reason: str = "end_turn"


@dataclass
class _FakeStream:
    message: FakeMessage

    def __enter__(self) -> _FakeStream:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get_final_message(self) -> FakeMessage:
        return self.message


@dataclass
class _FakeMessages:
    message: FakeMessage
    calls: list[dict[str, Any]] = field(default_factory=list)

    def stream(self, **kwargs: Any) -> _FakeStream:
        self.calls.append(kwargs)
        return _FakeStream(self.message)


@dataclass
class FakeClient:
    """A stand-in for ``anthropic.Anthropic`` exposing only ``messages.stream``."""

    message: FakeMessage

    def __post_init__(self) -> None:
        self.messages = _FakeMessages(self.message)


def _request(system: str = "RULES") -> LLMRequest:
    return LLMRequest(prompt="CHILD brushes teeth.", config=CONFIG, system_prompt=system)


def test_returns_assembled_text_and_builds_streaming_call() -> None:
    client = FakeClient(
        FakeMessage(content=[FakeBlock("text", "scene "), FakeBlock("text", "script")])
    )
    provider = AnthropicProvider(model="claude-opus-4-8", client=client)

    response = provider.complete(_request())

    assert response.text == "scene script"
    (call,) = client.messages.calls
    assert call["model"] == "claude-opus-4-8"
    assert call["max_tokens"] == 16000
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "high"}
    assert call["messages"] == [{"role": "user", "content": "CHILD brushes teeth."}]
    assert call["system"] == "RULES"


def test_empty_system_prompt_is_omitted() -> None:
    client = FakeClient(FakeMessage(content=[FakeBlock("text", "ok")]))
    AnthropicProvider(client=client).complete(_request(system=""))
    assert "system" not in client.messages.calls[0]


def test_non_text_blocks_are_ignored() -> None:
    client = FakeClient(
        FakeMessage(content=[FakeBlock("thinking", "hmm"), FakeBlock("text", "answer")])
    )
    assert AnthropicProvider(client=client).complete(_request()).text == "answer"


def test_refusal_raises_provider_response_error() -> None:
    client = FakeClient(FakeMessage(content=[], stop_reason="refusal"))
    with pytest.raises(ProviderResponseError, match="refusal"):
        AnthropicProvider(client=client).complete(_request())


def test_empty_reply_raises_provider_response_error() -> None:
    client = FakeClient(FakeMessage(content=[FakeBlock("text", "   ")]))
    with pytest.raises(ProviderResponseError, match="no text"):
        AnthropicProvider(client=client).complete(_request())


def test_satisfies_llm_provider_protocol() -> None:
    client = FakeClient(FakeMessage(content=[FakeBlock("text", "ok")]))
    assert isinstance(AnthropicProvider(client=client), LLMProvider)


def test_missing_sdk_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate the SDK being absent (no client injected, import fails).
    def _boom() -> object:
        raise ImportError("no module named 'anthropic'")

    monkeypatch.setattr(provider_mod, "_load_anthropic_module", _boom)
    with pytest.raises(ProviderUnavailableError, match="anthropic"):
        AnthropicProvider()
