"""Provider-agnostic types for the ``wegofwd-llm`` seam.

Defines the contract a concrete LLM provider must satisfy (:class:`LLMProvider`)
and the privacy-relevant records around a call: :class:`ProviderConfig` (the
no-training / zero-retention guarantee) and :class:`ProviderRequestRecord` (an
auditable note of what configuration a request used — lengths only, never text).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

__all__ = [
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "ProviderConfig",
    "ProviderRequestRecord",
]


@dataclass(frozen=True)
class ProviderConfig:
    """Privacy posture of an LLM provider configuration.

    Story text about a child may only be sent to a provider configured for both
    no-training and zero-retention (PRIVACY.md §6). This record is what the seam
    checks before dispatch and stores afterwards.

    Args:
        provider_id: Stable identifier of the provider + setting (e.g.
            ``"anthropic:no-train-zdr"``). Safe to log.
        no_training: Provider guarantees the payload is not used for training.
        zero_retention: Provider guarantees the payload is not retained.

    Raises:
        ValueError: If ``provider_id`` is blank.
    """

    provider_id: str
    no_training: bool
    zero_retention: bool

    def __post_init__(self) -> None:
        if not self.provider_id or not self.provider_id.strip():
            raise ValueError("provider_id must be a non-empty identifier")

    @property
    def is_privacy_compliant(self) -> bool:
        """Whether the configuration meets the bar for sending child story text."""
        return self.no_training and self.zero_retention


@dataclass(frozen=True)
class LLMRequest:
    """A single outbound request through the seam.

    ``prompt`` is expected to be already pseudonymized; the seam guards this
    before constructing the request.

    Args:
        prompt: The text to send. Must not contain a child identifier.
        config: The provider configuration governing this request.
    """

    prompt: str
    config: ProviderConfig


@dataclass(frozen=True)
class LLMResponse:
    """A provider's reply.

    Args:
        text: The generated text returned by the provider.
    """

    text: str


@dataclass(frozen=True)
class ProviderRequestRecord:
    """An auditable record that a request ran under a given privacy posture.

    Deliberately stores only the prompt *length*, never its content, so the
    record is safe to persist and log (PRIVACY.md §6).

    Args:
        request_id: Caller-supplied correlation id for this request.
        provider_id: The provider configuration used.
        no_training: Whether the no-training guarantee applied.
        zero_retention: Whether the zero-retention guarantee applied.
        prompt_chars: Character count of the outbound prompt (length only).
        created_at: When the request was made, if a clock was supplied.
    """

    request_id: str
    provider_id: str
    no_training: bool
    zero_retention: bool
    prompt_chars: int
    created_at: datetime | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """The contract a concrete LLM provider must satisfy to plug into the seam.

    Implementations live outside this module (provider-agnostic by design). A
    provider receives an :class:`LLMRequest` whose prompt is already minimized.
    """

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate a completion for ``request`` and return the provider's reply.

        Args:
            request: The outbound request (prompt already pseudonymized).

        Returns:
            The provider's :class:`LLMResponse`.

        Raises:
            Exception: Implementations raise provider-specific errors; the seam
                does not constrain them here.
        """
        ...
