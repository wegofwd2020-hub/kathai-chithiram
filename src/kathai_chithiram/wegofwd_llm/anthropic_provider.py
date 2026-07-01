"""A concrete :class:`LLMProvider` backed by the Anthropic API.

This is the first real provider behind the otherwise provider-agnostic
``wegofwd-llm`` seam. It lives apart from the seam's core types so importing the
package never requires the ``anthropic`` SDK; install it with the optional
extra::

    pip install 'kathai-chithiram[generation]'

The provider is a thin text-in/text-out adapter: the seam has already
pseudonymized the prompt and verified the privacy posture, so this only turns a
:class:`LLMRequest` into a Messages API call and returns the reply text. The
contract-shaping and validation live in
:mod:`kathai_chithiram.generation.generator`, not here.

Defaults follow current best practice for building on Claude: model
``claude-opus-4-8``, adaptive thinking, and streaming (so a large generation
cannot trip an HTTP read timeout). A safety *refusal* or an empty reply is a
domain error, not silently-empty output.

Zero data retention / no-training (KC-6, PRIVACY.md §6): Anthropic's
no-training + zero-data-retention posture is an **organization-level**
configuration of the account a key belongs to, not a per-request header — the
Messages API exposes no ZDR/no-train flag to set on a call. The enforcement
surface is therefore the *credential*: story text about a child may only be sent
with a key provisioned against a ZDR / no-training org. This module reads that
key from a **dedicated, isolated** environment variable
(:data:`ZDR_API_KEY_ENV`), distinct from any ambient developer key, and
:func:`build_zdr_provider` fails closed if it is absent rather than silently
falling back to a non-ZDR key.
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

__all__ = ["DEFAULT_MODEL", "ZDR_API_KEY_ENV", "AnthropicProvider", "build_zdr_provider"]

#: The default model. Latest, most capable Opus-tier model (CLAUDE.md: default
#: to the latest Claude models when building AI applications).
DEFAULT_MODEL = "claude-opus-4-8"

#: Environment variable holding the dedicated no-training / zero-retention API
#: key. Deliberately distinct from ``ANTHROPIC_API_KEY`` so a general developer
#: key can never be used to send a child's story text (KC-6, PRIVACY.md §6).
ZDR_API_KEY_ENV = "ANTHROPIC_ZDR_API_KEY"


def _load_anthropic_module() -> Any:
    """Import the optional ``anthropic`` SDK, or raise ``ImportError`` if absent.

    Indirected through a helper so construction can convert the absence into a
    domain error, and so tests can simulate a missing SDK without uninstalling.
    """
    return importlib.import_module("anthropic")


class AnthropicProvider:
    """An :class:`LLMProvider` that completes requests via the Anthropic API.

    Args:
        model: The Claude model id. Defaults to :data:`DEFAULT_MODEL`.
        client: A pre-built Anthropic client. Injectable for tests; when
            ``None`` a default ``anthropic.Anthropic(api_key=...)`` is
            constructed.
        api_key: The API key for the constructed client. For production use pass
            the dedicated ZDR / no-training key (see :func:`build_zdr_provider`);
            if ``None`` the SDK resolves the ambient ``ANTHROPIC_API_KEY``, which
            is **not** appropriate for real child story text.
        max_tokens: Output token ceiling for a generation. A scene script is
            small, but the default leaves ample headroom.
        effort: Reasoning effort passed via ``output_config`` (``"low"`` …
            ``"max"``). ``"high"`` suits getting a contract-valid script right.

    Raises:
        ProviderUnavailableError: If no ``client`` is given and the ``anthropic``
            SDK is not installed.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        client: Any | None = None,
        api_key: str | None = None,
        max_tokens: int = 16000,
        effort: str = "high",
    ) -> None:
        if client is None:
            try:
                module = _load_anthropic_module()
            except ImportError as exc:
                raise ProviderUnavailableError(
                    f"anthropic:{model}",
                    "the 'anthropic' SDK is not installed; "
                    "install it with: pip install 'kathai-chithiram[generation]'",
                ) from exc
            # Pass the key explicitly so a dedicated ZDR credential is used
            # rather than whatever the SDK would resolve from the environment.
            client = module.Anthropic(api_key=api_key) if api_key else module.Anthropic()
        # Held structurally (it may be a real client or an injected fake), so the
        # adapter duck-types the streaming + content-block surface it uses.
        self._client: Any = client
        self._model = model
        self._max_tokens = max_tokens
        self._effort = effort

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Send ``request`` to the model and return its text reply.

        Streams the response (via ``messages.stream``) so a long generation
        cannot hit an idle-connection timeout, then reads the assembled message.

        Args:
            request: The outbound request. ``request.prompt`` is the (already
                pseudonymized) story; ``request.system_prompt`` carries the
                safety + contract instructions.

        Returns:
            The model's reply text as an :class:`LLMResponse`.

        Raises:
            ProviderResponseError: If the model declines the request (a safety
                refusal) or returns no usable text.
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self._effort},
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt

        with self._client.messages.stream(**kwargs) as stream:
            message = stream.get_final_message()

        if getattr(message, "stop_reason", None) == "refusal":
            raise ProviderResponseError(
                self._model,
                "the model declined the request (safety refusal)",
            )

        text = "".join(
            block.text
            for block in message.content
            if getattr(block, "type", None) == "text"
        )
        if not text.strip():
            raise ProviderResponseError(
                self._model,
                "the model returned no text content",
            )
        return LLMResponse(text=text)


def build_zdr_provider(
    *,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    env: Mapping[str, str] | None = None,
) -> AnthropicProvider:
    """Build a provider backed by the dedicated ZDR / no-training key.

    Fails **closed**: if :data:`ZDR_API_KEY_ENV` is not set, it raises rather
    than falling back to the ambient ``ANTHROPIC_API_KEY`` — story text about a
    child must only go to an org configured for no-training / zero-retention
    (PRIVACY.md §6), and that guarantee rides on which credential is used.

    Args:
        model: The Claude model id.
        effort: Reasoning effort for generation.
        env: Environment mapping to read the key from (defaults to
            ``os.environ``).

    Returns:
        An :class:`AnthropicProvider` constructed with the dedicated key.

    Raises:
        ProviderConfigError: If the ZDR key is not configured.
        ProviderUnavailableError: If the ``anthropic`` SDK is not installed.
    """
    source = os.environ if env is None else env
    key = source.get(ZDR_API_KEY_ENV)
    if not key:
        raise ProviderConfigError(
            f"anthropic:{model}:zdr-key",
            f"{ZDR_API_KEY_ENV} is not set; refusing to send story text without a "
            "dedicated no-training / zero-retention credential (no fallback to a "
            "general API key)",
        )
    return AnthropicProvider(model=model, effort=effort, api_key=key)
