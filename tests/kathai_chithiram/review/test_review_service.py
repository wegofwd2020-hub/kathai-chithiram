"""Tests for the review workflow: load bundle, approve/reject, deliver gate (KC-7)."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from kathai_chithiram.errors import ReviewError, StoryNotFoundError
from kathai_chithiram.generation import EXAMPLE_SCENE_SCRIPT
from kathai_chithiram.review import ReviewDecision, load_review_bundle, review_story
from kathai_chithiram.storage import (
    BackupPurgeLog,
    StoryArtifactStore,
    delete_story,
    purge_undelivered_stories,
)

_CREATED = datetime(2026, 6, 1, tzinfo=timezone.utc)
_DECIDED = datetime(2026, 6, 2, tzinfo=timezone.utc)
STORY_TEXT = "Robin is scared of the dark. Robin turns on a light and feels calm."


def _script() -> dict:
    return copy.deepcopy(EXAMPLE_SCENE_SCRIPT)


def _clock() -> datetime:
    return _DECIDED


def _rendered_story(tmp_path: Path, story_id: str = "s1") -> StoryArtifactStore:
    """A store with a created story, scene script, and a rendered draft."""
    store = StoryArtifactStore(tmp_path / "store")
    store.create_story(story_id, created_at=_CREATED, story_text=STORY_TEXT)
    store.write_scene_script(story_id, _script())
    store.add_media(story_id, "animation.mp4", b"\x00fake-mp4\x01")
    return store


def _intake_story(tmp_path: Path, story_id: str = "s1") -> StoryArtifactStore:
    store = _rendered_story(tmp_path, story_id)
    store.write_intake_record(
        story_id,
        {
            "consent": {"is_guardian": True, "ai_processing": True, "human_review_ack": True},
            "provider_posture": {
                "provider_id": "anthropic:no-train-zdr",
                "no_training": True,
                "zero_retention": True,
            },
            "minimization_warnings": [],
        },
    )
    return store


# --- load_review_bundle -----------------------------------------------------


def test_load_bundle_surfaces_script_media_and_intake(tmp_path: Path) -> None:
    store = _intake_story(tmp_path)
    bundle = load_review_bundle(store, "s1")

    assert bundle.scene_script["title"] == EXAMPLE_SCENE_SCRIPT["title"]
    assert [p.name for p in bundle.media_paths] == ["animation.mp4"]
    assert bundle.intake_record is not None
    assert bundle.intake_record["provider_posture"]["no_training"] is True
    assert bundle.existing_review is None
    assert bundle.metadata.delivered is False


def test_load_bundle_missing_story_raises(tmp_path: Path) -> None:
    store = StoryArtifactStore(tmp_path / "store")
    with pytest.raises(StoryNotFoundError):
        load_review_bundle(store, "nope")


# --- approve ----------------------------------------------------------------


def test_approve_marks_delivered_and_records_decision(tmp_path: Path) -> None:
    store = _rendered_story(tmp_path)
    record = review_story(
        store, "s1", decision=ReviewDecision.APPROVED, reviewer="alex", clock=_clock
    )

    assert record.approved is True
    assert store.read_metadata("s1").delivered is True

    saved = store.read_review_record("s1")
    assert saved is not None
    assert saved["decision"] == "approved"
    assert saved["reviewer"] == "alex"
    assert saved["decided_at"] == _DECIDED.isoformat()


def test_approve_blocked_without_a_rendered_draft(tmp_path: Path) -> None:
    store = StoryArtifactStore(tmp_path / "store")
    store.create_story("s1", created_at=_CREATED, story_text=STORY_TEXT)
    store.write_scene_script("s1", _script())  # no media rendered

    with pytest.raises(ReviewError, match="no rendered draft"):
        review_story(store, "s1", decision=ReviewDecision.APPROVED, reviewer="alex")

    # Nothing was delivered and no decision was written.
    assert store.read_metadata("s1").delivered is False
    assert store.read_review_record("s1") is None


def test_approve_records_provider_posture_fingerprint(tmp_path: Path) -> None:
    store = _intake_story(tmp_path)
    record = review_story(
        store, "s1", decision=ReviewDecision.APPROVED, reviewer="alex", clock=_clock
    )
    assert record.reviewed["provider_posture"]["zero_retention"] is True
    assert record.reviewed["scene_count"] == len(EXAMPLE_SCENE_SCRIPT["scenes"])
    assert record.reviewed["media_files"] == ["animation.mp4"]


# --- reject -----------------------------------------------------------------


def test_reject_requires_a_reason(tmp_path: Path) -> None:
    store = _rendered_story(tmp_path)
    with pytest.raises(ReviewError, match="rejection must include a reason"):
        review_story(store, "s1", decision=ReviewDecision.REJECTED, reviewer="alex")


def test_reject_leaves_story_undelivered(tmp_path: Path) -> None:
    store = _rendered_story(tmp_path)
    record = review_story(
        store,
        "s1",
        decision=ReviewDecision.REJECTED,
        reviewer="alex",
        reason="scene 3 flashes too fast",
        clock=_clock,
    )

    assert record.approved is False
    assert store.read_metadata("s1").delivered is False
    saved = store.read_review_record("s1")
    assert saved is not None and saved["decision"] == "rejected"


def test_review_requires_a_reviewer(tmp_path: Path) -> None:
    store = _rendered_story(tmp_path)
    with pytest.raises(ReviewError, match="reviewer must be identified"):
        review_story(store, "s1", decision=ReviewDecision.APPROVED, reviewer="  ")


# --- privacy / audit --------------------------------------------------------


def test_review_record_holds_no_story_text(tmp_path: Path) -> None:
    store = _rendered_story(tmp_path)
    review_story(
        store, "s1", decision=ReviewDecision.APPROVED, reviewer="alex", clock=_clock
    )
    raw = (store.story_dir("s1") / "review.json").read_text(encoding="utf-8")
    assert "scared of the dark" not in raw
    assert STORY_TEXT not in raw


def test_review_record_is_swept_by_hard_delete(tmp_path: Path) -> None:
    store = _rendered_story(tmp_path)
    review_story(
        store, "s1", decision=ReviewDecision.APPROVED, reviewer="alex", clock=_clock
    )
    review_path = store.story_dir("s1") / "review.json"
    assert review_path.is_file()

    delete_story(store, "s1", purge_log=BackupPurgeLog(tmp_path / "purge.log"))
    assert not review_path.exists()
    assert store.artifact_paths("s1") == []


# --- retention interaction --------------------------------------------------


def test_approved_story_survives_retention_but_unreviewed_is_purged(tmp_path: Path) -> None:
    store = StoryArtifactStore(tmp_path / "store")
    for sid in ("approved", "ignored"):
        store.create_story(sid, created_at=_CREATED, story_text=STORY_TEXT)
        store.write_scene_script(sid, _script())
        store.add_media(sid, "animation.mp4", b"\x00mp4\x01")

    review_story(store, "approved", decision=ReviewDecision.APPROVED, reviewer="alex")

    # 40 days later, both are older than the 30-day window.
    now = _CREATED + timedelta(days=40)
    receipts = purge_undelivered_stories(
        store, now=now, purge_log=BackupPurgeLog(tmp_path / "purge.log")
    )

    purged = {r.story_id for r in receipts}
    assert purged == {"ignored"}
    assert store.exists("approved")
    assert not store.exists("ignored")


def test_bundle_reports_prior_decision(tmp_path: Path) -> None:
    store = _rendered_story(tmp_path)
    review_story(
        store, "s1", decision=ReviewDecision.APPROVED, reviewer="alex", clock=_clock
    )
    bundle = load_review_bundle(store, "s1")
    assert bundle.existing_review is not None
    assert bundle.existing_review["reviewer"] == "alex"
    # A round-trip through the store yields valid JSON.
    assert json.dumps(bundle.existing_review)
