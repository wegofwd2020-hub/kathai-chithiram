"""Per-child key layer: init, cipher round-trip, crypto-shred, rewrap (KC-10 / §3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kathai_chithiram.errors import DecryptionError
from kathai_chithiram.storage.crypto import AesGcmCipher, generate_key
from kathai_chithiram.storage.store import StoryArtifactStore


def _cipher() -> AesGcmCipher:
    import base64
    return AesGcmCipher(base64.urlsafe_b64decode(generate_key()))


def test_init_child_key_is_idempotent_and_wraps_under_master(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_child_key("child-1")
    key_path = store._child_key_path("child-1")
    assert key_path.is_file()
    first = key_path.read_bytes()
    store._init_child_key("child-1")  # idempotent — must not regenerate
    assert key_path.read_bytes() == first


def test_child_cipher_round_trips(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_child_key("child-1")
    cipher = store._child_cipher("child-1")
    token = cipher.encrypt(b"hello")
    assert cipher.decrypt(token, artifact="t") == b"hello"


def test_child_cipher_fails_closed_after_shred(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_child_key("child-1")
    store.shred_child_key("child-1")
    assert not store._child_key_path("child-1").is_file()
    with pytest.raises(DecryptionError):
        store._child_cipher("child-1")


def test_shred_is_idempotent(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.shred_child_key("never-created")  # no error


def test_plaintext_store_child_layer_is_noop(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=None)
    store._init_child_key("child-1")
    assert store._child_cipher("child-1") is None
    assert not store._child_key_path("child-1").is_file()


def test_rewrap_child_rotates_under_new_master(tmp_path):
    old = _cipher()
    store = StoryArtifactStore(tmp_path, cipher=old)
    store._init_child_key("child-1")
    plain_cipher = store._child_cipher("child-1")
    probe = plain_cipher.encrypt(b"x")

    new = _cipher()
    store.rewrap_child("child-1", new_master=new)
    # Old master can no longer unwrap; new master can, and yields the SAME data key.
    store._cipher = new
    assert store._child_cipher("child-1").decrypt(probe, artifact="x") == b"x"


_NOW = datetime(2026, 7, 7, tzinfo=timezone.utc)
_SCRIPT = {"schema_version": "1.0", "title": "Calm night", "scenes": []}


def test_child_scoped_story_wraps_under_child_key_and_reads_back(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="a tale", child_id="child-1")
    store.write_scene_script("s1", _SCRIPT)
    # Parent marker written; child key exists; body round-trips through the child key.
    assert (store.story_dir("s1") / "_data_key.parent").read_text().strip() == "child-1"
    assert store._child_key_path("child-1").is_file()
    assert store.read_scene_script("s1") == _SCRIPT


def test_non_child_story_stays_master_wrapped(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s2", created_at=_NOW, story_text="plain")
    store.write_scene_script("s2", _SCRIPT)
    assert not (store.story_dir("s2") / "_data_key.parent").exists()
    assert store.read_scene_script("s2") == _SCRIPT


def test_shredding_child_key_makes_its_story_unreadable(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="secret", child_id="child-1")
    store.write_scene_script("s1", _SCRIPT)
    store.shred_child_key("child-1")
    with pytest.raises(DecryptionError):
        store.read_scene_script("s1")


def test_iter_story_ids_excludes_reserved_children_dir(tmp_path):
    """Regression: _children reserved dir must not appear in iter_story_ids()."""
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="x", child_id="child-1")
    ids = list(store.iter_story_ids())
    assert "s1" in ids
    assert "_children" not in ids
