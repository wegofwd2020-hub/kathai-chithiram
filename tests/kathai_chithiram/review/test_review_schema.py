"""Tests for the review decision schema (KC-7)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kathai_chithiram.review import ReviewDecision, ReviewRecord

_WHEN = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _approved(**overrides: object) -> ReviewRecord:
    kwargs: dict[str, object] = {
        "story_id": "s1",
        "decision": ReviewDecision.APPROVED,
        "reviewer": "alex",
        "decided_at": _WHEN,
        "reason": None,
        "reviewed": {"scene_count": 3},
    }
    kwargs.update(overrides)
    return ReviewRecord(**kwargs)  # type: ignore[arg-type]


def test_approval_needs_no_reason() -> None:
    record = _approved()
    assert record.approved is True
    assert record.reason is None


def test_rejection_requires_a_reason() -> None:
    with pytest.raises(ValueError, match="rejection must include a reason"):
        _approved(decision=ReviewDecision.REJECTED, reason=None)


def test_rejection_with_reason_is_valid() -> None:
    record = _approved(decision=ReviewDecision.REJECTED, reason="scene 3 flashes too fast")
    assert record.approved is False
    assert record.reason == "scene 3 flashes too fast"


def test_reviewer_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="reviewer"):
        _approved(reviewer="   ")


def test_decision_must_be_enum() -> None:
    with pytest.raises(ValueError, match="decision must be a ReviewDecision"):
        _approved(decision="approved")


def test_to_record_and_from_record_roundtrip() -> None:
    record = _approved(reason="looks calm and clear")
    restored = ReviewRecord.from_record(record.to_record())
    assert restored == record


def test_from_record_rejects_missing_keys() -> None:
    with pytest.raises(ValueError, match="missing keys"):
        ReviewRecord.from_record({"story_id": "s1", "decision": "approved"})


def test_from_record_rejects_unknown_decision() -> None:
    payload = _approved().to_record()
    payload["decision"] = "maybe"
    with pytest.raises(ValueError, match="not a valid review decision"):
        ReviewRecord.from_record(payload)


def test_from_record_rejects_bad_timestamp() -> None:
    payload = _approved().to_record()
    payload["decided_at"] = "not-a-date"
    with pytest.raises(ValueError, match="ISO-8601"):
        ReviewRecord.from_record(payload)
