"""QwenProvider: OpenAI-compatible chat.completions, JSON mode on schema, maps text out."""

from __future__ import annotations

from typing import Any

import pytest

from kathai_chithiram.errors import ProviderResponseError
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, ProviderConfig
from kathai_chithiram.wegofwd_llm.qwen_provider import QwenProvider

_CFG = ProviderConfig(provider_id="qwen:test", no_training=False, zero_retention=False)


class _Msg:
    def __init__(self, content: str) -> None:
        self.message = type("M", (), {"content": content})()


class _Completion:
    def __init__(self, content: str) -> None:
        self.choices = [_Msg(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Completion:
        self.calls.append(kwargs)
        return _Completion(self._content)


class _FakeClient:
    def __init__(self, content: str = '{"ok": true}') -> None:
        self.chat = type("C", (), {"completions": _FakeCompletions(content)})()


def _req(**over: Any) -> LLMRequest:
    base: dict[str, Any] = dict(prompt="hello", config=_CFG, system_prompt="", output_schema=None)
    base.update(over)
    return LLMRequest(**base)


def test_completes_and_returns_text() -> None:
    client = _FakeClient(content='{"scene": 1}')
    provider = QwenProvider(client=client, model="qwen-x")
    assert provider.complete(_req()).text == '{"scene": 1}'
    call = client.chat.completions.calls[0]
    assert call["model"] == "qwen-x"
    assert call["messages"][-1] == {"role": "user", "content": "hello"}


def test_system_message_added_when_present() -> None:
    client = _FakeClient()
    provider = QwenProvider(client=client, model="qwen-x")
    provider.complete(_req(system_prompt="be calm"))
    msg = client.chat.completions.calls[0]["messages"][0]
    assert msg == {"role": "system", "content": "be calm"}


def test_json_mode_set_when_schema_present() -> None:
    client = _FakeClient()
    provider = QwenProvider(client=client, model="qwen-x")
    provider.complete(_req(output_schema={"type": "object"}))
    assert client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}


def test_empty_reply_raises() -> None:
    provider = QwenProvider(client=_FakeClient(content="  "), model="qwen-x")
    with pytest.raises(ProviderResponseError):
        provider.complete(_req())
