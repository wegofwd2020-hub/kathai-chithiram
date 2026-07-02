"""Tests for run_progress: measure -> suggest -> record (inert), the gated wire-up."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from kathai_chithiram.feedback.schema import MoodCheckin, PromptLevel, SessionFeedback
from kathai_chithiram.progress.engine import IndicatorState
from kathai_chithiram.progress.evidence import build_evidence
from kathai_chithiram.progress.policy import (
    Comparator,
    Condition,
    Metric,
    ProgressPolicy,
    ThresholdRule,
)
from kathai_chithiram.progress.run import run_progress
from kathai_chithiram.storage import StoryArtifactStore

_BASE = datetime(2026, 6, 1, tzinfo=timezone.utc)
_NOW = datetime(2026, 6, 10, tzinfo=timezone.utc)


def _store(tmp_path: Path) -> StoryArtifactStore:
    store = StoryArtifactStore(tmp_path / "store")
    store.create_story("s1", created_at=_BASE, story_text="x")
    return store


def _feedback(count: int, *, level: PromptLevel) -> list[SessionFeedback]:
    return [
        SessionFeedback(
            goal_id="g1",
            story_id="s1",
            prompt_level=level,
            completed=True,
            mood_checkin=MoodCheckin.HAPPY,
            recorded_at=_BASE + timedelta(days=day),
        )
        for day in range(count)
    ]


def _policy(*, threshold: float = 0.8, min_sessions: int = 2) -> ProgressPolicy:
    return ProgressPolicy(
        policy_id="synthetic-v1",
        window=3,
        min_sessions=min_sessions,
        enabled=True,
        rules=(
            ThresholdRule(
                rule_id="advance",
                conditions=(
                    Condition(Metric.INDEPENDENCE_RATE, Comparator.GE, threshold),
                ),
                signal="advance",
                suggested_premise="Try a slightly harder step.",
                rationale="Independence has held.",
            ),
        ),
    )


def test_signal_records_an_inert_suggestion(tmp_path: Path):
    store = _store(tmp_path)
    evidence = build_evidence("g1", _feedback(3, level=PromptLevel.INDEPENDENT), window=3)

    outcome = run_progress(
        store,
        evidence=evidence,
        policy=_policy(),  # independence_rate 1.0 >= 0.8 → fires
        story_id="s1",
        suggestion_id="sug1",
        created_at=_NOW,
    )

    assert outcome.indicator.state is IndicatorState.SIGNAL_PRESENT
    assert outcome.recorded is True
    assert outcome.suggestion is not None
    assert outcome.suggestion.suggestion_id == "sug1"
    # The suggestion was actually persisted for a therapist to act on.
    records = store.read_progress_suggestions("s1")
    assert any(r.get("suggestion_id") == "sug1" for r in records)


def test_no_signal_records_nothing(tmp_path: Path):
    store = _store(tmp_path)
    # All refused → independence_rate 0.0, never meets the 0.8 threshold.
    evidence = build_evidence("g1", _feedback(3, level=PromptLevel.REFUSED), window=3)

    outcome = run_progress(
        store,
        evidence=evidence,
        policy=_policy(),
        story_id="s1",
        suggestion_id="sug1",
        created_at=_NOW,
    )

    assert outcome.indicator.state is IndicatorState.NO_SIGNAL
    assert outcome.recorded is False
    assert outcome.suggestion is None
    assert store.read_progress_suggestions("s1") == []


def test_insufficient_data_records_nothing(tmp_path: Path):
    store = _store(tmp_path)
    evidence = build_evidence("g1", _feedback(1, level=PromptLevel.INDEPENDENT), window=3)

    outcome = run_progress(
        store,
        evidence=evidence,
        policy=_policy(min_sessions=2),  # only 1 session < 2
        story_id="s1",
        suggestion_id="sug1",
        created_at=_NOW,
    )

    assert outcome.indicator.state is IndicatorState.INSUFFICIENT_DATA
    assert outcome.recorded is False
    assert store.read_progress_suggestions("s1") == []
