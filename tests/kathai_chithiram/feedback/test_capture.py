"""Tests for feedback capture through the store (record + load round-trip)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from kathai_chithiram.errors import StoryNotFoundError
from kathai_chithiram.feedback import (
    MoodCheckin,
    PromptLevel,
    SessionFeedback,
    load_session_feedback,
    record_session_feedback,
)
from kathai_chithiram.storage import StoryArtifactStore

_CREATED = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _store_with_story(tmp_path: Path) -> StoryArtifactStore:
    store = StoryArtifactStore(tmp_path / "stories")
    store.create_story("story-1", created_at=_CREATED, story_text="A calm story.")
    return store


def _fb(prompt: PromptLevel, mood: MoodCheckin, *, day: int) -> SessionFeedback:
    return SessionFeedback(
        goal_id="goal-1",
        story_id="story-1",
        prompt_level=prompt,
        completed=prompt is PromptLevel.INDEPENDENT,
        mood_checkin=mood,
        recorded_at=datetime(2026, 6, day, tzinfo=timezone.utc),
    )


def test_record_and_load_round_trip_in_order(tmp_path: Path) -> None:
    store = _store_with_story(tmp_path)
    first = _fb(PromptLevel.PROMPTED, MoodCheckin.NEUTRAL, day=2)
    second = _fb(PromptLevel.INDEPENDENT, MoodCheckin.HAPPY, day=3)

    record_session_feedback(store=store, story_id="story-1", feedback=first)
    record_session_feedback(store=store, story_id="story-1", feedback=second)

    assert load_session_feedback(store=store, story_id="story-1") == [first, second]


def test_load_is_empty_when_none_captured(tmp_path: Path) -> None:
    store = _store_with_story(tmp_path)
    assert load_session_feedback(store=store, story_id="story-1") == []


def test_feedback_is_enumerated_as_an_artifact(tmp_path: Path) -> None:
    # So a verifiable hard-delete sweeps it (ADR-002 D5 / PRIVACY §5).
    store = _store_with_story(tmp_path)
    record_session_feedback(
        store=store,
        story_id="story-1",
        feedback=_fb(PromptLevel.REFUSED, MoodCheckin.UNHAPPY, day=2),
    )
    names = {p.name for p in store.artifact_paths("story-1")}
    assert "feedback.jsonl" in names


def test_record_requires_existing_story(tmp_path: Path) -> None:
    store = StoryArtifactStore(tmp_path / "stories")
    with pytest.raises(StoryNotFoundError):
        record_session_feedback(
            store=store,
            story_id="missing",
            feedback=_fb(PromptLevel.PROMPTED, MoodCheckin.NEUTRAL, day=2),
        )
