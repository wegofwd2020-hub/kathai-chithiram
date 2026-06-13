"""The ``wegofwd-llm`` seam: provider-agnostic generation boundary.

Generation never talks to a concrete LLM provider directly. It goes through
this seam, which (a) enforces identifier minimization before any text leaves
the device, (b) refuses providers that lack a no-training / zero-retention
guarantee, and (c) records the provider configuration used per request
(PRIVACY.md §6, CLAUDE.md architecture rules).

A concrete provider is anything implementing :class:`LLMProvider`; none is
hard-coded here.
"""

from __future__ import annotations

from kathai_chithiram.wegofwd_llm.gateway import GenerationResult, run_generation
from kathai_chithiram.wegofwd_llm.provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderConfig,
    ProviderRequestRecord,
)

__all__ = [
    "GenerationResult",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "ProviderConfig",
    "ProviderRequestRecord",
    "run_generation",
]
