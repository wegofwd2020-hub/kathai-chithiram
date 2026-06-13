"""Tests for the story artifact store (KC-1 foundation)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from kathai_chithiram.errors import StoryNotFoundError
from kathai_chithiram.storage import StoryArtifactStore

_CREATED = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _store(tmp_path: Path) -> StoryArtifactStore:
    return StoryArtifactStore(tmp_path / "stories")


def test_create_and_enumerate_artifacts(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_story("story-1", created_at=_CREATED, story_text="A calm story.")
    store.write_scene_script("story-1", {"schema_version": "1.0", "scenes": []})
    store.add_media("story-1", "out.mp4", b"\x00\x01")
    store.add_cache("story-1", "frames.bin", b"\x02")

    names = {p.name for p in store.artifact_paths("story-1")}
    assert names == {"story.txt", "scene_script.json", "_meta.json", "out.mp4", "frames.bin"}


def test_metadata_roundtrip_and_mark_delivered(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_story("story-1", created_at=_CREATED, story_text="hi")
    meta = store.read_metadata("story-1")
    assert meta.created_at == _CREATED
    assert meta.delivered is False

    updated = store.mark_delivered("story-1")
    assert updated.delivered is True
    assert store.read_metadata("story-1").delivered is True


def test_metadata_holds_no_story_text(tmp_path: Path) -> None:
    store = _store(tmp_path)
    secret = "SENTINEL_RAW_STORY_TEXT"
    store.create_story("story-1", created_at=_CREATED, story_text=f"{secret} here")
    meta_file = store.story_dir("story-1") / "_meta.json"
    assert secret not in meta_file.read_text(encoding="utf-8")


def test_iter_story_ids(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_story("a", created_at=_CREATED, story_text="x")
    store.create_story("b", created_at=_CREATED, story_text="y")
    assert list(store.iter_story_ids()) == ["a", "b"]


def test_missing_story_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.exists("nope") is False
    with pytest.raises(StoryNotFoundError):
        store.read_metadata("nope")
    with pytest.raises(StoryNotFoundError):
        store.write_scene_script("nope", {})


@pytest.mark.parametrize("bad_id", ["../evil", "a/b", "..", "", "a b"])
def test_unsafe_story_id_rejected(tmp_path: Path, bad_id: str) -> None:
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="story_id"):
        store.story_dir(bad_id)


@pytest.mark.parametrize("bad_name", ["../evil", "a/b", "..", "."])
def test_unsafe_media_filename_rejected(tmp_path: Path, bad_name: str) -> None:
    store = _store(tmp_path)
    store.create_story("story-1", created_at=_CREATED, story_text="x")
    with pytest.raises(ValueError, match="filename"):
        store.add_media("story-1", bad_name, b"data")
