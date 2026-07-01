"""Tests for the pure progress-engine interpreter (ADR-003).

The policies and feedback here are synthetic mock data (CLAUDE.md: no real child
data in tests). Thresholds are picked to exercise the interpreter, not to express a
clinical judgment — which is the collaborator's, not the tests' (ADR-003 Decision 2).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from kathai_chithiram.errors import PolicyError
from kathai_chithiram.feedback.schema import MoodCheckin, PromptLevel, SessionFeedback
from kathai_chithiram.progress import (
    Comparator,
    Condition,
    IndicatorState,
    Metric,
    ProgressPolicy,
    ThresholdRule,
    build_evidence,
    compute_metrics,
    measure,
    suggest,
)

_BASE = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _fb(
    *,
    level: PromptLevel = PromptLevel.INDEPENDENT,
    completed: bool = True,
    mood: MoodCheckin = MoodCheckin.HAPPY,
    day: int = 0,
) -> SessionFeedback:
    return SessionFeedback(
        goal_id="g1",
        story_id=f"s{day}",
        prompt_level=level,
        completed=completed,
        mood_checkin=mood,
        recorded_at=_BASE + timedelta(days=day),
    )


def _evidence(feedback: list[SessionFeedback], *, window: int):
    return build_evidence("g1", feedback, window=window)


def _cond(
    metric: Metric = Metric.INDEPENDENCE_RATE,
    comparator: Comparator = Comparator.GE,
    threshold: float = 0.6,
) -> Condition:
    return Condition(metric=metric, comparator=comparator, threshold=threshold)


def _rule(
    rule_id: str = "advance",
    *,
    conditions: tuple[Condition, ...] | None = None,
    signal: str = "advance",
    with_copy: bool = True,
) -> ThresholdRule:
    return ThresholdRule(
        rule_id=rule_id,
        conditions=conditions if conditions is not None else (_cond(),),
        signal=signal,
        suggested_premise="Consider a slightly harder step." if with_copy else None,
        rationale="Independence has held across recent sessions." if with_copy else None,
    )


def _policy(
    *,
    window: int = 3,
    min_sessions: int = 2,
    rules: tuple[ThresholdRule, ...] | None = None,
    enabled: bool = True,
) -> ProgressPolicy:
    return ProgressPolicy(
        policy_id="synthetic-v1",
        window=window,
        min_sessions=min_sessions,
        rules=rules if rules is not None else (_rule(),),
        enabled=enabled,
    )


# --- compute_metrics -------------------------------------------------------


def test_metrics_are_raw_rates_and_mean() -> None:
    feedback = [
        _fb(level=PromptLevel.INDEPENDENT, completed=True, mood=MoodCheckin.HAPPY, day=0),
        _fb(level=PromptLevel.PROMPTED, completed=True, mood=MoodCheckin.NEUTRAL, day=1),
        _fb(level=PromptLevel.REFUSED, completed=False, mood=MoodCheckin.UNHAPPY, day=2),
    ]
    metrics = compute_metrics(_evidence(feedback, window=3))
    assert metrics[Metric.INDEPENDENCE_RATE] == pytest.approx(1 / 3)
    assert metrics[Metric.REFUSAL_RATE] == pytest.approx(1 / 3)
    assert metrics[Metric.COMPLETION_RATE] == pytest.approx(2 / 3)
    assert metrics[Metric.MEAN_MOOD] == pytest.approx((4 + 3 + 2) / 3)


def test_trend_metrics_absent_below_two_sessions() -> None:
    metrics = compute_metrics(_evidence([_fb(day=0)], window=3))
    assert Metric.MOOD_TREND not in metrics
    assert Metric.COMPLETION_TREND not in metrics


def test_mood_trend_compares_newer_half_to_older_half() -> None:
    # Odd count drops the middle session; newer half improves over older half.
    feedback = [
        _fb(mood=MoodCheckin.VERY_UNHAPPY, day=0),  # older half
        _fb(mood=MoodCheckin.NEUTRAL, day=1),  # dropped middle
        _fb(mood=MoodCheckin.VERY_HAPPY, day=2),  # newer half
    ]
    metrics = compute_metrics(_evidence(feedback, window=3))
    assert metrics[Metric.MOOD_TREND] == pytest.approx(5.0 - 1.0)


def test_metrics_empty_for_no_sessions() -> None:
    assert compute_metrics(_evidence([_fb(day=0)], window=3)) != {}
    # An all-other-goal filter yields an empty window.
    other = SessionFeedback(
        goal_id="other",
        story_id="s0",
        prompt_level=PromptLevel.INDEPENDENT,
        completed=True,
        mood_checkin=MoodCheckin.HAPPY,
        recorded_at=_BASE,
    )
    assert compute_metrics(build_evidence("g1", [other], window=3)) == {}


# --- measure ---------------------------------------------------------------


def test_measure_rejects_window_mismatch() -> None:
    evidence = _evidence([_fb(day=0), _fb(day=1)], window=5)
    with pytest.raises(PolicyError, match="does not match policy window"):
        measure(evidence, _policy(window=3))


def test_measure_insufficient_data_below_min_sessions() -> None:
    evidence = _evidence([_fb(day=0)], window=3)
    indicator = measure(evidence, _policy(min_sessions=2))
    assert indicator.state is IndicatorState.INSUFFICIENT_DATA
    assert indicator.fired_rule_id is None
    # Even a suppressed verdict carries its computed metrics (explainability).
    assert Metric.INDEPENDENCE_RATE in indicator.metrics


def test_measure_disabled_policy_reports_no_signal() -> None:
    feedback = [_fb(day=0), _fb(day=1), _fb(day=2)]  # would otherwise fire
    indicator = measure(_evidence(feedback, window=3), _policy(enabled=False))
    assert indicator.state is IndicatorState.NO_SIGNAL
    assert indicator.fired_rule_id is None


def test_measure_fires_first_matching_rule() -> None:
    feedback = [_fb(day=0), _fb(day=1), _fb(day=2)]  # all independent → rate 1.0
    indicator = measure(_evidence(feedback, window=3), _policy())
    assert indicator.state is IndicatorState.SIGNAL_PRESENT
    assert indicator.fired_rule_id == "advance"
    assert indicator.signal == "advance"
    assert indicator.goal_id == "g1"
    assert indicator.policy_id == "synthetic-v1"


def test_measure_no_rule_matches_reports_no_signal() -> None:
    feedback = [
        _fb(level=PromptLevel.REFUSED, day=0),
        _fb(level=PromptLevel.REFUSED, day=1),
        _fb(level=PromptLevel.PROMPTED, day=2),
    ]  # independence rate 0.0 < 0.6
    indicator = measure(_evidence(feedback, window=3), _policy())
    assert indicator.state is IndicatorState.NO_SIGNAL
    assert indicator.fired_rule_id is None


def test_measure_requires_all_conditions_in_a_rule() -> None:
    # AND: high independence but low completion must not fire a two-condition rule.
    rule = _rule(
        conditions=(
            _cond(Metric.INDEPENDENCE_RATE, Comparator.GE, 0.6),
            _cond(Metric.COMPLETION_RATE, Comparator.GE, 0.6),
        ),
    )
    feedback = [
        _fb(completed=False, day=0),
        _fb(completed=False, day=1),
        _fb(completed=False, day=2),
    ]  # independence 1.0 but completion 0.0
    indicator = measure(_evidence(feedback, window=3), _policy(rules=(rule,)))
    assert indicator.state is IndicatorState.NO_SIGNAL


def test_measure_rule_order_first_match_wins() -> None:
    ease = _rule(rule_id="ease", conditions=(_cond(threshold=0.5),), signal="ease")
    advance = _rule(rule_id="advance", conditions=(_cond(threshold=0.9),), signal="advance")
    feedback = [_fb(day=0), _fb(day=1), _fb(day=2)]  # rate 1.0 — both match
    indicator = measure(_evidence(feedback, window=3), _policy(rules=(ease, advance)))
    assert indicator.fired_rule_id == "ease"  # earlier rule wins


def test_measure_condition_on_uncomputable_trend_does_not_match() -> None:
    # min_sessions=1 lets a single-session window through, but a mood-trend condition
    # cannot be computed there, so the rule must not fire.
    rule = _rule(conditions=(_cond(Metric.MOOD_TREND, Comparator.GE, 0.0),))
    indicator = measure(_evidence([_fb(day=0)], window=3), _policy(min_sessions=1, rules=(rule,)))
    assert indicator.state is IndicatorState.NO_SIGNAL


# --- suggest ---------------------------------------------------------------


def _signal_indicator(**policy_overrides: object):
    feedback = [_fb(day=0), _fb(day=1), _fb(day=2)]
    policy = _policy(**policy_overrides)  # type: ignore[arg-type]
    return measure(_evidence(feedback, window=3), policy), policy


def test_suggest_builds_the_fired_rules_suggestion() -> None:
    indicator, policy = _signal_indicator()
    at = _BASE + timedelta(days=10)
    suggestion = suggest(indicator, policy, suggestion_id="sg1", created_at=at)
    assert suggestion is not None
    assert suggestion.suggestion_id == "sg1"
    assert suggestion.goal_id == "g1"
    assert suggestion.suggested_premise == "Consider a slightly harder step."
    assert suggestion.rationale == "Independence has held across recent sessions."
    assert suggestion.created_at == at


def test_suggest_returns_none_without_signal() -> None:
    evidence = _evidence([_fb(day=0)], window=3)
    indicator = measure(evidence, _policy(min_sessions=2))  # insufficient data
    assert suggest(indicator, _policy(), suggestion_id="sg1", created_at=_BASE) is None


def test_suggest_returns_none_for_signal_without_copy() -> None:
    rule = _rule(with_copy=False)
    indicator, policy = _signal_indicator(rules=(rule,))
    assert indicator.state is IndicatorState.SIGNAL_PRESENT
    assert suggest(indicator, policy, suggestion_id="sg1", created_at=_BASE) is None


def test_suggest_is_deterministic() -> None:
    indicator, policy = _signal_indicator()
    a = suggest(indicator, policy, suggestion_id="sg1", created_at=_BASE)
    b = suggest(indicator, policy, suggestion_id="sg1", created_at=_BASE)
    assert a is not None and b is not None
    assert a.to_record() == b.to_record()
