"""The access audit seam — a log-safe record of every access and denial (ADR-004 D5).

Every authorized content access, and every denial, is recorded as an
:class:`AccessEvent` carrying only opaque ids, an action, an outcome, and a
timestamp — **never** story text, captions, or names (PRIVACY.md §6). Because a
record names no content, an audit log is safe to retain (even centrally, even after
a story is hard-deleted) for its "detect operator browsing" value.

The sink is a seam (:class:`AuditSink`): this module ships an in-memory sink for tests
and simple use; a durable local-file sink and a tamper-evident central sink are
concretes that land with the store integration and the eventual deployment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

__all__ = ["AccessEvent", "AccessOutcome", "AuditSink", "InMemoryAuditSink"]


class AccessOutcome(Enum):
    """Whether an access attempt was permitted or refused."""

    ALLOWED = "allowed"
    DENIED = "denied"


@dataclass(frozen=True)
class AccessEvent:
    """One log-safe audit record of an access attempt.

    Args:
        principal_id: The principal that attempted access, or ``None`` if the attempt
            failed before authentication (opaque id; never a name).
        story_id: The story involved, or ``None`` if not story-scoped (opaque id).
        action: The attempted action (e.g. ``"read_content"``).
        outcome: Whether it was allowed or denied.
        recorded_at: When the attempt happened (supplied by the caller so the record
            stays deterministic and testable).
        reason: Optional short reason, for denials (no child data).

    Raises:
        ValueError: If ``action`` is empty or ``recorded_at`` is not a datetime.
    """

    principal_id: str | None
    story_id: str | None
    action: str
    outcome: AccessOutcome
    recorded_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.action or not self.action.strip():
            raise ValueError("action must be a non-empty label")
        if not isinstance(self.outcome, AccessOutcome):
            raise ValueError("outcome must be an AccessOutcome")
        if not isinstance(self.recorded_at, datetime):
            raise ValueError("recorded_at must be a datetime")

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-serializable, log-safe record (opaque ids only)."""
        return {
            "principal_id": self.principal_id,
            "story_id": self.story_id,
            "action": self.action,
            "outcome": self.outcome.value,
            "recorded_at": self.recorded_at.isoformat(),
            "reason": self.reason,
        }


@runtime_checkable
class AuditSink(Protocol):
    """Receives access audit events. Implementations must not raise on a valid event."""

    def record(self, event: AccessEvent) -> None:
        """Persist one :class:`AccessEvent`."""
        ...


class InMemoryAuditSink:
    """An audit sink that keeps events in memory — for tests and simple in-process use.

    A durable local-file sink and a tamper-evident central sink are separate concretes
    (they land with the store integration / deployment).
    """

    def __init__(self) -> None:
        self._events: list[AccessEvent] = []

    def record(self, event: AccessEvent) -> None:
        """Append ``event`` to the in-memory log."""
        self._events.append(event)

    def events(self) -> tuple[AccessEvent, ...]:
        """Return the recorded events, in the order they were recorded."""
        return tuple(self._events)
