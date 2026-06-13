"""Storage for a story's artifacts and their lifecycle.

A story owns a set of derived artifacts — raw text, the derived scene script,
rendered media, and caches — all scoped to one family and sharing that story's
retention and deletion rules (PRIVACY.md §4/§5). This package models where those
artifacts live (:class:`StoryArtifactStore`), how to hard-delete them verifiably
(:func:`delete_story`), and the default 30-day retention sweep
(:func:`purge_undelivered_stories`).
"""

from __future__ import annotations

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
    "BackupPurgeLog",
    "DeletionReceipt",
    "StoryArtifactStore",
    "StoryMetadata",
    "delete_story",
    "purge_undelivered_stories",
]
