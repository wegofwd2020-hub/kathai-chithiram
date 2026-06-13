"""The enforced generation path through the ``wegofwd-llm`` seam.

:func:`run_generation` is the single choke point for sending a parent's story
to a provider. It guarantees, in order, that:

1. the provider configuration is no-training / zero-retention (PRIVACY.md §6);
2. the child's identifiers are removed from the outbound text;
3. nothing leaks through — a residual identifier is a hard stop, not a warning;
4. the configuration used is recorded per request (lengths only, never text).

No concrete provider is referenced; callers pass any :class:`LLMProvider`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from kathai_chithiram.errors import IdentifierLeakError, ProviderConfigError
from kathai_chithiram.privacy.pseudonymize import (
    NameMapping,
    count_identifiers,
    pseudonymize,
)
from kathai_chithiram.wegofwd_llm.provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderConfig,
    ProviderRequestRecord,
)

__all__ = ["GenerationResult", "run_generation"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenerationResult:
    """The outcome of a seam call.

    Args:
        response: The provider's reply.
        record: The auditable provider-configuration record for this request.
    """

    response: LLMResponse
    record: ProviderRequestRecord


def run_generation(
    *,
    story_text: str,
    mapping: NameMapping,
    provider: LLMProvider,
    config: ProviderConfig,
    request_id: str,
    clock: Callable[[], datetime] | None = None,
) -> GenerationResult:
    """Pseudonymize, guard, dispatch, and record a single generation request.

    Args:
        story_text: The raw parent-authored story. Never sent verbatim; its
            identifiers are stripped first.
        mapping: The local identifier→token mapping for this child.
        provider: Any concrete provider implementing :class:`LLMProvider`.
        config: The provider configuration; must be privacy-compliant.
        request_id: Caller-supplied correlation id for the audit record.
        clock: Optional callable returning the current time, used to stamp the
            record. Injectable for deterministic tests; if ``None`` the record
            carries no timestamp.

    Returns:
        A :class:`GenerationResult` with the provider response and the audit
        record.

    Raises:
        ValueError: If ``request_id`` is blank.
        ProviderConfigError: If ``config`` is not no-training / zero-retention.
        IdentifierLeakError: If a child identifier survives pseudonymization;
            nothing is dispatched in that case.
    """
    if not request_id or not request_id.strip():
        raise ValueError("request_id must be a non-empty correlation id")

    # 1. Refuse a provider that has not committed to no-training / zero-retention
    #    before doing anything else with the story.
    if not config.is_privacy_compliant:
        raise ProviderConfigError(
            config.provider_id,
            "provider must guarantee both no-training and zero-retention "
            "to receive child story text",
        )

    # 2. Minimize: strip the child's identifiers to the token.
    prompt = pseudonymize(story_text, mapping)

    # 3. Guard immediately before dispatch: a residual identifier is a defect.
    residual = count_identifiers(prompt, mapping)
    if residual:
        logger.warning(
            "wegofwd-llm blocked dispatch: residual identifiers=%d request=%s provider=%s",
            residual,
            request_id,
            config.provider_id,
        )
        raise IdentifierLeakError(residual)

    # 4. Log only safe fields (no story text, no name) and dispatch.
    logger.info(
        "wegofwd-llm dispatch: request=%s provider=%s no_training=%s "
        "zero_retention=%s prompt_chars=%d",
        request_id,
        config.provider_id,
        config.no_training,
        config.zero_retention,
        len(prompt),
    )
    response = provider.complete(LLMRequest(prompt=prompt, config=config))

    # 5. Record the privacy posture this request ran under.
    record = ProviderRequestRecord(
        request_id=request_id,
        provider_id=config.provider_id,
        no_training=config.no_training,
        zero_retention=config.zero_retention,
        prompt_chars=len(prompt),
        created_at=clock() if clock is not None else None,
    )
    return GenerationResult(response=response, record=record)
