"""Verifiable hard-delete of a story and all its derived artifacts.

Implements PRIVACY.md §5: a parent's delete removes the raw story text, the
derived scene script, rendered media, and caches — a *hard* delete with no
tombstoned copy of raw text. The removal is verified (the function confirms no
artifact remains) and cascades to backups via an append-only purge log keyed by
story id (which carries no story text, so it is not itself a tombstone).
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from kathai_chithiram.errors import DeletionError, StoryNotFoundError
from kathai_chithiram.storage.store import StoryArtifactStore

__all__ = ["BackupPurgeLog", "DeletionReceipt", "delete_story"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeletionReceipt:
    """Proof of a completed, verified hard-delete.

    Args:
        story_id: The story that was deleted (safe opaque id).
        removed_file_count: How many artifact files were removed.
        backup_purge_logged: Whether the backup-cascade record was written.
    """

    story_id: str
    removed_file_count: int
    backup_purge_logged: bool


class BackupPurgeLog:
    """Append-only record of story ids to purge from backups on the next cycle.

    Backups cannot be reached synchronously, so deletion records an intent here
    and the backup job consumes it on its next run (PRIVACY.md §5). The log
    stores only the opaque story id and a timestamp — never raw story text — so
    it does not become a tombstone of personal content.

    Args:
        path: File the log is appended to (JSON Lines). Created on demand.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        """The backing file path."""
        return self._path

    def record(self, story_id: str, *, when: datetime | None = None) -> None:
        """Append a purge entry for ``story_id``.

        Args:
            story_id: The story to purge from backups (no raw text).
            when: Optional timestamp; recorded as ISO if given.

        Raises:
            OSError: If the log cannot be written.
        """
        entry = {"story_id": story_id, "requested_at": when.isoformat() if when else None}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def pending_story_ids(self) -> list[str]:
        """Return the story ids currently queued for backup purge.

        Returns:
            Story ids in append order (empty if the log does not exist).

        Raises:
            ValueError: If a log line is malformed.
        """
        if not self._path.is_file():
            return []
        ids: list[str] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                ids.append(json.loads(line)["story_id"])
            except (KeyError, ValueError) as exc:
                raise ValueError("malformed backup-purge log line") from exc
        return ids


def delete_story(
    store: StoryArtifactStore,
    story_id: str,
    *,
    purge_log: BackupPurgeLog,
    when: datetime | None = None,
) -> DeletionReceipt:
    """Hard-delete every artifact of ``story_id`` and verify nothing remains.

    Args:
        store: The artifact store holding the story.
        story_id: The story to delete.
        purge_log: Backup-cascade log to record the deletion in.
        when: Optional timestamp recorded in the purge log.

    Returns:
        A :class:`DeletionReceipt` confirming the verified deletion.

    Raises:
        StoryNotFoundError: If no story exists for ``story_id``.
        DeletionError: If removal fails, or if any artifact remains afterwards
            (a partial delete must never pass silently).
        ValueError: If ``story_id`` is unsafe.
    """
    if not store.exists(story_id):
        raise StoryNotFoundError(story_id)

    story_dir = store.story_dir(story_id)
    removed_count = len(store.artifact_paths(story_id))

    try:
        shutil.rmtree(story_dir)
    except OSError as exc:
        logger.warning("hard-delete failed: story=%s reason=os_error", story_id)
        raise DeletionError(story_id, "filesystem removal failed") from exc

    # Verify: the directory and every artifact must be gone. This is the
    # "deletion must be verifiable" guarantee, enforced rather than assumed.
    if story_dir.exists() or store.artifact_paths(story_id):
        raise DeletionError(story_id, "artifacts remained after deletion")

    purge_log.record(story_id, when=when)
    logger.info(
        "hard-delete complete: story=%s removed_files=%d backup_purge_logged=True",
        story_id,
        removed_count,
    )
    return DeletionReceipt(
        story_id=story_id, removed_file_count=removed_count, backup_purge_logged=True
    )
