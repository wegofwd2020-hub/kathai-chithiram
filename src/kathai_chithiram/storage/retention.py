"""Default retention sweep: delete undelivered story text after 30 days.

PRIVACY.md §5: raw story text is kept only as long as needed to produce and
deliver the animation, then deleted within 30 days unless the parent opted to
save it. This sweep finds undelivered stories older than the threshold and
hard-deletes them through :func:`delete_story`, so the same verification and
backup-cascade guarantees apply.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from kathai_chithiram.errors import StoryNotFoundError
from kathai_chithiram.storage.deletion import (
    BackupPurgeLog,
    DeletionReceipt,
    delete_story,
)
from kathai_chithiram.storage.store import StoryArtifactStore

__all__ = ["DEFAULT_RETENTION", "purge_undelivered_stories"]

#: Default maximum age for undelivered story text before it is purged.
DEFAULT_RETENTION = timedelta(days=30)

logger = logging.getLogger(__name__)


def purge_undelivered_stories(
    store: StoryArtifactStore,
    *,
    now: datetime,
    purge_log: BackupPurgeLog,
    max_age: timedelta = DEFAULT_RETENTION,
) -> list[DeletionReceipt]:
    """Hard-delete undelivered stories older than ``max_age``.

    A story is purged only if it is **both** undelivered and older than the
    threshold; delivered stories and recent ones are left untouched.

    Args:
        store: The artifact store to sweep.
        now: The current time, injected for deterministic runs and testing.
        purge_log: Backup-cascade log passed through to each deletion.
        max_age: Maximum age for undelivered story text (default 30 days).

    Returns:
        A receipt for each story deleted, in store order.

    Raises:
        ValueError: If ``max_age`` is negative.
    """
    if max_age < timedelta(0):
        raise ValueError("max_age must be non-negative")

    cutoff = now - max_age
    receipts: list[DeletionReceipt] = []

    for story_id in list(store.iter_story_ids()):
        try:
            metadata = store.read_metadata(story_id)
        except StoryNotFoundError:
            # Raced with another delete or a partially-written story; skip it.
            logger.warning("retention: skipping story without metadata story=%s", story_id)
            continue

        # Keep delivered stories, and anything not strictly older than the
        # window (a story created exactly at the cutoff is still within 30 days).
        if metadata.delivered or metadata.created_at >= cutoff:
            continue

        receipts.append(delete_story(store, story_id, purge_log=purge_log, when=now))

    logger.info("retention sweep complete: purged=%d", len(receipts))
    return receipts
