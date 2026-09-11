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


def test_cacheable_prefix_becomes_two_system_blocks() -> None:
    # A repair attempt: system_prompt is prefix + volatile remainder. The prefix
    # is emitted as a cache-marked block; the remainder as a plain block.
    client = FakeClient(FakeMessage(content=[FakeBlock("text", "ok")]))
    req = LLMRequest(
        prompt="CHILD brushes teeth.",
        config=CONFIG,
        system_prompt="RULESfeedback",
        system_prefix="RULES",
    )
    AnthropicProvider(client=client).complete(req)
    assert client.messages.calls[0]["system"] == [
        {"type": "text", "text": "RULES", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "feedback"},
    ]


def test_prefix_equal_to_whole_system_is_one_cached_block() -> None:
    # First attempt: system_prompt == system_prefix, so there is no remainder.
    client = FakeClient(FakeMessage(content=[FakeBlock("text", "ok")]))
    req = LLMRequest(prompt="p", config=CONFIG, system_prompt="RULES", system_prefix="RULES")
    AnthropicProvider(client=client).complete(req)
    assert client.messages.calls[0]["system"] == [
        {"type": "text", "text": "RULES", "cache_control": {"type": "ephemeral"}},
    ]


def test_prefix_ignored_when_not_a_prefix_of_system() -> None:
    # Defensive: if system_prefix isn't actually a leading substring, send the
    # whole system as a plain string rather than risk mangling it.
    client = FakeClient(FakeMessage(content=[FakeBlock("text", "ok")]))
    req = LLMRequest(prompt="p", config=CONFIG, system_prompt="RULES", system_prefix="XYZ")
    AnthropicProvider(client=client).complete(req)
    assert client.messages.calls[0]["system"] == "RULES"


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


# --- ZDR / no-training credential (KC-6) ----------------------------------------


def test_build_zdr_provider_fails_closed_without_key() -> None:
    from kathai_chithiram.errors import ProviderConfigError
    from kathai_chithiram.wegofwd_llm.anthropic_provider import build_zdr_provider

    with pytest.raises(ProviderConfigError, match="ANTHROPIC_ZDR_API_KEY"):
        build_zdr_provider(env={})


def test_build_zdr_provider_uses_the_dedicated_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from kathai_chithiram.wegofwd_llm.anthropic_provider import (
        ZDR_API_KEY_ENV,
        build_zdr_provider,
    )

    built_with: list[dict[str, Any]] = []

    class _FakeModule:
        def Anthropic(self, **kwargs: Any) -> FakeClient:
            built_with.append(kwargs)
            return FakeClient(FakeMessage(content=[FakeBlock("text", "ok")]))

    monkeypatch.setattr(provider_mod, "_load_anthropic_module", lambda: _FakeModule())
    # An ambient general key must NOT be the one used.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ambient-should-not-be-used")

    provider = build_zdr_provider(env={ZDR_API_KEY_ENV: "sk-zdr-dedicated"})

    assert isinstance(provider, AnthropicProvider)
    assert built_with == [{"api_key": "sk-zdr-dedicated"}]


def test_build_zdr_provider_missing_sdk_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kathai_chithiram.wegofwd_llm.anthropic_provider import (
        ZDR_API_KEY_ENV,
        build_zdr_provider,
    )

    def _boom() -> object:
        raise ImportError("no module named 'anthropic'")

    monkeypatch.setattr(provider_mod, "_load_anthropic_module", _boom)
    with pytest.raises(ProviderUnavailableError, match="anthropic"):
        build_zdr_provider(env={ZDR_API_KEY_ENV: "sk-zdr"})


# --- Structured outputs (KC-12) ------------------------------------------------


def test_output_schema_sets_json_schema_format_with_effort() -> None:
    client = FakeClient(FakeMessage(content=[FakeBlock("text", "{}")]))
    schema = {"type": "object", "additionalProperties": False}
    req = LLMRequest(prompt="p", config=CONFIG, system_prompt="RULES", output_schema=schema)
    AnthropicProvider(client=client, effort="high").complete(req)
    assert client.messages.calls[0]["output_config"] == {
        "effort": "high",
        "format": {"type": "json_schema", "schema": schema},
    }


def test_no_output_schema_sends_no_format_key() -> None:
    client = FakeClient(FakeMessage(content=[FakeBlock("text", "ok")]))
    AnthropicProvider(client=client).complete(_request())
    assert client.messages.calls[0]["output_config"] == {"effort": "high"}
    assert "format" not in client.messages.calls[0]["output_config"]


def test_refusal_still_raises_on_structured_path() -> None:
    client = FakeClient(FakeMessage(content=[], stop_reason="refusal"))
    schema = {"type": "object", "additionalProperties": False}
    req = LLMRequest(prompt="p", config=CONFIG, output_schema=schema)
    with pytest.raises(ProviderResponseError, match="refusal"):
        AnthropicProvider(client=client).complete(req)
