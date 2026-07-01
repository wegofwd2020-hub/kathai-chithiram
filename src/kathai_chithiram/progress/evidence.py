"""Read-only evidence view over captured feedback primitives (ADR-002 Decision 7.2).

This is the *explainability substrate* the ADR requires: it surfaces the exact
inputs a therapist would reason over — which sessions, and their raw primitive
values — for one goal over a window of recent sessions.

It deliberately computes **no progress measure**. There is no percentage, no
ratio, no trend, no mastery flag, and no threshold verdict here — those are the
progress *measure*, which ADR-002 Decision 2/6 gate behind the Decision 7
preconditions (a professional collaborator must define the window K, thresholds,
and trend definitions first). What this module provides is raw, deterministic
transparency: the ordered sessions and a raw tally of their values, nothing
derived or interpreted. The eventual engine will layer its measure on top of this
evidence — it will not replace it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from kathai_chithiram.feedback.schema import MoodCheckin, PromptLevel, SessionFeedback

__all__ = ["EvidenceBundle", "EvidenceRow", "build_evidence"]


@dataclass(frozen=True)
class EvidenceRow:
    """One session's raw primitives, flattened for display.

    Args:
        story_id: The story/animation the session used (opaque id).
        prompt_level: How much support the child needed.
        completed: Whether the child completed the target behaviour.
        mood_checkin: The session mood check-in.
        recorded_at: When the feedback was captured.
    """

    story_id: str
    prompt_level: PromptLevel
    completed: bool
    mood_checkin: MoodCheckin
    recorded_at: datetime


@dataclass(frozen=True)
class EvidenceBundle:
    """The raw inputs behind (a future) progress view for one goal.

    Carries only the sessions and raw tallies — **never** a computed measure.
    ``prompt_level_counts`` and ``completed_count`` are raw frequencies (the same
    thing a reader would get by counting :attr:`rows`), provided for convenience;
    turning them into a percentage, ratio, trend, or verdict is the gated engine's
    job (ADR-002 Decision 2/6), not this bundle's.

    Args:
        goal_id: The therapist-owned goal these sessions worked toward.
        window: The requested number of most-recent sessions to include.
        rows: The selected sessions in chronological order (oldest first). At most
            ``window`` of them; fewer if not that many exist.
        prompt_level_counts: Raw count of each prompt level over ``rows``.
        completed_count: Raw count of sessions where ``completed`` was true.
    """

    goal_id: str
    window: int
    rows: tuple[EvidenceRow, ...]
    prompt_level_counts: dict[PromptLevel, int]
    completed_count: int

    @property
    def session_count(self) -> int:
        """How many sessions are in the window (``len(rows)``)."""
        return len(self.rows)


def build_evidence(
    goal_id: str,
    feedback: Iterable[SessionFeedback],
    *,
    window: int,
) -> EvidenceBundle:
    """Gather the raw evidence for ``goal_id`` over the most recent ``window`` sessions.

    Filters ``feedback`` to the goal, orders by ``recorded_at``, keeps the last
    ``window`` records, and returns them as raw rows plus raw tallies. Computes no
    progress measure (ADR-002 Decision 2/6).

    Args:
        goal_id: The goal to gather evidence for.
        feedback: Session feedback records (any goals; filtered here).
        window: The number of most-recent sessions to include (must be >= 1).

    Returns:
        An :class:`EvidenceBundle` of the raw inputs.

    Raises:
        ValueError: If ``window`` is less than 1.
    """
    if window < 1:
        raise ValueError("window must be >= 1")

    matching = sorted(
        (f for f in feedback if f.goal_id == goal_id),
        key=lambda f: f.recorded_at,
    )
    selected = matching[-window:]

    rows = tuple(
        EvidenceRow(
            story_id=f.story_id,
            prompt_level=f.prompt_level,
            completed=f.completed,
            mood_checkin=f.mood_checkin,
            recorded_at=f.recorded_at,
        )
        for f in selected
    )
    prompt_level_counts = {
        level: sum(1 for r in rows if r.prompt_level is level) for level in PromptLevel
    }
    completed_count = sum(1 for r in rows if r.completed)

    return EvidenceBundle(
        goal_id=goal_id,
        window=window,
        rows=rows,
        prompt_level_counts=prompt_level_counts,
        completed_count=completed_count,
    )
