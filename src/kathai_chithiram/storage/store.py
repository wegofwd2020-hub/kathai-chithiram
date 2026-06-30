"""Filesystem-backed store for a single story's artifacts.

Layout, one directory per story::

    <root>/<story_id>/
        story.txt          # raw parent-authored story text (High sensitivity)
        scene_script.json  # derived scene script
        intake.json        # non-sensitive: consent flags + provider posture
        feedback.jsonl     # per-session feedback primitives (ADR-002 capture)
        media/             # rendered animations
        cache/             # derived caches
        _meta.json         # non-sensitive: created_at, delivered flag

``story_id`` is an opaque identifier (e.g. a UUID), never a child's name, and is
validated to a safe character set so it cannot escape ``root`` via path
traversal. ``_meta.json`` deliberately holds **no** story text or name.

NOTE (at-rest encryption): PRIVACY.md §7 requires story text encrypted at rest.
This reference store writes plaintext files; encryption is a separate control
that must be added before any production use. It is called out here so the gap
is explicit, not silent.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from kathai_chithiram.errors import StoryNotFoundError

__all__ = ["StoryArtifactStore", "StoryMetadata"]

# Opaque-id safe set: alphanumerics, dash, underscore. Blocks "/", "..", etc.
_STORY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

# File names additionally allow a dot for extensions (e.g. "out.mp4"); ".." and
# "." are rejected explicitly so a dot can never form a traversal component.
_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")

_STORY_TEXT_FILE = "story.txt"
_SCENE_SCRIPT_FILE = "scene_script.json"
_INTAKE_FILE = "intake.json"
_FEEDBACK_FILE = "feedback.jsonl"
_META_FILE = "_meta.json"
_MEDIA_DIR = "media"
_CACHE_DIR = "cache"


@dataclass(frozen=True)
class StoryMetadata:
    """Non-sensitive bookkeeping for one story.

    Args:
        story_id: Opaque story identifier.
        created_at: When the story was created (timezone-aware recommended).
        delivered: Whether the rendered animation has been delivered to the
            parent. Governs the undelivered-retention sweep.
    """

    story_id: str
    created_at: datetime
    delivered: bool


def _validate_story_id(story_id: str) -> str:
    """Return ``story_id`` if it is a safe path component, else raise.

    Args:
        story_id: Candidate identifier.

    Returns:
        The validated id.

    Raises:
        ValueError: If the id is empty or contains unsafe characters.
    """
    if not _STORY_ID_PATTERN.match(story_id):
        raise ValueError("story_id must match ^[A-Za-z0-9_-]+$ (no path separators)")
    return story_id


class StoryArtifactStore:
    """A directory tree holding each story's artifacts under a common root.

    Args:
        root: Base directory under which per-story directories live. Created on
            demand.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        """The base directory of the store."""
        return self._root

    def story_dir(self, story_id: str) -> Path:
        """Return the directory for ``story_id`` (validated; not created here).

        Args:
            story_id: Opaque story identifier.

        Returns:
            The absolute-or-relative path to the story's directory.

        Raises:
            ValueError: If ``story_id`` is unsafe.
        """
        return self._root / _validate_story_id(story_id)

    def exists(self, story_id: str) -> bool:
        """Return whether any directory exists for ``story_id``.

        Args:
            story_id: Opaque story identifier.

        Returns:
            ``True`` if the story directory exists.

        Raises:
            ValueError: If ``story_id`` is unsafe.
        """
        return self.story_dir(story_id).is_dir()

    def create_story(
        self,
        story_id: str,
        *,
        created_at: datetime,
        story_text: str,
        delivered: bool = False,
    ) -> StoryMetadata:
        """Create a story directory with its raw text and metadata.

        Args:
            story_id: Opaque story identifier.
            created_at: Creation timestamp recorded in metadata.
            story_text: The raw parent-authored story.
            delivered: Initial delivered flag (default ``False``).

        Returns:
            The written :class:`StoryMetadata`.

        Raises:
            ValueError: If ``story_id`` is unsafe.
            OSError: If the files cannot be written.
        """
        story_dir = self.story_dir(story_id)
        story_dir.mkdir(parents=True, exist_ok=True)
        (story_dir / _STORY_TEXT_FILE).write_text(story_text, encoding="utf-8")
        metadata = StoryMetadata(
            story_id=story_id, created_at=created_at, delivered=delivered
        )
        self._write_metadata(story_dir, metadata)
        return metadata

    def write_scene_script(self, story_id: str, script: Mapping[str, Any]) -> None:
        """Persist the derived scene script for ``story_id``.

        Args:
            story_id: Opaque story identifier.
            script: The scene-script document.

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` is unsafe.
            OSError: If the file cannot be written.
        """
        story_dir = self._require(story_id)
        (story_dir / _SCENE_SCRIPT_FILE).write_text(
            json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def write_intake_record(self, story_id: str, record: Mapping[str, Any]) -> None:
        """Persist the non-sensitive intake/consent record for ``story_id``.

        The record captures the parent's consent flags and the provider privacy
        posture (the legal-basis evidence, PRIVACY.md §8). It MUST NOT contain
        story text or a child's name. It lives in the story directory, so a
        hard-delete of the story removes it along with everything else.

        Args:
            story_id: Opaque story identifier.
            record: A JSON-serializable, non-sensitive consent record.

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` is unsafe.
            OSError: If the file cannot be written.
        """
        story_dir = self._require(story_id)
        (story_dir / _INTAKE_FILE).write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
        )

    def append_session_feedback(self, story_id: str, record: Mapping[str, Any]) -> None:
        """Append one per-session feedback record to the story's feedback log.

        The log (``feedback.jsonl``, one JSON object per line) accrues the
        capture-track primitives of ADR-002. It lives in the story directory, so
        a verifiable hard-delete of the story removes it along with everything
        else. The record carries only opaque ids, enums, and a timestamp — no
        story text or name.

        Args:
            story_id: Opaque story identifier.
            record: A JSON-serializable feedback record (e.g.
                :meth:`SessionFeedback.to_record`).

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` is unsafe.
            OSError: If the log cannot be written.
        """
        story_dir = self._require(story_id)
        with (story_dir / _FEEDBACK_FILE).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def read_session_feedback(self, story_id: str) -> list[dict[str, Any]]:
        """Return every feedback record for ``story_id``, in append order.

        Args:
            story_id: Opaque story identifier.

        Returns:
            The decoded records (empty if none were captured).

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` is unsafe, or a log line is malformed.
        """
        story_dir = self._require(story_id)
        log_path = story_dir / _FEEDBACK_FILE
        if not log_path.is_file():
            return []
        records: list[dict[str, Any]] = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"malformed feedback record for story {story_id!r}") from exc
        return records

    def add_media(self, story_id: str, filename: str, data: bytes) -> Path:
        """Write a rendered media file under the story's ``media/`` directory.

        Args:
            story_id: Opaque story identifier.
            filename: Bare file name (no path separators).
            data: Raw bytes to write.

        Returns:
            The path written.

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` or ``filename`` is unsafe.
            OSError: If the file cannot be written.
        """
        return self._write_child(story_id, _MEDIA_DIR, filename, data)

    def add_cache(self, story_id: str, filename: str, data: bytes) -> Path:
        """Write a derived cache file under the story's ``cache/`` directory.

        Args:
            story_id: Opaque story identifier.
            filename: Bare file name (no path separators).
            data: Raw bytes to write.

        Returns:
            The path written.

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` or ``filename`` is unsafe.
            OSError: If the file cannot be written.
        """
        return self._write_child(story_id, _CACHE_DIR, filename, data)

    def artifact_paths(self, story_id: str) -> list[Path]:
        """Return every file belonging to ``story_id``, sorted.

        Used by deletion to enumerate (and afterwards confirm the absence of)
        all of a story's artifacts.

        Args:
            story_id: Opaque story identifier.

        Returns:
            A sorted list of file paths (empty if the story does not exist).

        Raises:
            ValueError: If ``story_id`` is unsafe.
        """
        story_dir = self.story_dir(story_id)
        if not story_dir.is_dir():
            return []
        return sorted(p for p in story_dir.rglob("*") if p.is_file())

    def read_metadata(self, story_id: str) -> StoryMetadata:
        """Read the non-sensitive metadata for ``story_id``.

        Args:
            story_id: Opaque story identifier.

        Returns:
            The stored :class:`StoryMetadata`.

        Raises:
            StoryNotFoundError: If the story or its metadata is missing.
            ValueError: If ``story_id`` is unsafe or metadata is malformed.
        """
        story_dir = self._require(story_id)
        meta_path = story_dir / _META_FILE
        if not meta_path.is_file():
            raise StoryNotFoundError(story_id)
        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
            return StoryMetadata(
                story_id=story_id,
                created_at=datetime.fromisoformat(raw["created_at"]),
                delivered=bool(raw["delivered"]),
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(f"malformed metadata for story {story_id!r}") from exc

    def mark_delivered(self, story_id: str) -> StoryMetadata:
        """Mark ``story_id`` as delivered and persist the change.

        Args:
            story_id: Opaque story identifier.

        Returns:
            The updated :class:`StoryMetadata`.

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` is unsafe.
        """
        current = self.read_metadata(story_id)
        updated = StoryMetadata(
            story_id=current.story_id, created_at=current.created_at, delivered=True
        )
        self._write_metadata(self.story_dir(story_id), updated)
        return updated

    def iter_story_ids(self) -> Iterator[str]:
        """Yield the id of every story currently in the store.

        Yields:
            Each story id (directory name) under the store root. If the root
            does not exist yet, yields nothing.
        """
        if not self._root.is_dir():
            return
        for child in sorted(self._root.iterdir()):
            if child.is_dir():
                yield child.name

    def _require(self, story_id: str) -> Path:
        """Return the story dir, raising :class:`StoryNotFoundError` if absent."""
        story_dir = self.story_dir(story_id)
        if not story_dir.is_dir():
            raise StoryNotFoundError(story_id)
        return story_dir

    def _write_child(self, story_id: str, subdir: str, filename: str, data: bytes) -> Path:
        """Validate and write ``data`` to ``<story>/<subdir>/<filename>``."""
        if filename in {".", ".."} or not _FILENAME_PATTERN.match(filename):
            raise ValueError("filename must match ^[A-Za-z0-9_.-]+$ and not be '.' or '..'")
        story_dir = self._require(story_id)
        target_dir = story_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        target.write_bytes(data)
        return target

    @staticmethod
    def _write_metadata(story_dir: Path, metadata: StoryMetadata) -> None:
        """Serialize metadata to ``_meta.json`` (no story text or name)."""
        payload = {
            "created_at": metadata.created_at.isoformat(),
            "delivered": metadata.delivered,
        }
        (story_dir / _META_FILE).write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
