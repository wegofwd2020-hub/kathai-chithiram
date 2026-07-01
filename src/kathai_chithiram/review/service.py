"""Review a stored draft, then approve (deliver) or reject it — KC-7.

This is the coded form of the human-review gate (CONTENT_SAFETY.md §6). It sits
between a rendered *draft* and a *delivered* animation:

    render draft (guarded)  ->  human reviews  ->  approve -> mark delivered
                                              \\-> reject  -> left for retention

Two operations:

* :func:`load_review_bundle` gathers everything a reviewer needs to judge one
  story — the scene script, the rendered draft(s), and the consent record.
* :func:`review_story` records the decision durably (``review.json``) and, on
  approval, marks the story delivered so the retention sweep no longer purges it.

Approval is only permitted once a guard-passing draft has actually been rendered
(the pipeline files media only after the render-time safety guard passes), so an
approval cannot bypass the safety pipeline. The decision record is non-sensitive
and lives in the story directory, so a hard-delete removes it too.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kathai_chithiram.errors import ReviewError
from kathai_chithiram.review.schema import ReviewDecision, ReviewRecord
from kathai_chithiram.storage import StoryArtifactStore, StoryMetadata

__all__ = ["ReviewBundle", "load_review_bundle", "review_story"]


@dataclass(frozen=True)
class ReviewBundle:
    """Everything a human needs to review one story's draft.

    Args:
        story_id: The story under review (opaque id).
        metadata: The story's non-sensitive metadata (incl. delivered flag).
        scene_script: The generated scene script (child shown as a token).
        media_paths: Rendered draft animation(s); empty if none rendered yet.
        intake_record: The consent + provider-posture record, or ``None`` if the
            story was created without an intake (e.g. via ``generate``).
        existing_review: A prior review decision, or ``None`` if unreviewed.
    """

    story_id: str
    metadata: StoryMetadata
    scene_script: dict[str, Any]
    media_paths: list[Path]
    intake_record: dict[str, Any] | None
    existing_review: dict[str, Any] | None


def load_review_bundle(store: StoryArtifactStore, story_id: str) -> ReviewBundle:
    """Gather the artifacts a reviewer needs to judge ``story_id``.

    Args:
        store: The artifact store holding the story.
        story_id: The story to load.

    Returns:
        A :class:`ReviewBundle` with the scene script, rendered draft(s), consent
        record, and any prior decision.

    Raises:
        StoryNotFoundError: If no story, or no scene script, exists for the id.
        ValueError: If ``story_id`` is unsafe or an artifact is malformed.
    """
    metadata = store.read_metadata(story_id)
    return ReviewBundle(
        story_id=story_id,
        metadata=metadata,
        scene_script=store.read_scene_script(story_id),
        media_paths=store.media_paths(story_id),
        intake_record=store.read_intake_record(story_id),
        existing_review=store.read_review_record(story_id),
    )


def review_story(
    store: StoryArtifactStore,
    story_id: str,
    *,
    decision: ReviewDecision,
    reviewer: str,
    reason: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ReviewRecord:
    """Record a human-review decision for ``story_id`` and apply its effect.

    On approval the story is marked delivered *first* (so the retention sweep can
    no longer purge it) and then the decision is written; on rejection the
    decision is written and the story is left undelivered.

    Args:
        store: The artifact store holding the story.
        story_id: The story being reviewed.
        decision: Approve or reject.
        reviewer: Who reviewed (non-empty identifier; recorded for audit).
        reason: Operator-authored review notes. Required for a rejection.
        clock: Optional clock for the timestamp (injectable for tests). Defaults
            to ``datetime.now(timezone.utc)``.

    Returns:
        The written :class:`ReviewRecord`.

    Raises:
        StoryNotFoundError: If no story, or no scene script, exists for the id.
        ReviewError: If the reviewer is missing, a rejection has no reason, or an
            approval is attempted before a guard-passing draft has been rendered.
        ValueError: If ``story_id`` is unsafe or an artifact is malformed.
        OSError: If the decision cannot be written.
    """
    if not reviewer or not reviewer.strip():
        raise ReviewError(story_id, "a reviewer must be identified to record a decision")

    # read_scene_script also asserts the story (and its script) exist.
    script = store.read_scene_script(story_id)
    media_paths = store.media_paths(story_id)

    if decision is ReviewDecision.REJECTED and not (reason or "").strip():
        raise ReviewError(story_id, "a rejection must include a reason")
    if decision is ReviewDecision.APPROVED and not media_paths:
        raise ReviewError(
            story_id,
            "cannot approve a story with no rendered draft; a guard-passing "
            "animation must exist before it can be delivered",
        )

    now = (clock or _default_clock)()
    record = ReviewRecord(
        story_id=story_id,
        decision=decision,
        reviewer=reviewer.strip(),
        decided_at=now,
        reason=reason,
        reviewed=_reviewed_fingerprint(script, media_paths, store.read_intake_record(story_id)),
    )

    # Deliver first so an approved animation can never be lost to the retention
    # sweep in the window between marking and writing the audit record.
    if record.approved:
        store.mark_delivered(story_id)
    store.write_review_record(story_id, record.to_record())
    return record


def _reviewed_fingerprint(
    script: dict[str, Any],
    media_paths: list[Path],
    intake_record: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a non-sensitive fingerprint of what was reviewed (no story text)."""
    fingerprint: dict[str, Any] = {
        "schema_version": script.get("schema_version"),
        "scene_count": len(script.get("scenes", [])),
        "fps": script.get("fps"),
        "total_duration_s": script.get("total_duration_s"),
        "media_files": [p.name for p in media_paths],
    }
    if intake_record is not None and "provider_posture" in intake_record:
        fingerprint["provider_posture"] = intake_record["provider_posture"]
    return fingerprint


def _default_clock() -> datetime:
    """Return the current UTC time (the production clock for review records)."""
    return datetime.now(timezone.utc)
