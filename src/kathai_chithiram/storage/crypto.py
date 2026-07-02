"""At-rest encryption seam for stored artifacts (KC-5, PRIVACY.md §7).

The store persists special-category child data (a parent's story and everything
derived from it). This module provides the cipher that encrypts those artifacts
on disk. It is a thin, provider-agnostic seam — like ``wegofwd-llm`` for the LLM
— so the store depends on the :class:`StorageCipher` interface, not a concrete
backend.

Design:

* :class:`AesGcmCipher` uses AES-256-GCM (authenticated encryption): each call
  gets a fresh random nonce, and the stored token is ``nonce || ciphertext``.
  Authentication means a tampered or truncated token fails to decrypt rather
  than returning garbage.
* The key is supplied from configuration (:data:`STORAGE_KEY_ENV`), never
  committed, and is distinct from the LLM provider key. If no key is configured,
  :func:`load_cipher_from_env` returns ``None`` and the store falls back to its
  documented plaintext behaviour — encryption is opt-in but is required for any
  deployment that persists real data.
* The ``cryptography`` backend is imported lazily so a deployment that does not
  enable encryption need not install the ``[encryption]`` extra.

Scope: this covers **at rest** only. The "in transit" half of PRIVACY.md §7 is a
separate concern for whenever a network boundary exists.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from kathai_chithiram.errors import DecryptionError, EncryptionKeyError

__all__ = [
    "DATA_KEY_BYTES",
    "STORAGE_KEY_ENV",
    "AesGcmCipher",
    "StorageCipher",
    "generate_data_key",
    "generate_key",
    "load_cipher_from_env",
    "unwrap_data_key",
    "wrap_data_key",
]

#: Environment variable holding the base64-encoded 32-byte storage key.
STORAGE_KEY_ENV = "KC_STORAGE_KEY"

_KEY_BYTES = 32  # AES-256
_NONCE_BYTES = 12  # GCM standard nonce length

#: Length of a per-story data key (AES-256), for envelope encryption (KC-10).
DATA_KEY_BYTES = _KEY_BYTES


@runtime_checkable
class StorageCipher(Protocol):
    """Authenticated encryption for a single stored artifact's bytes."""

    def encrypt(self, plaintext: bytes) -> bytes:
        """Return an authenticated ciphertext token for ``plaintext``."""
        ...

    def decrypt(self, token: bytes, *, artifact: str) -> bytes:
        """Return the plaintext for ``token``, or raise :class:`DecryptionError`.

        Args:
            token: The stored ciphertext token.
            artifact: A safe label for the artifact (e.g. its file name), used in
                the error if decryption fails. No secret or story content.
        """
        ...


class AesGcmCipher:
    """AES-256-GCM cipher; a stored token is ``nonce || ciphertext``.

    Args:
        key: A 32-byte AES-256 key.

    Raises:
        EncryptionKeyError: If the key is not exactly 32 bytes.
    """

    def __init__(self, key: bytes) -> None:
        if len(key) != _KEY_BYTES:
            raise EncryptionKeyError(f"key must be {_KEY_BYTES} bytes, got {len(key)}")
        # Imported lazily so the store works without the [encryption] extra when
        # no key is configured.
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        self._aead = AESGCM(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        """Return ``nonce || ciphertext`` with a fresh random nonce."""
        nonce = os.urandom(_NONCE_BYTES)
        return nonce + self._aead.encrypt(nonce, plaintext, None)

    def decrypt(self, token: bytes, *, artifact: str) -> bytes:
        """Authenticate and decrypt ``token``; fail closed on any error.

        Raises:
            DecryptionError: If the token is too short, corrupt, tampered with,
                or was written under a different key.
        """
        from cryptography.exceptions import InvalidTag

        if len(token) < _NONCE_BYTES:
            raise DecryptionError(artifact)
        nonce, ciphertext = token[:_NONCE_BYTES], token[_NONCE_BYTES:]
        try:
            return self._aead.decrypt(nonce, ciphertext, None)
        except InvalidTag as exc:
            raise DecryptionError(artifact) from exc


def generate_data_key() -> bytes:
    """Return a fresh 32-byte per-story data key for envelope encryption (KC-10).

    Unlike :func:`generate_key`, this returns raw key bytes (not a base64 string):
    a data key is never configured by a human — it is generated per story, wrapped
    under the master key with :func:`wrap_data_key`, and only ever stored wrapped.

    Returns:
        32 cryptographically-random bytes suitable for :class:`AesGcmCipher`.
    """
    return os.urandom(_KEY_BYTES)


def wrap_data_key(master: StorageCipher, data_key: bytes) -> bytes:
    """Wrap a per-story ``data_key`` under the ``master`` cipher (envelope encryption).

    The returned token is authenticated ciphertext (KC-10): destroying it renders
    the story's artifacts unrecoverable even if their ciphertext bytes survive in a
    stale backup (crypto-shredding, DPIA R5).

    Args:
        master: The master cipher (from :data:`STORAGE_KEY_ENV`) that wraps keys.
        data_key: The 32-byte per-story data key to wrap.

    Returns:
        The wrapped (encrypted) data key.

    Raises:
        EncryptionKeyError: If ``data_key`` is not exactly 32 bytes.
    """
    if len(data_key) != _KEY_BYTES:
        raise EncryptionKeyError(f"data key must be {_KEY_BYTES} bytes, got {len(data_key)}")
    return master.encrypt(data_key)


def unwrap_data_key(
    master: StorageCipher, wrapped: bytes, *, artifact: str
) -> AesGcmCipher:
    """Unwrap a wrapped data key and return the per-story artifact cipher.

    Fails closed: a tampered wrapped key, or one wrapped under a different master,
    raises :class:`DecryptionError` rather than yielding a usable cipher.

    Args:
        master: The master cipher that wrapped the key.
        wrapped: The wrapped data-key token from :func:`wrap_data_key`.
        artifact: A safe label for the wrapped-key artifact, used in the error if
            unwrapping fails. No key material or story content.

    Returns:
        An :class:`AesGcmCipher` bound to the unwrapped per-story data key.

    Raises:
        DecryptionError: If the wrapped key cannot be authenticated/decrypted.
        EncryptionKeyError: If the unwrapped material is not a valid 32-byte key.
    """
    data_key = master.decrypt(wrapped, artifact=artifact)
    return AesGcmCipher(data_key)


def generate_key() -> str:
    """Return a fresh base64 key string suitable for :data:`STORAGE_KEY_ENV`.

    Returns:
        A URL-safe base64 encoding of 32 random bytes. Store it as a secret; do
        not commit it.
    """
    return base64.urlsafe_b64encode(os.urandom(_KEY_BYTES)).decode("ascii")


def load_cipher_from_env(env: Mapping[str, str] | None = None) -> StorageCipher | None:
    """Build the storage cipher from configuration, or ``None`` if unconfigured.

    Args:
        env: Environment mapping to read (defaults to ``os.environ``).

    Returns:
        An :class:`AesGcmCipher` when :data:`STORAGE_KEY_ENV` is set, else
        ``None`` (the store then writes plaintext — see module docstring).

    Raises:
        EncryptionKeyError: If the key is set but is not valid base64 or is the
            wrong length.
    """
    source = os.environ if env is None else env
    raw = source.get(STORAGE_KEY_ENV)
    if not raw:
        return None
    try:
        key = base64.urlsafe_b64decode(raw)
    except (ValueError, TypeError) as exc:
        raise EncryptionKeyError(f"{STORAGE_KEY_ENV} is not valid base64") from exc
    return AesGcmCipher(key)
