"""Tests for the at-rest encryption seam (KC-5)."""

from __future__ import annotations

import base64

import pytest

from kathai_chithiram.errors import DecryptionError, EncryptionKeyError
from kathai_chithiram.storage.crypto import (
    STORAGE_KEY_ENV,
    AesGcmCipher,
    generate_key,
    load_cipher_from_env,
)


def _cipher() -> AesGcmCipher:
    return AesGcmCipher(base64.urlsafe_b64decode(generate_key()))


def test_roundtrip() -> None:
    cipher = _cipher()
    plaintext = b"Robin is scared of the dark."
    assert cipher.decrypt(cipher.encrypt(plaintext), artifact="x") == plaintext


def test_ciphertext_is_not_plaintext_and_nonce_randomized() -> None:
    cipher = _cipher()
    data = b"a calm story"
    token1 = cipher.encrypt(data)
    token2 = cipher.encrypt(data)
    assert data not in token1
    # Fresh random nonce per call -> identical plaintext yields distinct tokens.
    assert token1 != token2


def test_tampered_ciphertext_fails_closed() -> None:
    cipher = _cipher()
    token = bytearray(cipher.encrypt(b"secret"))
    token[-1] ^= 0x01  # flip a bit in the ciphertext
    with pytest.raises(DecryptionError, match="report.mp4"):
        cipher.decrypt(bytes(token), artifact="report.mp4")


def test_wrong_key_fails_closed() -> None:
    token = _cipher().encrypt(b"secret")
    other = _cipher()
    with pytest.raises(DecryptionError):
        other.decrypt(token, artifact="x")


def test_truncated_token_fails_closed() -> None:
    with pytest.raises(DecryptionError):
        _cipher().decrypt(b"short", artifact="x")


def test_key_must_be_32_bytes() -> None:
    with pytest.raises(EncryptionKeyError, match="32 bytes"):
        AesGcmCipher(b"too-short")


def test_load_cipher_absent_returns_none() -> None:
    assert load_cipher_from_env({}) is None
    assert load_cipher_from_env({STORAGE_KEY_ENV: ""}) is None


def test_load_cipher_builds_from_env() -> None:
    cipher = load_cipher_from_env({STORAGE_KEY_ENV: generate_key()})
    assert cipher is not None
    assert cipher.decrypt(cipher.encrypt(b"ok"), artifact="x") == b"ok"


def test_load_cipher_rejects_bad_base64() -> None:
    with pytest.raises(EncryptionKeyError, match="base64"):
        load_cipher_from_env({STORAGE_KEY_ENV: "not valid base64 !!!"})


def test_load_cipher_rejects_wrong_length_key() -> None:
    short = base64.urlsafe_b64encode(b"0123456789").decode("ascii")  # 10 bytes
    with pytest.raises(EncryptionKeyError, match="32 bytes"):
        load_cipher_from_env({STORAGE_KEY_ENV: short})
