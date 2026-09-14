"""QwenProvider — a concrete LLMProvider backed by an OpenAI-compatible Qwen endpoint.

Uses the ``openai`` SDK pointed at a Qwen-hosting base URL (e.g. DashScope's
OpenAI-compatible mode). Like every provider, it asserts no privacy posture of its own:
the gateway decides, from the caller's ``ProviderConfig``, whether real story text may
flow (a hosted Qwen API is treated non-compliant until its terms are verified).
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Mapping
from typing import Any

from kathai_chithiram.errors import (
    ProviderConfigError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, LLMResponse

__all__ = [
    "DEFAULT_QWEN_MODEL",
    "QWEN_API_KEY_ENV",
    "QWEN_BASE_URL_ENV",
    "QwenProvider",
    "build_qwen_provider",
]

DEFAULT_QWEN_MODEL = "qwen-plus"
QWEN_API_KEY_ENV = "QWEN_API_KEY"
QWEN_BASE_URL_ENV = "QWEN_BASE_URL"


def _load_openai() -> Any:
    """Import the optional ``openai`` SDK, or raise ``ImportError`` if absent."""
    return importlib.import_module("openai")


class QwenProvider:
    """Generate completions with a Qwen model via an OpenAI-compatible endpoint.

    Args:
        model: The Qwen model id.
        client: An injected OpenAI-compatible client (tests supply a fake); when
            ``None`` a client is built from ``api_key`` and ``base_url``.
        api_key: The API key for the Qwen host. Required when ``client`` is ``None``.
        base_url: The OpenAI-compatible base URL. Required when ``client`` is ``None``.

    Raises:
        ProviderUnavailableError: If the ``openai`` SDK is not installed.
    """

    def __init__(self, *, model: str = DEFAULT_QWEN_MODEL, client: Any | None = None,
                 api_key: str | None = None, base_url: str | None = None) -> None:
        if client is None:
            try:
                openai = _load_openai()
            except ImportError as exc:
                raise ProviderUnavailableError(
                    f"qwen:{model}",
                    "the 'openai' SDK is not installed; install it with: "
                    "pip install 'kathai-chithiram[qwen]'",
                ) from exc
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._client = client
        self._model = model

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Send ``request`` to the Qwen endpoint and return its text reply.

        Args:
            request: The outbound request (prompt already pseudonymised by the gateway).

        Returns:
            The model's :class:`LLMResponse`.

        Raises:
            ProviderResponseError: If the model returns no usable text.
        """
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        kwargs: dict[str, Any] = {"model": self._model, "messages": messages}
        if request.output_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
        completion = self._client.chat.completions.create(**kwargs)
        text = (completion.choices[0].message.content or "") if completion.choices else ""
        if not text.strip():
            raise ProviderResponseError(self._model, "the model returned no text content")
        return LLMResponse(text=text)


def build_qwen_provider(
    *, model: str = DEFAULT_QWEN_MODEL, base_url: str | None = None,
    env: Mapping[str, str] | None = None
) -> QwenProvider:
    """Build a QwenProvider from ``QWEN_API_KEY`` + base URL; fails closed if absent.

    Args:
        model: The Qwen model id.
        base_url: Override for the OpenAI-compatible base URL (else ``QWEN_BASE_URL``).
        env: Environment mapping (defaults to ``os.environ``).

    Returns:
        A configured :class:`QwenProvider`.

    Raises:
        ProviderConfigError: If the API key or base URL is missing.
    """
    source = os.environ if env is None else env
    key = source.get(QWEN_API_KEY_ENV)
    url = base_url or source.get(QWEN_BASE_URL_ENV)
    if not key:
        raise ProviderConfigError(f"qwen:{model}", f"{QWEN_API_KEY_ENV} is not set")
    if not url:
        raise ProviderConfigError(
            f"qwen:{model}", f"{QWEN_BASE_URL_ENV} is not set (OpenAI-compatible endpoint)"
        )
    return QwenProvider(model=model, api_key=key, base_url=url)
