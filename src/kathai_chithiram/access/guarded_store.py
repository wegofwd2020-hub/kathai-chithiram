"""The enforcement boundary — a principal-bound guard over ``StoryArtifactStore``.

ADR-004 chooses full technical enforcement at the store boundary. Rather than thread a
``Principal`` through every persistence method (rewriting the store and all its tests),
the enforcement lives in this thin wrapper: a :class:`GuardedStore` binds one
authenticated principal to an underlying :class:`StoryArtifactStore`, and exposes the
content-bearing operations, each of which **authorizes before it delegates** and
records a log-safe audit event. The persistence layer stays a pure data store; this is
the only object a caller that must be access-controlled should hold.

Guarantees (ADR-004 Decisions 1/5/6):

* **Deny-by-default.** Every content operation authorizes against the story's grants
  first; a principal with no role, or a story with no recorded owner, is refused with
  :class:`~kathai_chithiram.errors.AccessDeniedError` and **no bytes are read,
  decrypted, or written**.
* **Audited.** Every allowed access and every denial is recorded to the audit sink
  (opaque ids only), when a sink is supplied.
* **Composes with encryption.** Authorization runs before the underlying store touches
  the cipher, so an unauthorized principal never causes plaintext to be produced.

Bootstrap: :meth:`create_story` establishes the calling principal as the owner (a new
story has no prior grants to check against); thereafter every operation is authorized
against those grants.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kathai_chithiram.access.audit import AccessEvent, AccessOutcome, AuditSink
from kathai_chithiram.access.policy import AccessPolicy, Action, StoryGrants
from kathai_chithiram.access.principal import Principal, Role
from kathai_chithiram.errors import AccessDeniedError
from kathai_chithiram.storage.store import StoryArtifactStore, StoryMetadata

__all__ = ["GuardedStore"]


class GuardedStore:
    """A ``StoryArtifactStore`` façade that enforces one principal's access (ADR-004).

    Args:
        store: The underlying persistence store.
        principal: The authenticated identity every operation runs as.
        policy: The authorization policy (defaults to a fresh :class:`AccessPolicy`).
        audit: Optional audit sink; when supplied, every allowed/denied access is
            recorded.
        clock: Optional clock for audit timestamps (injectable for tests). Defaults to
            ``datetime.now(timezone.utc)``.
    """

    def __init__(
        self,
        store: StoryArtifactStore,
        principal: Principal,
        *,
        policy: AccessPolicy | None = None,
        audit: AuditSink | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._principal = principal
        self._policy = policy if policy is not None else AccessPolicy()
        self._audit = audit
        self._clock = clock if clock is not None else _default_clock

    # --- ownership / grants -------------------------------------------------

    def create_story(
        self,
        story_id: str,
        *,
        created_at: datetime,
        story_text: str,
        delivered: bool = False,
    ) -> StoryMetadata:
        """Create a story and record the calling principal as its owner.

        A new story has no grants to authorize against, so this is the bootstrap:
        the caller becomes the :attr:`~kathai_chithiram.access.principal.Role.FAMILY_OWNER`.

        Raises:
            ValueError: If ``story_id`` is unsafe.
            OSError: If the artifacts cannot be written.
        """
        metadata = self._store.create_story(
            story_id, created_at=created_at, story_text=story_text, delivered=delivered
        )
        grants = StoryGrants(owner_id=self._principal.principal_id, assignments={})
        self._store.write_grants(story_id, _grants_to_record(grants))
        self._record(story_id, Action.MANAGE_STORY, AccessOutcome.ALLOWED)
        return metadata

    def assign_role(self, story_id: str, principal_id: str, role: Role) -> StoryGrants:
        """Grant ``role`` on ``story_id`` to another principal (owner-only).

        Args:
            story_id: The story to assign a role on.
            principal_id: The principal receiving the role (opaque id).
            role: An assignable role (``REVIEWER`` / ``THERAPIST``).

        Returns:
            The updated :class:`StoryGrants`.

        Raises:
            AccessDeniedError: If the caller is not authorized to manage the story.
            StoryNotFoundError: If the story does not exist.
            ValueError: If the resulting grants are invalid (e.g. a non-assignable
                role, or assigning the owner).
        """
        grants = self._guard(story_id, Action.MANAGE_STORY)
        updated = StoryGrants(
            owner_id=grants.owner_id,
            assignments={**grants.assignments, principal_id: role},
        )
        self._store.write_grants(story_id, _grants_to_record(updated))
        return updated

    def grants(self, story_id: str) -> StoryGrants:
        """Return the story's grants (owner-only view).

        Raises:
            AccessDeniedError: If the caller is not authorized to manage the story.
        """
        return self._guard(story_id, Action.MANAGE_STORY)

    # --- content reads ------------------------------------------------------

    def read_scene_script(self, story_id: str) -> dict[str, Any]:
        """Read the scene script, if the principal may read this story's content."""
        self._guard(story_id, Action.READ_CONTENT)
        return self._store.read_scene_script(story_id)

    def read_media(self, story_id: str, filename: str) -> bytes:
        """Read one media file's bytes, if authorized for content."""
        self._guard(story_id, Action.READ_CONTENT)
        return self._store.read_media(story_id, filename)

    def media_paths(self, story_id: str) -> list[Path]:
        """List the story's media paths, if authorized for content."""
        self._guard(story_id, Action.READ_CONTENT)
        return self._store.media_paths(story_id)

    def read_review_record(self, story_id: str) -> dict[str, Any] | None:
        """Read the review decision, if authorized for content."""
        self._guard(story_id, Action.READ_CONTENT)
        return self._store.read_review_record(story_id)

    def read_intake_record(self, story_id: str) -> dict[str, Any] | None:
        """Read the intake/consent record, if authorized to read intake."""
        self._guard(story_id, Action.READ_INTAKE)
        return self._store.read_intake_record(story_id)

    def read_session_feedback(self, story_id: str) -> list[dict[str, Any]]:
        """Read the session feedback, if authorized to read feedback."""
        self._guard(story_id, Action.READ_FEEDBACK)
        return self._store.read_session_feedback(story_id)

    def read_progress_suggestions(self, story_id: str) -> list[dict[str, Any]]:
        """Read the premise suggestions, if authorized to read suggestions."""
        self._guard(story_id, Action.READ_SUGGESTIONS)
        return self._store.read_progress_suggestions(story_id)

    # --- content writes -----------------------------------------------------

    def write_scene_script(self, story_id: str, script: Mapping[str, Any]) -> None:
        """Persist a scene script, if authorized to write content."""
        self._guard(story_id, Action.WRITE_CONTENT)
        self._store.write_scene_script(story_id, script)

    def write_intake_record(self, story_id: str, record: Mapping[str, Any]) -> None:
        """Persist an intake record, if authorized to write content."""
        self._guard(story_id, Action.WRITE_CONTENT)
        self._store.write_intake_record(story_id, record)

    def add_media(self, story_id: str, filename: str, data: bytes) -> Path:
        """Add a media file, if authorized to write content."""
        self._guard(story_id, Action.WRITE_CONTENT)
        return self._store.add_media(story_id, filename, data)

    def append_session_feedback(self, story_id: str, record: Mapping[str, Any]) -> None:
        """Append a session feedback primitive, if authorized to write feedback."""
        self._guard(story_id, Action.WRITE_FEEDBACK)
        self._store.append_session_feedback(story_id, record)

    def append_progress_suggestion(self, story_id: str, record: Mapping[str, Any]) -> None:
        """Append a suggestion/decision record, if authorized to decide suggestions."""
        self._guard(story_id, Action.DECIDE_SUGGESTION)
        self._store.append_progress_suggestion(story_id, record)

    def write_review_record(self, story_id: str, record: Mapping[str, Any]) -> None:
        """Persist a review decision, if authorized to write reviews."""
        self._guard(story_id, Action.WRITE_REVIEW)
        self._store.write_review_record(story_id, record)

    def mark_delivered(self, story_id: str) -> StoryMetadata:
        """Mark the story delivered, if authorized to manage the story."""
        self._guard(story_id, Action.MANAGE_STORY)
        return self._store.mark_delivered(story_id)

    # --- internals ----------------------------------------------------------

    def _guard(self, story_id: str, action: Action) -> StoryGrants:
        """Authorize ``action`` on ``story_id``; audit the outcome; return the grants.

        Raises:
            AccessDeniedError: If the story has no recorded owner, or the principal's
                role does not grant ``action``. Audited as a denial before re-raising.
        """
        record = self._store.read_grants(story_id)
        try:
            if record is None:
                raise AccessDeniedError(
                    action.value,
                    "story has no access grants",
                    principal_id=self._principal.principal_id,
                    story_id=story_id,
                )
            grants = _grants_from_record(record)
            self._policy.authorize(self._principal, grants, action, story_id=story_id)
        except AccessDeniedError as exc:
            self._record(story_id, action, AccessOutcome.DENIED, reason=exc.reason)
            raise
        self._record(story_id, action, AccessOutcome.ALLOWED)
        return grants

    def _record(
        self,
        story_id: str,
        action: Action,
        outcome: AccessOutcome,
        *,
        reason: str | None = None,
    ) -> None:
        """Emit a log-safe audit event, if a sink is configured."""
        if self._audit is None:
            return
        self._audit.record(
            AccessEvent(
                principal_id=self._principal.principal_id,
                story_id=story_id,
                action=action.value,
                outcome=outcome,
                recorded_at=self._clock(),
                reason=reason,
            )
        )


def _grants_to_record(grants: StoryGrants) -> dict[str, Any]:
    """Serialize :class:`StoryGrants` to a store record (opaque ids + role labels)."""
    return {
        "owner_id": grants.owner_id,
        "assignments": {pid: role.value for pid, role in grants.assignments.items()},
    }


def _grants_from_record(record: Mapping[str, Any]) -> StoryGrants:
    """Parse a stored grants record into :class:`StoryGrants`.

    Raises:
        ValueError: If the record is malformed or carries an unknown role.
    """
    try:
        owner_id = record["owner_id"]
        raw_assignments = record["assignments"]
    except (KeyError, TypeError) as exc:
        raise ValueError("grants record missing owner_id/assignments") from exc
    if not isinstance(raw_assignments, Mapping):
        raise ValueError("grants assignments must be a mapping")
    try:
        assignments = {pid: Role(value) for pid, value in raw_assignments.items()}
    except ValueError as exc:
        raise ValueError("grants record carries an unknown role") from exc
    return StoryGrants(owner_id=owner_id, assignments=assignments)


def _default_clock() -> datetime:
    """Return the current UTC time (the production clock for audit events)."""
    return datetime.now(timezone.utc)
