"""Tests for the log-safe access audit seam (ADR-004 Decision 5)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kathai_chithiram.access import (
    AccessEvent,
    AccessOutcome,
    AuditSink,
    InMemoryAuditSink,
    JsonlAuditSink,
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


def test_event_from_record_round_trips() -> None:
    event = _event(principal_id=None, outcome=AccessOutcome.DENIED, reason="no role")
    assert AccessEvent.from_record(event.to_record()) == event


def test_jsonl_sink_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    JsonlAuditSink(path).record(_event(action="a1"))
    JsonlAuditSink(path).record(_event(action="a2", outcome=AccessOutcome.DENIED))
    # A fresh sink (new process, same file) sees the whole append-only trail.
    events = JsonlAuditSink(path).read()
    assert [(e.action, e.outcome) for e in events] == [
        ("a1", AccessOutcome.ALLOWED),
        ("a2", AccessOutcome.DENIED),
    ]
    assert isinstance(JsonlAuditSink(path), AuditSink)


def test_jsonl_sink_read_empty_when_absent(tmp_path: Path) -> None:
    assert JsonlAuditSink(tmp_path / "missing.jsonl").read() == []


def test_jsonl_sink_lines_are_log_safe(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    JsonlAuditSink(path).record(_event())
    text = path.read_text(encoding="utf-8")
    # Only opaque ids/actions on disk — a record carries no content fields at all.
    assert set(json.loads(text)) == {
        "principal_id",
        "story_id",
        "action",
        "outcome",
        "recorded_at",
        "reason",
    }
