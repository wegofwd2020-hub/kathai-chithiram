"""Tests for verifiable hard-delete + backup-purge cascade (KC-1)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kathai_chithiram.errors import DeletionError, StoryNotFoundError
from kathai_chithiram.storage import (
    BackupPurgeLog,
    StoryArtifactStore,
    delete_story,
)

_WHEN = datetime(2026, 6, 13, tzinfo=timezone.utc)
SECRET = "SENTINEL_RAW_STORY_TEXT_DO_NOT_LEAK"


def _seed(tmp_path: Path) -> tuple[StoryArtifactStore, BackupPurgeLog]:
    store = StoryArtifactStore(tmp_path / "stories")
    store.create_story("story-1", created_at=_WHEN, story_text=f"{SECRET} once upon a time")
    store.write_scene_script("story-1", {"schema_version": "1.0", "title": SECRET})
    store.add_media("story-1", "out.mp4", SECRET.encode("utf-8"))
    store.add_cache("story-1", "frames.bin", b"\x00")
    purge_log = BackupPurgeLog(tmp_path / "backup_purge.jsonl")
    return store, purge_log


def test_delete_removes_every_artifact(tmp_path: Path) -> None:
    store, purge_log = _seed(tmp_path)
    receipt = delete_story(store, "story-1", purge_log=purge_log, when=_WHEN)

    assert receipt.removed_file_count == 5
    assert store.exists("story-1") is False
    assert store.artifact_paths("story-1") == []
    assert not (store.story_dir("story-1")).exists()


def test_delete_sweeps_session_feedback(tmp_path: Path) -> None:
    # ADR-002 D5: the verifiable hard-delete must cover captured feedback too.
    store, purge_log = _seed(tmp_path)
    store.append_session_feedback(
        "story-1",
        {
            "goal_id": "goal-1",
            "story_id": "story-1",
            "prompt_level": "independent",
            "completed": True,
            "mood_checkin": 4,
            "recorded_at": _WHEN.isoformat(),
        },
    )
    assert (store.story_dir("story-1") / "feedback.jsonl").is_file()

    delete_story(store, "story-1", purge_log=purge_log, when=_WHEN)

    assert store.artifact_paths("story-1") == []
    assert not (store.story_dir("story-1")).exists()


def test_delete_leaves_no_tombstoned_raw_text(tmp_path: Path) -> None:
    store, purge_log = _seed(tmp_path)
    delete_story(store, "story-1", purge_log=purge_log, when=_WHEN)

    # Scan everything still under the store root + the purge log: the raw story
    # text (and its appearance in derived artifacts) must be completely gone.
    survivors = [p for p in store.root.rglob("*") if p.is_file()]
    assert survivors == []
    assert SECRET not in purge_log.path.read_text(encoding="utf-8")


def test_delete_cascades_to_backup_purge_log(tmp_path: Path) -> None:
    store, purge_log = _seed(tmp_path)
    receipt = delete_story(store, "story-1", purge_log=purge_log, when=_WHEN)

    assert receipt.backup_purge_logged is True
    assert purge_log.pending_story_ids() == ["story-1"]


def test_delete_missing_story_raises(tmp_path: Path) -> None:
    store, purge_log = _seed(tmp_path)
    with pytest.raises(StoryNotFoundError):
        delete_story(store, "ghost", purge_log=purge_log)


def test_delete_logs_without_raw_text(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    store, purge_log = _seed(tmp_path)
    with caplog.at_level(logging.INFO):
        delete_story(store, "story-1", purge_log=purge_log, when=_WHEN)
    assert "hard-delete complete" in caplog.text
    assert SECRET not in caplog.text


def test_partial_delete_is_reported_as_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, purge_log = _seed(tmp_path)

    # Simulate rmtree "succeeding" but leaving residue: the verification step
    # must convert that into a DeletionError rather than a silent pass.
    import kathai_chithiram.storage.deletion as deletion

    monkeypatch.setattr(deletion.shutil, "rmtree", lambda path: None)
    with pytest.raises(DeletionError, match="remained after deletion"):
        delete_story(store, "story-1", purge_log=purge_log, when=_WHEN)
