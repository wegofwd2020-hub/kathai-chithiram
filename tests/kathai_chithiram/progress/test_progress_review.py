"""Tests for the therapist-in-the-loop review plumbing (ADR-002 M1 scaffolding)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from kathai_chithiram.errors import SuggestionError
from kathai_chithiram.feedback.schema import MoodCheckin, PromptLevel, SessionFeedback
from kathai_chithiram.progress import (
    PremiseSuggestion,
    SuggestionStatus,
    build_goal_evidence,
    decide_suggestion,
    open_suggestions,
    record_suggestion,
)
from kathai_chithiram.storage import BackupPurgeLog, StoryArtifactStore, delete_story

_CREATED = datetime(2026, 6, 1, tzinfo=timezone.utc)
_WHEN = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _store(tmp_path: Path) -> StoryArtifactStore:
    store = StoryArtifactStore(tmp_path / "store")
    store.create_story("s1", created_at=_CREATED, story_text="A calm story.")
    return store


def _suggestion(sid: str = "sg1", goal: str = "g1") -> PremiseSuggestion:
    return PremiseSuggestion(
        suggestion_id=sid,
        goal_id=goal,
        suggested_premise="Try a two-step version.",
        rationale="Independent recently.",
        created_at=_WHEN,
    )


def _clock() -> datetime:
    return _WHEN


def test_record_then_open_lists_the_pending_suggestion(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_suggestion(store, "s1", _suggestion())
    pending = open_suggestions(store, "s1")
    assert [s.suggestion_id for s in pending] == ["sg1"]


def test_decide_removes_from_open_and_records_the_decision(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_suggestion(store, "s1", _suggestion())
    decision = decide_suggestion(
        store,
        "s1",
        suggestion_id="sg1",
        status=SuggestionStatus.ACCEPTED,
        reviewer="nadia",
        final_premise="Try a two-step version.",
        clock=_clock,
    )
    assert decision.status is SuggestionStatus.ACCEPTED
    assert open_suggestions(store, "s1") == []
    # The decision is persisted (two records: suggestion + decision).
    kinds = [r["kind"] for r in store.read_progress_suggestions("s1")]
    assert kinds == ["suggestion", "decision"]


def test_decide_unknown_suggestion_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(SuggestionError, match="no such suggestion"):
        decide_suggestion(
            store, "s1", suggestion_id="ghost", status=SuggestionStatus.DISMISSED, reviewer="n"
        )


def test_decide_twice_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_suggestion(store, "s1", _suggestion())
    decide_suggestion(
        store, "s1", suggestion_id="sg1", status=SuggestionStatus.DISMISSED, reviewer="n",
        note="too soon",
    )
    with pytest.raises(SuggestionError, match="already decided"):
        decide_suggestion(
            store, "s1", suggestion_id="sg1", status=SuggestionStatus.DISMISSED, reviewer="n",
            note="again",
        )


def test_deciding_triggers_nothing(tmp_path: Path) -> None:
    """ADR-002 Decisions 3/4/8: a decision edits no premise and makes no story."""
    store = _store(tmp_path)
    record_suggestion(store, "s1", _suggestion())
    decide_suggestion(
        store, "s1", suggestion_id="sg1", status=SuggestionStatus.ACCEPTED, reviewer="n",
        final_premise="Try a two-step version.",
    )
    # No scene script, no media were produced as a side effect.
    names = {p.name for p in store.artifact_paths("s1")}
    assert "scene_script.json" not in names
    assert not any(p.parent.name == "media" for p in store.artifact_paths("s1"))
    assert store.read_metadata("s1").delivered is False


def test_suggestions_are_swept_by_hard_delete(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_suggestion(store, "s1", _suggestion())
    log = store.story_dir("s1") / "suggestions.jsonl"
    assert log.is_file()

    delete_story(store, "s1", purge_log=BackupPurgeLog(tmp_path / "purge.log"))
    assert not log.exists()
    assert store.artifact_paths("s1") == []


def test_build_goal_evidence_aggregates_across_stories(tmp_path: Path) -> None:
    store = StoryArtifactStore(tmp_path / "store")
    for i, sid in enumerate(("s1", "s2")):
        store.create_story(sid, created_at=_CREATED, story_text="story")
        store.append_session_feedback(
            sid,
            SessionFeedback(
                goal_id="g1",
                story_id=sid,
                prompt_level=PromptLevel.INDEPENDENT,
                completed=True,
                mood_checkin=MoodCheckin.HAPPY,
                recorded_at=_CREATED + timedelta(days=i),
            ).to_record(),
        )
    bundle = build_goal_evidence(store, "g1", window=10)
    assert bundle.session_count == 2
    assert {r.story_id for r in bundle.rows} == {"s1", "s2"}
