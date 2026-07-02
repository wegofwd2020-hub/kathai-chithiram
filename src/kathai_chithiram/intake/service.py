"""Process a vetted parent submission into a stored, review-gated draft.

:func:`submit_intake` is the intake-side orchestrator. It enforces the legal
gate first (every consent must be granted), then runs the existing generation
path and stores the artifacts:

    consent gate -> generate_scene_script (seam) -> store
        story.txt + scene_script.json + intake.json (consent record)

It deliberately does **not** render or deliver: the rendered animation is a
later, human-review-gated step. Generation runs before any file is written, so
a failure leaves nothing stored. The child's name is used only to build the
pseudonymization mapping; the stored scene script keeps the token, and the
intake record holds no story text or name.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from kathai_chithiram.errors import ConsentError
from kathai_chithiram.generation import (
    GeneratedSceneScript,
    build_offline_scene_script,
    generate_scene_script,
)
from kathai_chithiram.intake.privacy_notice import PRIVACY_NOTICE_VERSION
from kathai_chithiram.intake.submission import ParentSubmission, minimization_warnings
from kathai_chithiram.privacy import NameMapping
from kathai_chithiram.storage import StoryStore
from kathai_chithiram.wegofwd_llm.provider import LLMProvider, ProviderConfig

__all__ = ["IntakeResult", "submit_intake"]


@dataclass(frozen=True)
class IntakeResult:
    """The outcome of accepting one parent submission.

    Args:
        story_id: The opaque id the story was stored under.
        generated: The validated scene script and its per-attempt audit records.
        warnings: Advisory minimization warnings surfaced for this submission
            (empty if none). Informational; intake still succeeded.
    """

    story_id: str
    generated: GeneratedSceneScript
    warnings: tuple[str, ...]


def submit_intake(
    submission: ParentSubmission,
    *,
    provider: LLMProvider | None = None,
    store: StoryStore,
    story_id: str | None = None,
    model_id: str = "anthropic",
    max_attempts: int = 3,
    offline: bool = False,
    clock: Callable[[], datetime] | None = None,
) -> IntakeResult:
    """Accept a consented submission, generate a scene script, and store it.

    Args:
        submission: The vetted parent submission.
        provider: Any concrete provider implementing :class:`LLMProvider`. Required
            unless ``offline`` is set (then no provider is used).
        store: The artifact store to write into.
        story_id: Opaque id to store under. Defaults to a random UUID.
        model_id: Identifier recorded in the provider config / intake record
            (e.g. the model name). Not the API key.
        max_attempts: Max generation attempts including repairs.
        offline: When ``True``, generate the scene script locally (no LLM, no
            network, no key) instead of through the provider seam. The consent gate,
            name stripping, contract validation, storage, and record are unchanged.
        clock: Optional clock for timestamps (injectable for tests). Defaults to
            ``datetime.now(timezone.utc)``.

    Returns:
        An :class:`IntakeResult` with the story id, generated script, and any
        advisory warnings.

    Raises:
        ValueError: If ``offline`` is ``False`` and no ``provider`` is given.
        ConsentError: If any required consent is not granted; nothing is
            generated or stored.
        ProviderConfigError: If the provider is not no-training / zero-retention.
        IdentifierLeakError: If a child identifier survives pseudonymization.
        SceneScriptGenerationError: If generation cannot produce a valid script.
        OSError: If the artifacts cannot be written.
    """
    if not offline and provider is None:
        raise ValueError("submit_intake requires a provider unless offline=True")

    missing = submission.missing_consents()
    if missing:
        raise ConsentError(missing)

    now = (clock or _default_clock)()
    story_id = story_id or uuid.uuid4().hex
    warnings = tuple(minimization_warnings(submission))

    mapping = NameMapping.for_child(
        submission.child_first_name, nickname=submission.child_nickname
    )

    if offline:
        # Local, non-LLM generation: nothing leaves the machine, so the posture is
        # recorded as offline rather than a provider guarantee.
        script = build_offline_scene_script(
            story_text=submission.story_text, mapping=mapping, story_id=story_id
        )
        generated = GeneratedSceneScript(script=script, records=(), attempts=0)
        posture = {
            "provider_id": "offline:local-generation",
            "no_training": True,
            "zero_retention": True,
        }
    else:
        assert provider is not None  # guaranteed by the guard above
        # The parent's ai_processing consent is the assertion that the story may go
        # to a no-training / zero-retention provider; the seam still enforces it.
        config = ProviderConfig(
            provider_id=f"{model_id}:no-train-zdr",
            no_training=True,
            zero_retention=True,
        )
        generated = generate_scene_script(
            story_text=submission.story_text,
            mapping=mapping,
            provider=provider,
            config=config,
            request_id=story_id,
            max_attempts=max_attempts,
            clock=clock,
        )
        posture = {
            "provider_id": config.provider_id,
            "no_training": config.no_training,
            "zero_retention": config.zero_retention,
        }

    store.create_story(story_id, created_at=now, story_text=submission.story_text)
    store.write_scene_script(story_id, generated.script)
    store.write_intake_record(
        story_id,
        {
            "consent": submission.consent.as_record(),
            "privacy_notice_version": PRIVACY_NOTICE_VERSION,
            "recorded_at": now.isoformat(),
            "provider_posture": posture,
            "minimization_warnings": list(warnings),
        },
    )

    return IntakeResult(story_id=story_id, generated=generated, warnings=warnings)


def _default_clock() -> datetime:
    """Return the current UTC time (the production clock for intake records)."""
    return datetime.now(timezone.utc)
