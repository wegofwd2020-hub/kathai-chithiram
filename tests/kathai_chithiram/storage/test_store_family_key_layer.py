"""Per-family key layer: init, cipher round-trip, crypto-shred, rewrap (§3)."""

from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest

from kathai_chithiram.errors import DecryptionError
from kathai_chithiram.storage.crypto import AesGcmCipher, generate_key
from kathai_chithiram.storage.store import StoryArtifactStore


def _cipher() -> AesGcmCipher:
    return AesGcmCipher(base64.urlsafe_b64decode(generate_key()))


def test_init_family_key_is_idempotent_and_wraps_under_master(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_family_key("fam-1")
    key_path = store._family_key_path("fam-1")
    assert key_path.is_file()
    first = key_path.read_bytes()
    store._init_family_key("fam-1")  # idempotent — must not regenerate
    assert key_path.read_bytes() == first


def test_family_cipher_round_trips(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_family_key("fam-1")
    cipher = store._family_cipher("fam-1")
    token = cipher.encrypt(b"hello")
    assert cipher.decrypt(token, artifact="t") == b"hello"


def test_family_cipher_fails_closed_after_shred(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_family_key("fam-1")
    store.shred_family_key("fam-1")
    assert not store._family_key_path("fam-1").is_file()
    with pytest.raises(DecryptionError):
        store._family_cipher("fam-1")


def test_shred_family_is_idempotent(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.shred_family_key("never-created")  # no error


def test_plaintext_store_family_layer_is_noop(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=None)
    store._init_family_key("fam-1")
    assert store._family_cipher("fam-1") is None
    assert not store._family_key_path("fam-1").is_file()


def test_rewrap_family_rotates_under_new_master(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_family_key("fam-1")
    probe = store._family_cipher("fam-1").encrypt(b"x")
    new = _cipher()
    store.rewrap_family("fam-1", new_master=new)
    store._cipher = new
    assert store._family_cipher("fam-1").decrypt(probe, artifact="x") == b"x"


_NOW = datetime(2026, 7, 7, tzinfo=timezone.utc)
_SCRIPT = {"schema_version": "1.0", "title": "Calm night", "scenes": []}


def test_family_scoped_child_key_wraps_under_family_key(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="a tale",
                       child_id="kid-1", family_id="fam-1")
    store.write_scene_script("s1", _SCRIPT)
    # Family marker written in the child dir; family key exists; body round-trips.
    child_dir = store._child_key_path("kid-1").parent
    assert (child_dir / "_family.parent").read_text().strip() == "fam-1"
    assert store._family_key_path("fam-1").is_file()
    assert store.read_scene_script("s1") == _SCRIPT


def test_legacy_child_key_without_family_stays_master_wrapped(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    # child_id but NO family_id → PR #95 behaviour: child key wrapped under master.
    store.create_story("s2", created_at=_NOW, story_text="plain", child_id="kid-2")
    store.write_scene_script("s2", _SCRIPT)
    assert not (store._child_key_path("kid-2").parent / "_family.parent").exists()
    assert store.read_scene_script("s2") == _SCRIPT


def test_shredding_family_key_makes_child_scoped_story_unreadable(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="secret",
                       child_id="kid-1", family_id="fam-1")
    store.write_scene_script("s1", _SCRIPT)
    store.shred_family_key("fam-1")
    with pytest.raises(DecryptionError):
        store.read_scene_script("s1")  # story key ← child key ← shredded family key


def test_iter_story_ids_excludes_reserved_dirs(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="x",
                       child_id="kid-1", family_id="fam-1")
    ids = list(store.iter_story_ids())
    assert "s1" in ids
    assert "_children" not in ids
    assert "_families" not in ids


def test_rewrap_child_is_noop_for_family_wrapped_child(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="x",
                       child_id="kid-1", family_id="fam-1")
    store.write_scene_script("s1", _SCRIPT)
    before = store._child_key_path("kid-1").read_bytes()
    store.rewrap_child("kid-1", new_master=_cipher())  # family-wrapped → no-op
    assert store._child_key_path("kid-1").read_bytes() == before
    assert store.read_scene_script("s1") == _SCRIPT  # story still readable (key untouched)
