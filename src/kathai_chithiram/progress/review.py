"""Therapist-in-the-loop review of premise suggestions (ADR-002 D3/D7.3) + evidence.

This is the *path* the ADR requires to exist and be tested: a suggestion is
recorded, then a named reviewer explicitly accepts / edits / dismisses it, and
that decision is persisted. It is deliberately inert:

* **It generates nothing.** No progress measure is computed and no suggestion is
  derived here — those are gated (ADR-002 Decision 6/7). A suggestion arrives from
  outside (a future, gated engine, or a person); this module only records the
  therapist's decision on it.
* **Deciding triggers nothing** (Decisions 3/4/8). Recording an acceptance does
  not edit a premise, generate a story, or schedule one. Any resulting story is a
  separate, human-driven pass through the full safety pipeline.

:func:`build_goal_evidence` gathers the read-only evidence for a goal from the
captured feedback (see :mod:`kathai_chithiram.progress.evidence`) — again, raw
inputs only, no measure.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from kathai_chithiram.errors import SuggestionError
from kathai_chithiram.feedback.schema import SessionFeedback
from kathai_chithiram.progress.evidence import EvidenceBundle, build_evidence
from kathai_chithiram.progress.suggestion import (
    PremiseSuggestion,
    SuggestionDecision,
    SuggestionStatus,
)
from kathai_chithiram.storage import StoryArtifactStore

__all__ = [
    "build_goal_evidence",
    "decide_suggestion",
    "open_suggestions",
    "record_suggestion",
]


def record_suggestion(
    store: StoryArtifactStore, story_id: str, suggestion: PremiseSuggestion
) -> None:
    """Persist a premise suggestion awaiting a therapist's decision.

    This does not generate the suggestion — it stores one that already exists so a
    therapist can act on it (ADR-002 Decision 7.3).

    Args:
        store: The artifact store.
        story_id: The story the suggestion is reviewed under.
        suggestion: The suggestion to record.

    Raises:
        StoryNotFoundError: If the story does not exist.
        OSError: If the record cannot be written.
    """
    store.append_progress_suggestion(story_id, suggestion.to_record())


def decide_suggestion(
    store: StoryArtifactStore,
    story_id: str,
    *,
    suggestion_id: str,
    status: SuggestionStatus,
    reviewer: str,
    final_premise: str | None = None,
    note: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> SuggestionDecision:
    """Record a therapist's accept / edit / dismiss decision on a suggestion.

    Recording the decision is the *only* effect — it never edits a premise,
    generates a story, or schedules one (ADR-002 Decisions 3/4/8).

    Args:
        store: The artifact store.
        story_id: The story the suggestion is under.
        suggestion_id: The suggestion being decided.
        status: The decision (accepted / edited / dismissed).
        reviewer: Who decided (non-empty identifier).
        final_premise: The approved premise, for accepted/edited decisions.
        note: Optional reviewer note.
        clock: Optional clock for the timestamp (injectable for tests). Defaults
            to ``datetime.now(timezone.utc)``.

    Returns:
        The written :class:`SuggestionDecision`.

    Raises:
        StoryNotFoundError: If the story does not exist.
        SuggestionError: If the suggestion is unknown or already decided.
        ValueError: If the decision fields are inconsistent (see
            :class:`SuggestionDecision`).
        OSError: If the record cannot be written.
    """
    suggestions, decided = _parse_log(store, story_id)
    if suggestion_id not in suggestions:
        raise SuggestionError(suggestion_id, "no such suggestion for this story")
    if suggestion_id in decided:
        raise SuggestionError(suggestion_id, "already decided")

    decision = SuggestionDecision(
        suggestion_id=suggestion_id,
        status=status,
        reviewer=reviewer,
        decided_at=(clock or _default_clock)(),
        final_premise=final_premise,
        note=note,
    )
    store.append_progress_suggestion(story_id, decision.to_record())
    return decision


def open_suggestions(store: StoryArtifactStore, story_id: str) -> list[PremiseSuggestion]:
    """Return the suggestions for ``story_id`` that have no decision yet.

    Args:
        store: The artifact store.
        story_id: The story to read.

    Returns:
        The pending suggestions, in the order they were recorded.

    Raises:
        StoryNotFoundError: If the story does not exist.
        ValueError: If a stored record is malformed.
    """
    suggestions, decided = _parse_log(store, story_id)
    return [s for sid, s in suggestions.items() if sid not in decided]


def build_goal_evidence(
    store: StoryArtifactStore, goal_id: str, *, window: int
) -> EvidenceBundle:
    """Gather the read-only evidence for ``goal_id`` across all stored feedback.

    Scans every story's captured feedback, keeps the records for this goal, and
    returns the raw evidence over the most recent ``window`` sessions. Computes no
    progress measure (ADR-002 Decision 2/6).

    Args:
        store: The artifact store to scan.
        goal_id: The goal to gather evidence for.
        window: The number of most-recent sessions to include (>= 1).

    Returns:
        The raw :class:`EvidenceBundle`.

    Raises:
        ValueError: If ``window`` < 1, or a stored feedback record is malformed.
    """
    feedback: list[SessionFeedback] = []
    for story_id in store.iter_story_ids():
        for raw in store.read_session_feedback(story_id):
            feedback.append(SessionFeedback.from_record(raw))
    return build_evidence(goal_id, feedback, window=window)


def _parse_log(
    store: StoryArtifactStore, story_id: str
) -> tuple[dict[str, PremiseSuggestion], set[str]]:
    """Return (suggestions by id, ids that have a decision) from the log."""
    suggestions: dict[str, PremiseSuggestion] = {}
    decided: set[str] = set()
    for record in store.read_progress_suggestions(story_id):
        kind = record.get("kind")
        if kind == "suggestion":
            suggestion = PremiseSuggestion.from_record(record)
            suggestions[suggestion.suggestion_id] = suggestion
        elif kind == "decision":
            decision = SuggestionDecision.from_record(record)
            decided.add(decision.suggestion_id)
        else:
            raise ValueError(f"unknown suggestion-log record kind: {kind!r}")
    return suggestions, decided


def _default_clock() -> datetime:
    """Return the current UTC time (the production clock for decisions)."""
    return datetime.now(timezone.utc)
