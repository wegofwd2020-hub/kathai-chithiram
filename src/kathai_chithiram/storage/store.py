"""Filesystem-backed store for a single story's artifacts.

Layout, one directory per story::

    <root>/<story_id>/
        story.txt          # raw parent-authored story text (High sensitivity)
        scene_script.json  # derived scene script
        intake.json        # non-sensitive: consent flags + provider posture
        review.json        # non-sensitive: human-review decision (KC-7)
        feedback.jsonl     # per-session feedback primitives (ADR-002 capture)
        suggestions.jsonl  # premise-suggestion review records (ADR-002 M1 track)
        media/             # rendered animations
        cache/             # derived caches
        _meta.json         # non-sensitive: created_at, delivered flag

``story_id`` is an opaque identifier (e.g. a UUID), never a child's name, and is
validated to a safe character set so it cannot escape ``root`` via path
traversal. ``_meta.json`` deliberately holds **no** story text or name.

At-rest encryption (KC-5, PRIVACY.md §7): when the store is built with a
:class:`~kathai_chithiram.storage.crypto.StorageCipher`, every artifact holding
personal data — ``story.txt``, ``scene_script.json``, ``intake.json``,
``review.json``, ``feedback.jsonl``, ``suggestions.jsonl``, and ``media/`` — is
encrypted on disk;
callers still read and write plaintext, so the ciphertext never crosses the
store boundary. ``_meta.json`` stays cleartext by design (it holds no story text
or name). If no cipher is supplied the store writes plaintext, which is the
documented fallback and must not be used for real data in production.

Envelope encryption (KC-10): a story created under a cipher gets its own random
**per-story data key**. Artifact bodies are encrypted under that data key, and
the data key itself is stored **wrapped** by the master cipher in
``_data_key.wrapped`` inside the story directory — the master key never encrypts
an artifact body directly. Two consequences follow:

* **Crypto-shredding (DPIA R5).** A hard-delete (KC-1) sweeps the story
  directory, destroying the only wrapped copy of the data key; the story's
  artifacts become unrecoverable even if their raw ciphertext survives in a stale
  backup, without depending on that backup layer to drop every byte.
* **Incremental rotation (DPIA R3).** :meth:`StoryArtifactStore.rewrap_story`
  re-wraps a story's data key under a new master **without** re-encrypting the
  artifact bodies, so master-key rotation touches only the small wrapped-key file.

Backward compatibility: a legacy store written before KC-10 has no
``_data_key.wrapped`` file; such a story's bodies were encrypted under the master
directly, and the store transparently falls back to the master cipher for it — so
old and new layouts coexist behind the same cipher seam with no plaintext window.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from kathai_chithiram.errors import DecryptionError, StoryNotFoundError
from kathai_chithiram.storage.crypto import (
    StorageCipher,
    generate_data_key,
    unwrap_data_key,
    wrap_data_key,
)

__all__ = ["StoryArtifactStore", "StoryMetadata"]

# Opaque-id safe set: alphanumerics, dash, underscore. Blocks "/", "..", etc.
_STORY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

# File names additionally allow a dot for extensions (e.g. "out.mp4"); ".." and
# "." are rejected explicitly so a dot can never form a traversal component.
_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")

_STORY_TEXT_FILE = "story.txt"
_SCENE_SCRIPT_FILE = "scene_script.json"
_INTAKE_FILE = "intake.json"
_REVIEW_FILE = "review.json"
_FEEDBACK_FILE = "feedback.jsonl"
_SUGGESTIONS_FILE = "suggestions.jsonl"
_GRANTS_FILE = "grants.json"
_WRAPPED_KEY_FILE = "_data_key.wrapped"
_META_FILE = "_meta.json"
_MEDIA_DIR = "media"
_CACHE_DIR = "cache"
_CHILDREN_DIR = "_children"
_CHILD_KEY_FILE = "_child_key.wrapped"
_PARENT_MARKER_FILE = "_parent.json"


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


def _encode_jsonl_line(text: str, cipher: StorageCipher | None) -> str:
    """Encode one JSONL record line.

    Plaintext mode stores the JSON verbatim; encrypted mode stores a base64 of
    the ciphertext token so each line stays independently appendable and
    decryptable.
    """
    if cipher is None:
        return text
    return base64.urlsafe_b64encode(cipher.encrypt(text.encode("utf-8"))).decode("ascii")


def _decode_jsonl_line(line: str, cipher: StorageCipher | None, *, artifact: str) -> str:
    """Decode one JSONL line written by :func:`_encode_jsonl_line`.

    Raises:
        DecryptionError: If a cipher is configured and the line cannot be
            decrypted.
        ValueError: If a cipher is configured and the line is not valid base64.
    """
    if cipher is None:
        return line
    try:
        token = base64.urlsafe_b64decode(line)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"malformed encrypted line in {artifact}") from exc
    return cipher.decrypt(token, artifact=artifact).decode("utf-8")


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
        cipher: Optional at-rest cipher. When supplied, artifacts holding
            personal data are encrypted on disk (KC-5); when ``None`` the store
            writes plaintext (the documented, non-production fallback).
    """

    def __init__(self, root: Path, *, cipher: StorageCipher | None = None) -> None:
        self._root = Path(root)
        self._cipher = cipher

    @staticmethod
    def _seal(plaintext: bytes, cipher: StorageCipher | None) -> bytes:
        """Encrypt ``plaintext`` under ``cipher``, or pass it through if ``None``."""
        return cipher.encrypt(plaintext) if cipher is not None else plaintext

    @staticmethod
    def _unseal(stored: bytes, cipher: StorageCipher | None, *, artifact: str) -> bytes:
        """Decrypt ``stored`` bytes under ``cipher``, or pass them through if ``None``.

        Raises:
            DecryptionError: If ``cipher`` is set and the bytes cannot be
                authenticated/decrypted.
        """
        if cipher is None:
            return stored
        return cipher.decrypt(stored, artifact=artifact)

    def _story_cipher(self, story_dir: Path) -> StorageCipher | None:
        """Return the cipher that encrypts ``story_dir``'s artifact bodies.

        Resolves the three at-rest layouts (KC-10):

        * No master cipher configured → ``None`` (plaintext store).
        * ``_data_key.wrapped`` present → the per-story data key, unwrapped under
          the master (envelope encryption). This is the layout for every story
          created after KC-10.
        * No wrapped-key file → the master cipher itself (a legacy KC-5 store whose
          bodies were encrypted under the master directly).

        Args:
            story_dir: The story's directory (assumed to exist).

        Returns:
            The per-story artifact cipher, or ``None`` for a plaintext store.

        Raises:
            DecryptionError: If a wrapped key is present but cannot be unwrapped
                under the configured master (tampered, or a different master).
        """
        if self._cipher is None:
            return None
        key_path = story_dir / _WRAPPED_KEY_FILE
        if not key_path.is_file():
            return self._cipher
        return unwrap_data_key(
            self._cipher, key_path.read_bytes(), artifact=_WRAPPED_KEY_FILE
        )

    def _init_story_cipher(self, story_dir: Path) -> StorageCipher | None:
        """Create (or load) ``story_dir``'s per-story cipher at story creation.

        On a cipher-backed store with no wrapped key yet, generates a fresh
        per-story data key, writes it wrapped under the master to
        ``_data_key.wrapped``, and returns the per-story cipher (KC-10). Idempotent:
        if a wrapped key already exists it is loaded rather than regenerated, so
        re-creating a story never orphans its existing artifacts.

        Args:
            story_dir: The story's directory (already created).

        Returns:
            The per-story artifact cipher, or ``None`` for a plaintext store.

        Raises:
            OSError: If the wrapped-key file cannot be written.
        """
        if self._cipher is None:
            return None
        key_path = story_dir / _WRAPPED_KEY_FILE
        if key_path.is_file():
            return self._story_cipher(story_dir)
        data_key = generate_data_key()
        key_path.write_bytes(wrap_data_key(self._cipher, data_key))
        return self._story_cipher(story_dir)

    def _child_key_path(self, child_id: str) -> Path:
        """Path to ``child_id``'s wrapped per-child key (store-managed key material)."""
        return self._root / _CHILDREN_DIR / _validate_story_id(child_id) / _CHILD_KEY_FILE

    def _init_child_key(self, child_id: str) -> None:
        """Create ``child_id``'s per-child key, wrapped under the master (idempotent).

        No-op on a plaintext store (no master cipher). If a wrapped key already
        exists it is left untouched, so re-creating a child's story never orphans
        that child's existing stories.

        Args:
            child_id: Opaque child id (validated).

        Raises:
            ValueError: If ``child_id`` is unsafe.
            OSError: If the key file cannot be written.
        """
        if self._cipher is None:
            return
        key_path = self._child_key_path(child_id)
        if key_path.is_file():
            return
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(wrap_data_key(self._cipher, generate_data_key()))

    def _child_cipher(self, child_id: str) -> StorageCipher | None:
        """Return ``child_id``'s per-child cipher, unwrapped under the master.

        Returns ``None`` on a plaintext store. Fails closed: a missing or
        un-unwrappable wrapped child key raises :class:`DecryptionError` — this is
        what makes shredding the key crypto-shred every story beneath it.

        Args:
            child_id: Opaque child id (validated).

        Raises:
            ValueError: If ``child_id`` is unsafe.
            DecryptionError: If the wrapped child key is missing or cannot be
                unwrapped under the configured master.
        """
        if self._cipher is None:
            return None
        key_path = self._child_key_path(child_id)
        if not key_path.is_file():
            raise DecryptionError(_CHILD_KEY_FILE)
        return unwrap_data_key(
            self._cipher, key_path.read_bytes(), artifact=_CHILD_KEY_FILE
        )

    def shred_child_key(self, child_id: str) -> None:
        """Destroy ``child_id``'s wrapped per-child key (crypto-shred, §3).

        Deleting this single file renders every per-story key wrapped under it
        un-unwrappable, so all of the child's story content becomes undecryptable at
        once — before and independent of ``rmtree`` or the backup cycle. Idempotent:
        absent key is a no-op. No-op on a plaintext store.

        Args:
            child_id: Opaque child id (validated).

        Raises:
            ValueError: If ``child_id`` is unsafe.
        """
        key_path = self._child_key_path(child_id)
        key_path.unlink(missing_ok=True)

    def rewrap_child(self, child_id: str, *, new_master: StorageCipher) -> None:
        """Re-wrap ``child_id``'s per-child key under ``new_master`` (master rotation).

        Unwraps the per-child key with this store's current master, then re-wraps it
        under ``new_master`` in place. Per-story keys (wrapped under the child key)
        and artifact bodies are untouched. No-op on a plaintext store or a child with
        no wrapped key.

        Args:
            child_id: Opaque child id (validated).
            new_master: The master cipher to wrap the child key under going forward.

        Raises:
            ValueError: If ``child_id`` is unsafe.
            DecryptionError: If the existing wrapped key cannot be unwrapped under
                this store's current master.
            OSError: If the key file cannot be rewritten.
        """
        if self._cipher is None:
            return
        key_path = self._child_key_path(child_id)
        if not key_path.is_file():
            return
        data_key = self._cipher.decrypt(key_path.read_bytes(), artifact=_CHILD_KEY_FILE)
        key_path.write_bytes(wrap_data_key(new_master, data_key))

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
        cipher = self._init_story_cipher(story_dir)
        (story_dir / _STORY_TEXT_FILE).write_bytes(
            self._seal(story_text.encode("utf-8"), cipher)
        )
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
        payload = json.dumps(script, ensure_ascii=False, indent=2).encode("utf-8")
        cipher = self._story_cipher(story_dir)
        (story_dir / _SCENE_SCRIPT_FILE).write_bytes(self._seal(payload, cipher))

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
        payload = json.dumps(record, indent=2, sort_keys=True).encode("utf-8")
        cipher = self._story_cipher(story_dir)
        (story_dir / _INTAKE_FILE).write_bytes(self._seal(payload, cipher))

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
        cipher = self._story_cipher(story_dir)
        line = _encode_jsonl_line(json.dumps(record, sort_keys=True), cipher)
        with (story_dir / _FEEDBACK_FILE).open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

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
        cipher = self._story_cipher(story_dir)
        records: list[dict[str, Any]] = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                decoded = _decode_jsonl_line(line, cipher, artifact=_FEEDBACK_FILE)
                records.append(json.loads(decoded))
            except json.JSONDecodeError as exc:
                raise ValueError(f"malformed feedback record for story {story_id!r}") from exc
        return records

    def append_progress_suggestion(self, story_id: str, record: Mapping[str, Any]) -> None:
        """Append one premise-suggestion or decision record to the story's log.

        The log (``suggestions.jsonl``, one JSON object per line) holds the
        therapist-in-the-loop review records of the M1 progress track (ADR-002
        Decision 7.3). It lives in the story directory, so it is encrypted at rest
        (KC-5) and a verifiable hard-delete removes it with everything else (KC-1,
        ADR-002 Decision 5). Suggestion text is operator/therapist-authored, not a
        child's words.

        Args:
            story_id: Opaque story identifier.
            record: A JSON-serializable record (e.g.
                :meth:`PremiseSuggestion.to_record` or
                :meth:`SuggestionDecision.to_record`).

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` is unsafe.
            OSError: If the log cannot be written.
        """
        story_dir = self._require(story_id)
        cipher = self._story_cipher(story_dir)
        line = _encode_jsonl_line(json.dumps(record, sort_keys=True), cipher)
        with (story_dir / _SUGGESTIONS_FILE).open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def read_progress_suggestions(self, story_id: str) -> list[dict[str, Any]]:
        """Return every suggestion/decision record for ``story_id``, in append order.

        Args:
            story_id: Opaque story identifier.

        Returns:
            The decoded records (empty if none were recorded).

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` is unsafe, or a log line is malformed.
        """
        story_dir = self._require(story_id)
        log_path = story_dir / _SUGGESTIONS_FILE
        if not log_path.is_file():
            return []
        cipher = self._story_cipher(story_dir)
        records: list[dict[str, Any]] = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                decoded = _decode_jsonl_line(line, cipher, artifact=_SUGGESTIONS_FILE)
                records.append(json.loads(decoded))
            except json.JSONDecodeError as exc:
                raise ValueError(f"malformed suggestion record for story {story_id!r}") from exc
        return records

    def read_scene_script(self, story_id: str) -> dict[str, Any]:
        """Return the stored scene script for ``story_id``.

        Args:
            story_id: Opaque story identifier.

        Returns:
            The decoded scene-script document.

        Raises:
            StoryNotFoundError: If the story, or its scene script, is missing.
            ValueError: If ``story_id`` is unsafe or the scene script is malformed.
        """
        story_dir = self._require(story_id)
        path = story_dir / _SCENE_SCRIPT_FILE
        if not path.is_file():
            raise StoryNotFoundError(story_id)
        cipher = self._story_cipher(story_dir)
        try:
            plaintext = self._unseal(path.read_bytes(), cipher, artifact=_SCENE_SCRIPT_FILE)
            script: dict[str, Any] = json.loads(plaintext)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed scene script for story {story_id!r}") from exc
        return script

    def read_intake_record(self, story_id: str) -> dict[str, Any] | None:
        """Return the stored intake/consent record, or ``None`` if there is none.

        A story created by the non-interactive ``generate`` path has no intake
        record; only the parent ``intake`` flow writes one. Callers must treat
        ``None`` as "no consent record on file", not as an error.

        Args:
            story_id: Opaque story identifier.

        Returns:
            The decoded intake record, or ``None`` if absent.

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` is unsafe or the record is malformed.
        """
        story_dir = self._require(story_id)
        path = story_dir / _INTAKE_FILE
        if not path.is_file():
            return None
        cipher = self._story_cipher(story_dir)
        try:
            plaintext = self._unseal(path.read_bytes(), cipher, artifact=_INTAKE_FILE)
            record: dict[str, Any] = json.loads(plaintext)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed intake record for story {story_id!r}") from exc
        return record

    def write_review_record(self, story_id: str, record: Mapping[str, Any]) -> None:
        """Persist the non-sensitive human-review decision for ``story_id``.

        The record captures who reviewed the draft, the decision, when, an
        optional operator-authored reason, and a non-sensitive fingerprint of
        what was reviewed (KC-7 / CONTENT_SAFETY.md §6). Like ``intake.json`` it
        MUST NOT contain story text or a child's name, and it lives in the story
        directory so a hard-delete removes it along with everything else.

        Args:
            story_id: Opaque story identifier.
            record: A JSON-serializable, non-sensitive review record (e.g.
                :meth:`ReviewRecord.to_record`).

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` is unsafe.
            OSError: If the file cannot be written.
        """
        story_dir = self._require(story_id)
        payload = json.dumps(record, indent=2, sort_keys=True).encode("utf-8")
        cipher = self._story_cipher(story_dir)
        (story_dir / _REVIEW_FILE).write_bytes(self._seal(payload, cipher))

    def read_review_record(self, story_id: str) -> dict[str, Any] | None:
        """Return the stored review decision, or ``None`` if the story is unreviewed.

        Args:
            story_id: Opaque story identifier.

        Returns:
            The decoded review record, or ``None`` if no decision has been made.

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` is unsafe or the record is malformed.
        """
        story_dir = self._require(story_id)
        path = story_dir / _REVIEW_FILE
        if not path.is_file():
            return None
        cipher = self._story_cipher(story_dir)
        try:
            plaintext = self._unseal(path.read_bytes(), cipher, artifact=_REVIEW_FILE)
            record: dict[str, Any] = json.loads(plaintext)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed review record for story {story_id!r}") from exc
        return record

    def write_grants(self, story_id: str, record: Mapping[str, Any]) -> None:
        """Persist the access-control grants (owner + assignments) for ``story_id``.

        The grants are opaque principal ids and role labels only — no names, no story
        text — so, like ``_meta.json``, they are stored **cleartext** (they are not
        personal data) and live in the story directory, so a hard-delete removes them
        with everything else (ADR-004 Decision 4). The mapping of the access model's
        ``StoryGrants`` to/from this record is the access layer's job, not the store's.

        Args:
            story_id: Opaque story identifier.
            record: A JSON-serializable grants record (opaque ids + role labels).

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` is unsafe.
            OSError: If the file cannot be written.
        """
        story_dir = self._require(story_id)
        (story_dir / _GRANTS_FILE).write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
        )

    def read_grants(self, story_id: str) -> dict[str, Any] | None:
        """Return the stored grants record, or ``None`` if none has been written.

        A ``None`` result means the story has no recorded owner; the access layer
        treats that as deny-by-default (ADR-004).

        Args:
            story_id: Opaque story identifier.

        Returns:
            The decoded grants record, or ``None`` if the story is not owned.

        Raises:
            StoryNotFoundError: If the story does not exist.
            ValueError: If ``story_id`` is unsafe or the record is malformed.
        """
        story_dir = self._require(story_id)
        path = story_dir / _GRANTS_FILE
        if not path.is_file():
            return None
        try:
            record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed grants record for story {story_id!r}") from exc
        return record

    def rewrap_story(self, story_id: str, *, new_master: StorageCipher) -> None:
        """Re-wrap ``story_id``'s data key under ``new_master`` (master-key rotation).

        Unwraps the per-story data key with **this store's** current master, then
        re-wraps it under ``new_master`` and rewrites ``_data_key.wrapped`` in place
        (KC-10). The artifact bodies are **not** touched — that is the point of
        envelope encryption: rotating the master re-writes only the small
        wrapped-key file, not every ciphertext. After rewrapping every story, the
        deployment can swap the configured master to ``new_master`` (DPIA R3).

        A story with no wrapped key (a legacy KC-5 store) or a plaintext store has
        no per-story key to rotate and is skipped silently — such stores must be
        migrated by re-encrypting bodies, which is out of scope for a rewrap.

        Args:
            story_id: Opaque story identifier.
            new_master: The master cipher to wrap the data key under going forward.

        Raises:
            StoryNotFoundError: If the story does not exist.
            DecryptionError: If the existing wrapped key cannot be unwrapped under
                this store's current master.
            ValueError: If ``story_id`` is unsafe.
            OSError: If the wrapped-key file cannot be rewritten.
        """
        if self._cipher is None:
            return
        story_dir = self._require(story_id)
        key_path = story_dir / _WRAPPED_KEY_FILE
        if not key_path.is_file():
            return
        data_key = self._cipher.decrypt(key_path.read_bytes(), artifact=_WRAPPED_KEY_FILE)
        key_path.write_bytes(wrap_data_key(new_master, data_key))

    def media_paths(self, story_id: str) -> list[Path]:
        """Return the rendered media files for ``story_id``, sorted.

        A non-empty result means at least one guard-passing draft has been
        rendered (the pipeline only files media after the render-time safety
        guard succeeds), which is the precondition the review step checks before
        an approval is allowed.

        Args:
            story_id: Opaque story identifier.

        Returns:
            A sorted list of media file paths (empty if none, or if the story
            does not exist).

        Raises:
            ValueError: If ``story_id`` is unsafe.
        """
        media_dir = self.story_dir(story_id) / _MEDIA_DIR
        if not media_dir.is_dir():
            return []
        return sorted(p for p in media_dir.iterdir() if p.is_file())

    def read_media(self, story_id: str, filename: str) -> bytes:
        """Return the decrypted bytes of a stored media file.

        Media is encrypted at rest, so a stored ``.mp4`` is not directly
        playable on disk; this returns the plaintext bytes for export or
        playback (e.g. writing a decrypted copy for a reviewer to watch).

        Args:
            story_id: Opaque story identifier.
            filename: Bare media file name (no path separators).

        Returns:
            The decrypted media bytes.

        Raises:
            StoryNotFoundError: If the story, or the media file, is missing.
            DecryptionError: If a cipher is configured and the file cannot be
                decrypted.
            ValueError: If ``story_id`` or ``filename`` is unsafe.
        """
        if filename in {".", ".."} or not _FILENAME_PATTERN.match(filename):
            raise ValueError("filename must match ^[A-Za-z0-9_.-]+$ and not be '.' or '..'")
        story_dir = self._require(story_id)
        path = story_dir / _MEDIA_DIR / filename
        if not path.is_file():
            raise StoryNotFoundError(story_id)
        cipher = self._story_cipher(story_dir)
        return self._unseal(path.read_bytes(), cipher, artifact=f"{_MEDIA_DIR}/{filename}")

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
        cipher = self._story_cipher(story_dir)
        target.write_bytes(self._seal(data, cipher))
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
