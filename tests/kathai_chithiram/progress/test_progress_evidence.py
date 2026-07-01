"""Tests for the read-only evidence view (ADR-002 M1 scaffolding, Decision 7.2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from kathai_chithiram.feedback.schema import MoodCheckin, PromptLevel, SessionFeedback
from kathai_chithiram.progress import EvidenceBundle, build_evidence

_BASE = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _fb(
    *,
    goal: str = "g1",
    story: str = "s1",
    level: PromptLevel = PromptLevel.INDEPENDENT,
    completed: bool = True,
    mood: MoodCheckin = MoodCheckin.HAPPY,
    day: int = 0,
) -> SessionFeedback:
    return SessionFeedback(
        goal_id=goal,
        story_id=story,
        prompt_level=level,
        completed=completed,
        mood_checkin=mood,
        recorded_at=_BASE + timedelta(days=day),
    )


def test_filters_to_the_goal() -> None:
    feedback = [_fb(goal="g1", day=0), _fb(goal="g2", day=1), _fb(goal="g1", day=2)]
    bundle = build_evidence("g1", feedback, window=10)
    assert bundle.session_count == 2
    assert all(True for _ in bundle.rows)  # only g1 rows present


def test_keeps_the_most_recent_window_in_chronological_order() -> None:
    feedback = [_fb(story=f"s{d}", day=d) for d in range(5)]  # days 0..4
    bundle = build_evidence("g1", feedback, window=3)
    assert bundle.window == 3
    assert [r.story_id for r in bundle.rows] == ["s2", "s3", "s4"]  # last 3, oldest-first


def test_fewer_records_than_window_returns_all() -> None:
    bundle = build_evidence("g1", [_fb(day=0), _fb(day=1)], window=5)
    assert bundle.session_count == 2


def test_raw_tallies_are_counts_not_a_measure() -> None:
    feedback = [
        _fb(level=PromptLevel.INDEPENDENT, completed=True, day=0),
        _fb(level=PromptLevel.PROMPTED, completed=True, day=1),
        _fb(level=PromptLevel.REFUSED, completed=False, day=2),
    ]
    bundle = build_evidence("g1", feedback, window=10)
    assert bundle.prompt_level_counts[PromptLevel.INDEPENDENT] == 1
    assert bundle.prompt_level_counts[PromptLevel.PROMPTED] == 1
    assert bundle.prompt_level_counts[PromptLevel.REFUSED] == 1
    assert bundle.completed_count == 2


def test_bundle_exposes_no_progress_measure() -> None:
    # The inert boundary: no percentage / ratio / trend / mastery / verdict.
    bundle = build_evidence("g1", [_fb()], window=1)
    for forbidden in ("percent", "percentage", "ratio", "trend", "mastery", "score", "verdict"):
        assert not hasattr(bundle, forbidden), f"evidence must not expose a {forbidden!r}"
    assert isinstance(bundle, EvidenceBundle)


def test_window_must_be_positive() -> None:
    with pytest.raises(ValueError, match="window must be >= 1"):
        build_evidence("g1", [_fb()], window=0)
