"""Tests for the per-session feedback primitive (ADR-002 capture contract)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kathai_chithiram.feedback import MoodCheckin, PromptLevel, SessionFeedback

_AT = datetime(2026, 6, 30, 9, 0, tzinfo=timezone.utc)


def _feedback(**overrides: object) -> SessionFeedback:
    base: dict[str, object] = {
        "goal_id": "goal-brush-teeth",
        "story_id": "story-1",
        "prompt_level": PromptLevel.INDEPENDENT,
        "completed": True,
        "mood_checkin": MoodCheckin.HAPPY,
        "recorded_at": _AT,
    }
    base.update(overrides)
    return SessionFeedback(**base)  # type: ignore[arg-type]


def test_round_trips_through_record() -> None:
    fb = _feedback()
    record = fb.to_record()
    assert record == {
        "goal_id": "goal-brush-teeth",
        "story_id": "story-1",
        "prompt_level": "independent",
        "completed": True,
        "mood_checkin": 4,
        "recorded_at": _AT.isoformat(),
    }
    assert SessionFeedback.from_record(record) == fb


def test_rejects_unsafe_ids() -> None:
    with pytest.raises(ValueError, match="goal_id"):
        _feedback(goal_id="has space")
    with pytest.raises(ValueError, match="story_id"):
        _feedback(story_id="../escape")


def test_rejects_wrong_types() -> None:
    with pytest.raises(ValueError, match="prompt_level"):
        _feedback(prompt_level="independent")  # raw str, not the enum
    with pytest.raises(ValueError, match="completed"):
        _feedback(completed=1)  # int, not bool
    with pytest.raises(ValueError, match="mood_checkin"):
        _feedback(mood_checkin=4)  # raw int, not the enum


def test_no_free_text_field() -> None:
    # The contract is minimal by design — no notes/free-text key (ADR-002 D1).
    assert set(_feedback().to_record()) == {
        "goal_id",
        "story_id",
        "prompt_level",
        "completed",
        "mood_checkin",
        "recorded_at",
    }


def test_from_record_rejects_missing_keys() -> None:
    record = _feedback().to_record()
    del record["mood_checkin"]
    with pytest.raises(ValueError, match="missing keys: mood_checkin"):
        SessionFeedback.from_record(record)


def test_from_record_rejects_bad_enum_values() -> None:
    bad_level = _feedback().to_record() | {"prompt_level": "maybe"}
    with pytest.raises(ValueError, match="prompt_level"):
        SessionFeedback.from_record(bad_level)

    bad_mood = _feedback().to_record() | {"mood_checkin": 9}
    with pytest.raises(ValueError, match="mood_checkin"):
        SessionFeedback.from_record(bad_mood)


def test_from_record_rejects_bool_mood() -> None:
    # bool is an int subclass; it must not slip through as a mood ordinal.
    bad = _feedback().to_record() | {"mood_checkin": True}
    with pytest.raises(ValueError, match="mood_checkin"):
        SessionFeedback.from_record(bad)
