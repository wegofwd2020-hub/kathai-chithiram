"""Turn a parent's story into a validated scene script through the seam.

:func:`generate_scene_script` is the product's "generation step": it sends the
pseudonymized story through the ``wegofwd-llm`` seam (which enforces the privacy
guarantees), parses the provider's reply as a scene script, and validates it
against the contract *before returning it*. Generation never hands a renderer an
unvalidated script (CLAUDE.md architecture rules).

A single LLM call cannot be trusted to satisfy every cross-field rule, so this
runs a bounded **validate-and-repair loop**: on a rejection it feeds the
(log-safe) failure back into the next attempt's system prompt and tries again,
up to ``max_attempts``. Each attempt is an independent seam call with its own
audit record. The child's real name is never restored here — ``child_token``
stays in the stored script; the name is a render-time substitution only.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from kathai_chithiram.errors import SceneScriptGenerationError, SceneScriptInvalidError
from kathai_chithiram.generation.scene_script_prompt import build_scene_script_system_prompt
from kathai_chithiram.privacy.pseudonymize import NameMapping
from kathai_chithiram.scene_script.validation import validate_scene_script
from kathai_chithiram.wegofwd_llm.gateway import run_generation
from kathai_chithiram.wegofwd_llm.provider import LLMProvider, ProviderConfig, ProviderRequestRecord

__all__ = ["GeneratedSceneScript", "generate_scene_script"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedSceneScript:
    """A validated scene script plus the audit trail of how it was produced.

    Args:
        script: The decoded, contract-valid scene script (safe to render).
        records: One :class:`ProviderRequestRecord` per attempt, in order — the
            privacy-posture audit for every seam call made.
        attempts: How many attempts were needed (``len(records)``); ``1`` when
            the first reply was already valid.
    """

    script: dict[str, Any]
    records: tuple[ProviderRequestRecord, ...]
    attempts: int


def generate_scene_script(
    *,
    story_text: str,
    mapping: NameMapping,
    provider: LLMProvider,
    config: ProviderConfig,
    request_id: str,
    max_attempts: int = 3,
    clock: Callable[[], datetime] | None = None,
) -> GeneratedSceneScript:
    """Generate a contract-valid scene script from a parent's story.

    Args:
        story_text: The raw parent-authored story. Pseudonymized by the seam
            before any dispatch; never sent or logged verbatim.
        mapping: The local identifier→token mapping for this child. Its token is
            what the script's ``child_token`` will carry.
        provider: Any concrete provider implementing :class:`LLMProvider`.
        config: The provider configuration; must be no-training / zero-retention
            (the seam enforces this).
        request_id: Caller-supplied correlation id. Each attempt derives a
            distinct id (``"<request_id>#<n>"``) for its audit record.
        max_attempts: Maximum number of generation attempts, including repairs.
            Must be at least 1.
        clock: Optional callable returning the current time, used to stamp each
            audit record. Injectable for deterministic tests.

    Returns:
        A :class:`GeneratedSceneScript` with the validated script and the
        per-attempt audit records.

    Raises:
        ValueError: If ``request_id`` is blank or ``max_attempts`` < 1.
        ProviderConfigError: If ``config`` is not no-training / zero-retention.
        IdentifierLeakError: If a child identifier survives pseudonymization.
        ProviderResponseError: If the provider refuses or returns no text.
        SceneScriptGenerationError: If no attempt yields a parseable,
            contract-valid script within ``max_attempts``.
    """
    if not request_id or not request_id.strip():
        raise ValueError("request_id must be a non-empty correlation id")
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be at least 1, got {max_attempts}")

    records: list[ProviderRequestRecord] = []
    feedback: str | None = None
    last_failure = "no attempt produced a parseable scene script"

    for attempt in range(1, max_attempts + 1):
        system_prompt = build_scene_script_system_prompt(
            child_token=mapping.token,
            repair_feedback=feedback,
        )
        result = run_generation(
            story_text=story_text,
            mapping=mapping,
            provider=provider,
            config=config,
            request_id=f"{request_id}#{attempt}",
            system_prompt=system_prompt,
            clock=clock,
        )
        records.append(result.record)

        try:
            script = _extract_scene_script(result.response.text)
            validate_scene_script(script)
        except SceneScriptInvalidError as exc:
            feedback = _feedback_from_invalid(exc)
            last_failure = feedback
            logger.info(
                "scene-script generation attempt %d/%d rejected: rule=%s",
                attempt,
                max_attempts,
                exc.rule,
            )
            continue
        except SceneScriptGenerationError as exc:
            feedback = exc.detail
            last_failure = exc.detail
            logger.info(
                "scene-script generation attempt %d/%d unparseable: rule=%s",
                attempt,
                max_attempts,
                exc.rule,
            )
            continue

        logger.info("scene-script generation succeeded on attempt %d/%d", attempt, max_attempts)
        return GeneratedSceneScript(
            script=script,
            records=tuple(records),
            attempts=attempt,
        )

    raise SceneScriptGenerationError(
        "generation.exhausted",
        f"no contract-valid scene script after {max_attempts} attempt(s); "
        f"last failure: {last_failure}",
        attempts=max_attempts,
    )


def _extract_scene_script(text: str) -> dict[str, Any]:
    """Decode the single JSON object from a provider reply.

    Tolerant of the common ways a model wraps JSON even when told not to: a
    leading/trailing code fence or stray prose. It extracts the substring from
    the first ``{`` to the last ``}`` and decodes that.

    Args:
        text: The raw provider reply.

    Returns:
        The decoded JSON object as a dict.

    Raises:
        SceneScriptGenerationError: If no JSON object can be decoded, or the
            top-level value is not an object. The message carries no story text
            (only the failure mode), so it is safe to log and to feed back.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise SceneScriptGenerationError(
            "generation.unparseable",
            "reply contained no JSON object; emit exactly one JSON object and nothing else",
        )

    candidate = text[start : end + 1]
    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise SceneScriptGenerationError(
            "generation.unparseable",
            f"reply was not valid JSON ({exc.msg}); emit exactly one well-formed JSON object",
        ) from exc

    if not isinstance(decoded, dict):
        raise SceneScriptGenerationError(
            "generation.unparseable",
            f"top-level JSON must be an object, got {type(decoded).__name__}",
        )
    return decoded


def _feedback_from_invalid(exc: SceneScriptInvalidError) -> str:
    """Render a validation failure as log-safe repair guidance.

    Uses only the safe fields of the error (rule id, scene index, field, and the
    detail — which the validator guarantees carries no raw story text).
    """
    location = ""
    if exc.scene_index is not None:
        location += f" (scene {exc.scene_index})"
    if exc.field is not None:
        location += f" (field '{exc.field}')"
    return f"validation rule '{exc.rule}'{location} failed: {exc.detail}"
