"""Tests for the log-safe access audit seam (ADR-004 Decision 5)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kathai_chithiram.access import (
    AccessEvent,
    AccessOutcome,
    AuditSink,
    InMemoryAuditSink,
)

_AT = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _event(**overrides: object) -> AccessEvent:
    kwargs: dict[str, object] = {
        "principal_id": "p1",
        "story_id": "s1",
        "action": "read_content",
        "outcome": AccessOutcome.ALLOWED,
        "recorded_at": _AT,
    }
    kwargs.update(overrides)
    return AccessEvent(**kwargs)  # type: ignore[arg-type]


def test_event_record_is_log_safe_opaque_ids_only() -> None:
    record = _event(outcome=AccessOutcome.DENIED, reason="no role").to_record()
    assert record == {
        "principal_id": "p1",
        "story_id": "s1",
        "action": "read_content",
        "outcome": "denied",
        "recorded_at": _AT.isoformat(),
        "reason": "no role",
    }


def test_event_allows_null_principal_before_authentication() -> None:
    event = _event(principal_id=None, story_id=None, action="authenticate")
    assert event.principal_id is None


def test_event_rejects_empty_action() -> None:
    with pytest.raises(ValueError, match="action must be a non-empty label"):
        _event(action="  ")


def test_in_memory_sink_keeps_order() -> None:
    sink = InMemoryAuditSink()
    sink.record(_event(action="a1"))
    sink.record(_event(action="a2", outcome=AccessOutcome.DENIED))
    assert [e.action for e in sink.events()] == ["a1", "a2"]
    assert isinstance(sink, AuditSink)
