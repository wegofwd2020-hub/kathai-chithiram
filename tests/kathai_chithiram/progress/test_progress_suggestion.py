"""Tests for the premise-suggestion / decision schema (ADR-002 M1 scaffolding)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kathai_chithiram.progress import (
    PremiseSuggestion,
    SuggestionDecision,
    SuggestionStatus,
)

_WHEN = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _suggestion(**overrides: object) -> PremiseSuggestion:
    kwargs: dict[str, object] = {
        "suggestion_id": "sg1",
        "goal_id": "g1",
        "suggested_premise": "Try a two-step version of the routine.",
        "rationale": "Independent across the recent window.",
        "created_at": _WHEN,
    }
    kwargs.update(overrides)
    return PremiseSuggestion(**kwargs)  # type: ignore[arg-type]


def _decision(**overrides: object) -> SuggestionDecision:
    kwargs: dict[str, object] = {
        "suggestion_id": "sg1",
        "status": SuggestionStatus.ACCEPTED,
        "reviewer": "nadia",
        "decided_at": _WHEN,
        "final_premise": "Try a two-step version of the routine.",
        "note": None,
    }
    kwargs.update(overrides)
    return SuggestionDecision(**kwargs)  # type: ignore[arg-type]


# --- PremiseSuggestion ----------------------------------------------------------


def test_suggestion_roundtrip() -> None:
    s = _suggestion()
    assert PremiseSuggestion.from_record(s.to_record()) == s


def test_suggestion_rejects_blank_premise() -> None:
    with pytest.raises(ValueError, match="suggested_premise"):
        _suggestion(suggested_premise="   ")


def test_suggestion_rejects_unsafe_id() -> None:
    with pytest.raises(ValueError, match="suggestion_id"):
        _suggestion(suggestion_id="../oops")


def test_suggestion_from_record_missing_keys() -> None:
    with pytest.raises(ValueError, match="missing keys"):
        PremiseSuggestion.from_record({"suggestion_id": "sg1"})


# --- SuggestionDecision ---------------------------------------------------------


def test_pending_is_not_a_decision() -> None:
    with pytest.raises(ValueError, match="accepted, edited, or dismissed"):
        _decision(status=SuggestionStatus.PENDING)


def test_reviewer_required() -> None:
    with pytest.raises(ValueError, match="reviewer"):
        _decision(reviewer="  ")


def test_accepted_requires_final_premise() -> None:
    with pytest.raises(ValueError, match="final premise"):
        _decision(status=SuggestionStatus.ACCEPTED, final_premise=None)


def test_dismissed_must_not_carry_final_premise() -> None:
    with pytest.raises(ValueError, match="must not carry a final premise"):
        _decision(status=SuggestionStatus.DISMISSED, final_premise="something")


def test_dismissed_with_note_is_valid() -> None:
    d = _decision(status=SuggestionStatus.DISMISSED, final_premise=None, note="too soon")
    assert d.status is SuggestionStatus.DISMISSED
    assert d.note == "too soon"


def test_decision_roundtrip() -> None:
    d = _decision(status=SuggestionStatus.EDITED, final_premise="An edited premise.")
    assert SuggestionDecision.from_record(d.to_record()) == d


def test_decision_from_record_rejects_bad_status() -> None:
    payload = _decision().to_record()
    payload["status"] = "maybe"
    with pytest.raises(ValueError, match="not a valid suggestion status"):
        SuggestionDecision.from_record(payload)
