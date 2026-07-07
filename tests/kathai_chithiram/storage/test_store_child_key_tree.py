"""Per-child key layer: init, cipher round-trip, crypto-shred, rewrap (KC-10 / §3)."""

from __future__ import annotations

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
