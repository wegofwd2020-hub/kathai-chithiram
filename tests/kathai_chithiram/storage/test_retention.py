"""Tests for the 30-day undelivered-story retention sweep (KC-1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from kathai_chithiram.storage import (
    BackupPurgeLog,
    StoryArtifactStore,
    purge_undelivered_stories,
)

_NOW = datetime(2026, 6, 13, tzinfo=timezone.utc)


def _seed(tmp_path: Path) -> tuple[StoryArtifactStore, BackupPurgeLog]:
    store = StoryArtifactStore(tmp_path / "stories")
    purge_log = BackupPurgeLog(tmp_path / "backup_purge.jsonl")

    # Old + undelivered -> should be purged.
    store.create_story("old-undelivered", created_at=_NOW - timedelta(days=40), story_text="a")
    # Old + delivered -> kept (parent chose to keep / already delivered).
    store.create_story("old-delivered", created_at=_NOW - timedelta(days=40), story_text="b")
    store.mark_delivered("old-delivered")
    # Recent + undelivered -> kept (within retention window).
    store.create_story("recent-undelivered", created_at=_NOW - timedelta(days=5), story_text="c")
    return store, purge_log


def test_purges_only_old_undelivered(tmp_path: Path) -> None:
    store, purge_log = _seed(tmp_path)
    receipts = purge_undelivered_stories(store, now=_NOW, purge_log=purge_log)

    assert [r.story_id for r in receipts] == ["old-undelivered"]
    assert store.exists("old-undelivered") is False
    assert store.exists("old-delivered") is True
    assert store.exists("recent-undelivered") is True
    assert purge_log.pending_story_ids() == ["old-undelivered"]


def test_boundary_exactly_at_threshold_is_kept(tmp_path: Path) -> None:
    store = StoryArtifactStore(tmp_path / "stories")
    purge_log = BackupPurgeLog(tmp_path / "backup_purge.jsonl")
    store.create_story("edge", created_at=_NOW - timedelta(days=30), story_text="x")

    receipts = purge_undelivered_stories(store, now=_NOW, purge_log=purge_log)
    # created_at == cutoff is not strictly older than the window, so it stays.
    assert receipts == []
    assert store.exists("edge") is True


def test_custom_max_age(tmp_path: Path) -> None:
    store, purge_log = _seed(tmp_path)
    receipts = purge_undelivered_stories(
        store, now=_NOW, purge_log=purge_log, max_age=timedelta(days=3)
    )
    # With a 3-day window, the recent undelivered story is now old enough too.
    assert {r.story_id for r in receipts} == {"old-undelivered", "recent-undelivered"}
