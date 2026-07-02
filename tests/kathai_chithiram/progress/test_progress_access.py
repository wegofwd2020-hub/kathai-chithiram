"""The feedback/suggestion functions enforce access when given a GuardedStore (KC-11).

The per-story progress functions accept any ``StoryStore``, so passing a
``GuardedStore`` makes them deny-by-default and role-scoped (ADR-004), while the raw
store keeps working elsewhere. The role scoping follows the actor model: the family
owner captures feedback; the therapist reads it and decides on suggestions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from kathai_chithiram.access import GuardedStore, Principal, Role
from kathai_chithiram.errors import AccessDeniedError
from kathai_chithiram.feedback import load_session_feedback, record_session_feedback
from kathai_chithiram.feedback.schema import MoodCheckin, PromptLevel, SessionFeedback
from kathai_chithiram.progress import (
    PremiseSuggestion,
    open_suggestions,
    record_suggestion,
)
from kathai_chithiram.storage import StoryArtifactStore

_AT = datetime(2026, 6, 1, tzinfo=timezone.utc)
_OWNER = Principal("family-1")
_THERAPIST = Principal("ther-1")
_STRANGER = Principal("nobody-1")


def _feedback() -> SessionFeedback:
    return SessionFeedback(
        goal_id="g1",
        story_id="s1",
        prompt_level=PromptLevel.INDEPENDENT,
        completed=True,
        mood_checkin=MoodCheckin.HAPPY,
        recorded_at=_AT,
    )


def _owned_story(tmp_path: Path) -> StoryArtifactStore:
    store = StoryArtifactStore(tmp_path / "store")
    owner = GuardedStore(store, _OWNER)
    owner.create_story("s1", created_at=_AT, story_text="a calm story")
    owner.assign_role("s1", _THERAPIST.principal_id, Role.THERAPIST)
    return store


def test_owner_captures_feedback_therapist_reads_and_suggests(tmp_path: Path) -> None:
    store = _owned_story(tmp_path)

    # Family owner captures feedback (write_feedback is theirs; ADR-002 actor model).
    record_session_feedback(
        store=GuardedStore(store, _OWNER), story_id="s1", feedback=_feedback()
    )

    # Therapist reads the feedback and files a suggestion decision path.
    therapist = GuardedStore(store, _THERAPIST)
    assert load_session_feedback(store=therapist, story_id="s1") == [_feedback()]
    record_suggestion(
        therapist,
        "s1",
        PremiseSuggestion(
            suggestion_id="sg1",
            goal_id="g1",
            suggested_premise="Consider a slightly harder step.",
            rationale="Independence has been high.",
            created_at=_AT,
        ),
    )
    assert [s.suggestion_id for s in open_suggestions(therapist, "s1")] == ["sg1"]


def test_therapist_cannot_capture_feedback(tmp_path: Path) -> None:
    # Feedback is parent-owned (BRAND §7): the therapist may read it, not write it.
    store = _owned_story(tmp_path)
    with pytest.raises(AccessDeniedError):
        record_session_feedback(
            store=GuardedStore(store, _THERAPIST), story_id="s1", feedback=_feedback()
        )


def test_stranger_is_denied_feedback_and_suggestions(tmp_path: Path) -> None:
    store = _owned_story(tmp_path)
    stranger = GuardedStore(store, _STRANGER)
    with pytest.raises(AccessDeniedError):
        load_session_feedback(store=stranger, story_id="s1")
    with pytest.raises(AccessDeniedError):
        open_suggestions(stranger, "s1")
