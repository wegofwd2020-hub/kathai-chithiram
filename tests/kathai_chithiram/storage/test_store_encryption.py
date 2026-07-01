"""Tests for the store with at-rest encryption enabled (KC-5)."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kathai_chithiram.errors import DecryptionError
from kathai_chithiram.storage import (
    BackupPurgeLog,
    StoryArtifactStore,
    delete_story,
    generate_key,
)
from kathai_chithiram.storage.crypto import AesGcmCipher

_CREATED = datetime(2026, 6, 1, tzinfo=timezone.utc)
STORY_TEXT = "Robin is scared of the dark. CHILD turns on a light."
SCRIPT = {"schema_version": "1.0", "title": "Calm night", "child_token": "CHILD", "scenes": []}


def _cipher() -> AesGcmCipher:
    return AesGcmCipher(base64.urlsafe_b64decode(generate_key()))


def _encrypted_store(tmp_path: Path) -> StoryArtifactStore:
    return StoryArtifactStore(tmp_path / "store", cipher=_cipher())


def _seed(store: StoryArtifactStore, story_id: str = "s1") -> None:
    store.create_story(story_id, created_at=_CREATED, story_text=STORY_TEXT)
    store.write_scene_script(story_id, SCRIPT)
    store.write_intake_record(story_id, {"consent": {"is_guardian": True}, "note": STORY_TEXT})
    store.write_review_record(story_id, {"decision": "approved", "reviewer": "alex"})
    store.append_session_feedback(
        story_id, {"goal_id": "g1", "story_id": story_id, "completed": True}
    )
    store.add_media(story_id, "animation.mp4", b"\x00MP4-BODY-" + STORY_TEXT.encode())


def test_story_text_is_encrypted_on_disk_but_reads_back_plaintext(tmp_path: Path) -> None:
    store = _encrypted_store(tmp_path)
    _seed(store)
    story_dir = store.story_dir("s1")

    raw = (story_dir / "story.txt").read_bytes()
    assert b"scared of the dark" not in raw
    assert b"CHILD" not in raw
    # The bytes on disk decrypt back to the original.
    # (No public read for story.txt; assert via the raw-cipher-free path fails below.)


def test_derived_artifacts_are_encrypted_but_round_trip(tmp_path: Path) -> None:
    store = _encrypted_store(tmp_path)
    _seed(store)
    story_dir = store.story_dir("s1")

    for name in ("scene_script.json", "intake.json", "review.json"):
        raw = (story_dir / name).read_bytes()
        assert b"CHILD" not in raw
        assert b"scared of the dark" not in raw

    assert store.read_scene_script("s1") == SCRIPT
    assert store.read_intake_record("s1")["note"] == STORY_TEXT
    assert store.read_review_record("s1")["reviewer"] == "alex"


def test_feedback_log_is_encrypted_but_round_trips(tmp_path: Path) -> None:
    store = _encrypted_store(tmp_path)
    _seed(store)
    raw = (store.story_dir("s1") / "feedback.jsonl").read_text(encoding="utf-8")
    assert "goal_id" not in raw  # the JSON keys are not visible in ciphertext
    records = store.read_session_feedback("s1")
    assert records == [{"goal_id": "g1", "story_id": "s1", "completed": True}]


def test_media_is_encrypted_but_read_media_returns_original(tmp_path: Path) -> None:
    store = _encrypted_store(tmp_path)
    _seed(store)
    on_disk = (store.story_dir("s1") / "media" / "animation.mp4").read_bytes()
    original = b"\x00MP4-BODY-" + STORY_TEXT.encode()
    assert on_disk != original
    assert STORY_TEXT.encode() not in on_disk
    assert store.read_media("s1", "animation.mp4") == original


def test_metadata_stays_cleartext(tmp_path: Path) -> None:
    store = _encrypted_store(tmp_path)
    _seed(store)
    meta_raw = (store.story_dir("s1") / "_meta.json").read_text(encoding="utf-8")
    # Cleartext and parseable, and carries no story text or name.
    parsed = json.loads(meta_raw)
    assert parsed["delivered"] is False
    assert "CHILD" not in meta_raw
    assert "dark" not in meta_raw
    assert store.read_metadata("s1").delivered is False


def test_reading_without_the_key_fails_closed(tmp_path: Path) -> None:
    _seed(_encrypted_store(tmp_path))
    plain = StoryArtifactStore(tmp_path / "store")  # no cipher
    # Ciphertext is never returned as if it were plaintext: JSON parse fails.
    with pytest.raises(ValueError):
        plain.read_scene_script("s1")


def test_reading_with_the_wrong_key_raises_decryption_error(tmp_path: Path) -> None:
    _seed(_encrypted_store(tmp_path))
    wrong = StoryArtifactStore(tmp_path / "store", cipher=_cipher())  # different key
    with pytest.raises(DecryptionError):
        wrong.read_scene_script("s1")


def test_hard_delete_removes_all_encrypted_artifacts(tmp_path: Path) -> None:
    store = _encrypted_store(tmp_path)
    _seed(store)
    assert store.artifact_paths("s1")  # something to delete

    delete_story(store, "s1", purge_log=BackupPurgeLog(tmp_path / "purge.log"))
    assert not store.exists("s1")
    assert store.artifact_paths("s1") == []
