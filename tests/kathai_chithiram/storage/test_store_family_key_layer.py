"""Per-family key layer: init, cipher round-trip, crypto-shred, rewrap (§3)."""

from __future__ import annotations

import base64

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
