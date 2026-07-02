"""Tests for envelope encryption with per-story keys (KC-10, crypto-shredding).

These exercise the store's envelope layer on top of the KC-5 at-rest cipher:
artifact bodies are encrypted under a per-story data key that is stored only
*wrapped* by the master, so destroying the wrapped key (on hard-delete) renders
the story unrecoverable even from a stale ciphertext backup, and master-key
rotation re-wraps that key without re-encrypting the bodies.
"""

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
_WRAPPED_KEY_FILE = "_data_key.wrapped"
STORY_TEXT = "Robin is scared of the dark."
SCRIPT = {"schema_version": "1.0", "title": "Calm night", "scenes": []}


def _cipher() -> AesGcmCipher:
    return AesGcmCipher(base64.urlsafe_b64decode(generate_key()))


def test_new_story_stores_a_wrapped_per_story_key(tmp_path: Path) -> None:
    master = _cipher()
    store = StoryArtifactStore(tmp_path / "store", cipher=master)
    store.create_story("s1", created_at=_CREATED, story_text=STORY_TEXT)

    key_path = store.story_dir("s1") / _WRAPPED_KEY_FILE
    assert key_path.is_file()
    # The wrapped file unwraps (under the master) to a 32-byte data key.
    data_key = master.decrypt(key_path.read_bytes(), artifact=_WRAPPED_KEY_FILE)
    assert len(data_key) == 32
    # It is swept by a hard-delete like every other artifact.
    assert key_path in store.artifact_paths("s1")


def test_each_story_gets_a_distinct_data_key(tmp_path: Path) -> None:
    master = _cipher()
    store = StoryArtifactStore(tmp_path / "store", cipher=master)
    store.create_story("s1", created_at=_CREATED, story_text=STORY_TEXT)
    store.create_story("s2", created_at=_CREATED, story_text=STORY_TEXT)

    key1 = master.decrypt(
        (store.story_dir("s1") / _WRAPPED_KEY_FILE).read_bytes(), artifact="k"
    )
    key2 = master.decrypt(
        (store.story_dir("s2") / _WRAPPED_KEY_FILE).read_bytes(), artifact="k"
    )
    assert key1 != key2


def test_bodies_are_not_encrypted_under_the_master_directly(tmp_path: Path) -> None:
    master = _cipher()
    store = StoryArtifactStore(tmp_path / "store", cipher=master)
    store.create_story("s1", created_at=_CREATED, story_text=STORY_TEXT)

    body = (store.story_dir("s1") / "story.txt").read_bytes()
    # The master cannot read the body: it is under the per-story data key, not
    # the master. This is what makes crypto-shredding the wrapped key sufficient.
    with pytest.raises(DecryptionError):
        master.decrypt(body, artifact="story.txt")


def test_hard_delete_crypto_shreds_the_story(tmp_path: Path) -> None:
    master = _cipher()
    store = StoryArtifactStore(tmp_path / "store", cipher=master)
    store.create_story("s1", created_at=_CREATED, story_text=STORY_TEXT)
    story_dir = store.story_dir("s1")

    # Recover the raw ciphertext body as a stale backup would preserve it.
    recovered_body = (story_dir / "story.txt").read_bytes()

    delete_story(store, "s1", purge_log=BackupPurgeLog(tmp_path / "purge.log"))
    assert not (story_dir / _WRAPPED_KEY_FILE).exists()

    # Even holding the master key AND the recovered ciphertext, the plaintext is
    # unrecoverable: the only wrapped copy of the data key was destroyed.
    with pytest.raises(DecryptionError):
        master.decrypt(recovered_body, artifact="story.txt")


def test_tampered_wrapped_key_fails_closed(tmp_path: Path) -> None:
    master = _cipher()
    store = StoryArtifactStore(tmp_path / "store", cipher=master)
    store.create_story("s1", created_at=_CREATED, story_text=STORY_TEXT)
    store.write_scene_script("s1", SCRIPT)

    key_path = store.story_dir("s1") / _WRAPPED_KEY_FILE
    tampered = bytearray(key_path.read_bytes())
    tampered[-1] ^= 0x01
    key_path.write_bytes(bytes(tampered))

    # Any read must resolve the per-story cipher first; unwrapping fails closed.
    with pytest.raises(DecryptionError):
        store.read_scene_script("s1")


def test_rewrap_rotates_master_without_touching_bodies(tmp_path: Path) -> None:
    old, new = _cipher(), _cipher()
    root = tmp_path / "store"
    store = StoryArtifactStore(root, cipher=old)
    store.create_story("s1", created_at=_CREATED, story_text=STORY_TEXT)
    store.write_scene_script("s1", SCRIPT)
    story_dir = store.story_dir("s1")

    body_before = (story_dir / "scene_script.json").read_bytes()
    wrapped_before = (story_dir / _WRAPPED_KEY_FILE).read_bytes()

    store.rewrap_story("s1", new_master=new)

    # Only the (small) wrapped key changed; the artifact body was not re-encrypted.
    assert (story_dir / "scene_script.json").read_bytes() == body_before
    assert (story_dir / _WRAPPED_KEY_FILE).read_bytes() != wrapped_before

    # The new master can read the story; the old master no longer can.
    assert StoryArtifactStore(root, cipher=new).read_scene_script("s1") == SCRIPT
    with pytest.raises(DecryptionError):
        StoryArtifactStore(root, cipher=old).read_scene_script("s1")


def test_rewrap_is_noop_without_a_per_story_key(tmp_path: Path) -> None:
    # A plaintext store has no data key to rotate — rewrap does nothing, no raise.
    plain = StoryArtifactStore(tmp_path / "plain")
    plain.create_story("s1", created_at=_CREATED, story_text=STORY_TEXT)
    plain.rewrap_story("s1", new_master=_cipher())
    assert not (plain.story_dir("s1") / _WRAPPED_KEY_FILE).exists()


def test_legacy_master_encrypted_story_still_reads(tmp_path: Path) -> None:
    """A KC-5 story (bodies under the master, no wrapped key) still round-trips."""
    master = _cipher()
    root = tmp_path / "store"
    story_dir = root / "legacy"
    story_dir.mkdir(parents=True)

    payload = json.dumps(SCRIPT, ensure_ascii=False, indent=2).encode("utf-8")
    (story_dir / "scene_script.json").write_bytes(master.encrypt(payload))
    (story_dir / "_meta.json").write_text(
        json.dumps({"created_at": _CREATED.isoformat(), "delivered": False}),
        encoding="utf-8",
    )

    store = StoryArtifactStore(root, cipher=master)
    assert not (story_dir / _WRAPPED_KEY_FILE).exists()
    # Falls back to the master cipher for a story with no wrapped key.
    assert store.read_scene_script("legacy") == SCRIPT

    # A new write to the legacy story stays consistent (also under the master).
    store.write_review_record("legacy", {"decision": "approved", "reviewer": "alex"})
    assert not (story_dir / _WRAPPED_KEY_FILE).exists()
    assert store.read_review_record("legacy") == {
        "decision": "approved",
        "reviewer": "alex",
    }
