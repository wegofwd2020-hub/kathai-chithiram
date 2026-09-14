"""GeminiProvider — a concrete LLMProvider backed by Google's google-genai SDK.

Non-goal by construction: this provider does NOT assert a privacy posture. Whether a
request may carry real story text is decided by the ``ProviderConfig`` the caller
builds and enforced at the gateway (PRIVACY.md §6). The AI Studio free tier is not a
no-training / zero-retention endpoint, so callers give it a non-compliant config and it
runs only under the gateway's explicit synthetic-data escape.
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
    "DEFAULT_GEMINI_MODEL",
    "GEMINI_API_KEY_ENV",
    "GeminiProvider",
    "build_gemini_provider",
]

#: Default model; overridable. Model ids move fast — verify against the installed SDK.
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"


def _load_genai() -> Any:
    """Import the optional ``google-genai`` SDK, or raise ``ImportError`` if absent."""
    return importlib.import_module("google.genai")


class GeminiProvider:
    """Generate completions with a Gemini model via the google-genai SDK.

    Args:
        model: The Gemini model id.
        client: An injected google-genai client (tests supply a fake); when ``None``
            the SDK client is constructed from ``api_key``.
        api_key: The Gemini API key (AI Studio). Required when ``client`` is ``None``.

    Raises:
        ProviderUnavailableError: If the ``google-genai`` SDK is not installed.
    """

    def __init__(self, *, model: str = DEFAULT_GEMINI_MODEL, client: Any | None = None,
                 api_key: str | None = None) -> None:
        if client is None:
            try:
                genai = _load_genai()
            except ImportError as exc:
                raise ProviderUnavailableError(
                    f"gemini:{model}",
                    "the 'google-genai' SDK is not installed; install it with: "
                    "pip install 'kathai-chithiram[gemini]'",
                ) from exc
            client = genai.Client(api_key=api_key)
        self._client = client
        self._model = model

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Send ``request`` to Gemini and return its text reply.

        Args:
            request: The outbound request (prompt already pseudonymised by the gateway).

        Returns:
            The model's :class:`LLMResponse`.

        Raises:
            ProviderResponseError: If the model returns no usable text.
        """
        config: dict[str, Any] = {}
        if request.system_prompt:
            config["system_instruction"] = request.system_prompt
        if request.output_schema is not None:
            # JSON mode (KC-12 partial constraint): "return JSON". The scene-script
            # schema still reaches the model via the prompt; the validate-and-repair
            # loop is the correctness guarantee.
            config["response_mime_type"] = "application/json"
        response = self._client.models.generate_content(
            model=self._model, contents=request.prompt, config=config
        )
        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise ProviderResponseError(self._model, "the model returned no text content")
        return LLMResponse(text=text)


def build_gemini_provider(
    *, model: str = DEFAULT_GEMINI_MODEL, env: Mapping[str, str] | None = None
) -> GeminiProvider:
    """Build a GeminiProvider from ``GEMINI_API_KEY``; fails closed if the key is absent.

    Args:
        model: The Gemini model id.
        env: Environment mapping (defaults to ``os.environ``).

    Returns:
        A configured :class:`GeminiProvider`.

    Raises:
        ProviderConfigError: If ``GEMINI_API_KEY`` is not set.
    """
    source = os.environ if env is None else env
    key = source.get(GEMINI_API_KEY_ENV)
    if not key:
        raise ProviderConfigError(
            f"gemini:{model}",
            f"{GEMINI_API_KEY_ENV} is not set; cannot construct the Gemini provider",
        )
    return GeminiProvider(model=model, api_key=key)
