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


def test_write_intake_record(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_story("story-1", created_at=_CREATED, story_text="hi")
    store.write_intake_record("story-1", {"consent": {"is_guardian": True}})

    intake = store.story_dir("story-1") / "intake.json"
    assert intake.is_file()
    # It is enumerated as an artifact (so a hard-delete sweeps it too).
    assert intake in store.artifact_paths("story-1")


def test_write_intake_record_requires_existing_story(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(StoryNotFoundError):
        store.write_intake_record("missing", {"consent": {}})


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


def test_read_scene_script_roundtrip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_story("s1", created_at=_CREATED, story_text="hi")
    script = {"schema_version": "1.0", "title": "Calm", "scenes": []}
    store.write_scene_script("s1", script)
    assert store.read_scene_script("s1") == script


def test_read_scene_script_missing_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_story("s1", created_at=_CREATED, story_text="hi")  # no scene script yet
    with pytest.raises(StoryNotFoundError):
        store.read_scene_script("s1")


def test_read_intake_record_absent_is_none(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_story("s1", created_at=_CREATED, story_text="hi")
    assert store.read_intake_record("s1") is None


def test_review_record_roundtrip_and_enumerated(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_story("s1", created_at=_CREATED, story_text="hi")
    assert store.read_review_record("s1") is None

    store.write_review_record("s1", {"decision": "approved", "reviewer": "alex"})
    assert store.read_review_record("s1") == {"decision": "approved", "reviewer": "alex"}
    # Enumerated as an artifact, so a hard-delete sweeps it too.
    assert store.story_dir("s1") / "review.json" in store.artifact_paths("s1")


def test_media_paths_lists_rendered_files(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_story("s1", created_at=_CREATED, story_text="hi")
    assert store.media_paths("s1") == []
    store.add_media("s1", "animation.mp4", b"\x00")
    assert [p.name for p in store.media_paths("s1")] == ["animation.mp4"]


def test_progress_suggestions_log_roundtrip_and_enumerated(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_story("s1", created_at=_CREATED, story_text="hi")
    assert store.read_progress_suggestions("s1") == []

    store.append_progress_suggestion("s1", {"kind": "suggestion", "suggestion_id": "sg1"})
    store.append_progress_suggestion("s1", {"kind": "decision", "suggestion_id": "sg1"})
    records = store.read_progress_suggestions("s1")
    assert [r["kind"] for r in records] == ["suggestion", "decision"]
    # Enumerated as an artifact, so a hard-delete sweeps it too.
    assert store.story_dir("s1") / "suggestions.jsonl" in store.artifact_paths("s1")
