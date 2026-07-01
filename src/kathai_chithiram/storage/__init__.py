"""Storage for a story's artifacts and their lifecycle.

A story owns a set of derived artifacts — raw text, the derived scene script,
rendered media, and caches — all scoped to one family and sharing that story's
retention and deletion rules (PRIVACY.md §4/§5). This package models where those
artifacts live (:class:`StoryArtifactStore`), how to hard-delete them verifiably
(:func:`delete_story`), the default 30-day retention sweep
(:func:`purge_undelivered_stories`), and the at-rest encryption seam
(:class:`StorageCipher`, KC-5).
"""

from __future__ import annotations

from kathai_chithiram.storage.crypto import (
    STORAGE_KEY_ENV,
    AesGcmCipher,
    StorageCipher,
    generate_key,
    load_cipher_from_env,
)
from kathai_chithiram.storage.deletion import (
    BackupPurgeLog,
    DeletionReceipt,
    delete_story,
)
from kathai_chithiram.storage.retention import (
    DEFAULT_RETENTION,
    purge_undelivered_stories,
)
from kathai_chithiram.storage.store import StoryArtifactStore, StoryMetadata

__all__ = [
    "DEFAULT_RETENTION",
    "STORAGE_KEY_ENV",
    "AesGcmCipher",
    "BackupPurgeLog",
    "DeletionReceipt",
    "StorageCipher",
    "StoryArtifactStore",
    "StoryMetadata",
    "delete_story",
    "generate_key",
    "load_cipher_from_env",
    "purge_undelivered_stories",
]
