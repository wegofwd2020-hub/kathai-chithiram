"""GeminiProvider: builds the google-genai call, JSON mode on schema, maps text out."""

from __future__ import annotations

from typing import Any

import pytest

from kathai_chithiram.errors import ProviderResponseError
from kathai_chithiram.wegofwd_llm.gemini_provider import GeminiProvider
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, ProviderConfig

_CFG = ProviderConfig(provider_id="gemini:test", no_training=False, zero_retention=False)


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[dict[str, Any]] = []

    def generate_content(
        self, *, model: str, contents: str, config: dict[str, Any]
    ) -> _FakeResponse:
        self.calls.append({"model": model, "contents": contents, "config": config})
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text: str = '{"ok": true}') -> None:
        self.models = _FakeModels(text)


def _req(**over: Any) -> LLMRequest:
    base: dict[str, Any] = dict(prompt="hello", config=_CFG, system_prompt="", output_schema=None)
    base.update(over)
    return LLMRequest(**base)


def test_completes_and_returns_text() -> None:
    client = _FakeClient(text='{"scene": 1}')
    provider = GeminiProvider(client=client, model="gemini-x")
    assert provider.complete(_req()).text == '{"scene": 1}'
    call = client.models.calls[0]
    assert call["model"] == "gemini-x"
    assert call["contents"] == "hello"


def test_json_mode_set_when_schema_present() -> None:
    client = _FakeClient()
    provider = GeminiProvider(client=client, model="gemini-x")
    provider.complete(_req(output_schema={"type": "object"}))
    assert client.models.calls[0]["config"]["response_mime_type"] == "application/json"


def test_system_instruction_passed_when_present() -> None:
    client = _FakeClient()
    provider = GeminiProvider(client=client, model="gemini-x")
    provider.complete(_req(system_prompt="be calm"))
    assert client.models.calls[0]["config"]["system_instruction"] == "be calm"


def test_empty_reply_raises() -> None:
    provider = GeminiProvider(client=_FakeClient(text="   "), model="gemini-x")
    with pytest.raises(ProviderResponseError):
        provider.complete(_req())
