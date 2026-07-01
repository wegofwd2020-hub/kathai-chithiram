"""Tests for the ``ProgressPolicy`` schema and its validation (ADR-003).

Every policy here is synthetic and non-clinical — the thresholds are chosen to
exercise validation, not to express any real clinical judgment (ADR-003 Decision 2).
"""

from __future__ import annotations

import pytest

from kathai_chithiram.progress import (
    Comparator,
    Condition,
    Metric,
    ProgressPolicy,
    ThresholdRule,
)


def _cond(
    metric: Metric = Metric.INDEPENDENCE_RATE,
    comparator: Comparator = Comparator.GE,
    threshold: float = 0.8,
) -> Condition:
    return Condition(metric=metric, comparator=comparator, threshold=threshold)


def _rule(
    rule_id: str = "advance",
    *,
    conditions: tuple[Condition, ...] | None = None,
    signal: str = "advance",
    suggested_premise: str | None = "Consider a slightly harder step next time.",
    rationale: str | None = "Independence has been high across the recent window.",
) -> ThresholdRule:
    return ThresholdRule(
        rule_id=rule_id,
        conditions=conditions if conditions is not None else (_cond(),),
        signal=signal,
        suggested_premise=suggested_premise,
        rationale=rationale,
    )


def _policy(**overrides: object) -> ProgressPolicy:
    kwargs: dict[str, object] = {
        "policy_id": "synthetic-v1",
        "window": 5,
        "min_sessions": 3,
        "rules": (_rule(),),
        "enabled": True,
    }
    kwargs.update(overrides)
    return ProgressPolicy(**kwargs)  # type: ignore[arg-type]


# --- Condition -------------------------------------------------------------


def test_condition_rejects_threshold_outside_metric_range() -> None:
    with pytest.raises(ValueError, match="outside"):
        Condition(metric=Metric.INDEPENDENCE_RATE, comparator=Comparator.GE, threshold=1.5)


def test_condition_rejects_bool_threshold() -> None:
    with pytest.raises(ValueError, match="threshold must be a number"):
        Condition(metric=Metric.COMPLETION_RATE, comparator=Comparator.GE, threshold=True)  # type: ignore[arg-type]


def test_condition_rejects_non_finite_threshold() -> None:
    with pytest.raises(ValueError, match="finite"):
        Condition(metric=Metric.MEAN_MOOD, comparator=Comparator.GE, threshold=float("inf"))


def test_condition_accepts_range_endpoints() -> None:
    assert Condition(metric=Metric.MOOD_TREND, comparator=Comparator.LE, threshold=-4.0)
    assert Condition(metric=Metric.MEAN_MOOD, comparator=Comparator.GE, threshold=5.0)


# --- ThresholdRule ---------------------------------------------------------


def test_rule_requires_at_least_one_condition() -> None:
    with pytest.raises(ValueError, match="non-empty tuple"):
        _rule(conditions=())


def test_rule_rejects_unsafe_id() -> None:
    with pytest.raises(ValueError, match="rule_id"):
        _rule(rule_id="not ok!")


def test_rule_suggestion_copy_must_be_paired() -> None:
    with pytest.raises(ValueError, match="both be set or both be None"):
        _rule(suggested_premise="do a thing", rationale=None)


def test_rule_may_signal_without_suggesting() -> None:
    rule = _rule(suggested_premise=None, rationale=None)
    assert rule.suggests is False


def test_rule_that_suggests_reports_it() -> None:
    assert _rule().suggests is True


# --- ProgressPolicy --------------------------------------------------------


def test_policy_rejects_window_below_one() -> None:
    with pytest.raises(ValueError, match="window must be an integer >= 1"):
        _policy(window=0)


def test_policy_rejects_min_sessions_above_window() -> None:
    with pytest.raises(ValueError, match="min_sessions must not exceed window"):
        _policy(window=3, min_sessions=4)


def test_policy_rejects_bool_window() -> None:
    with pytest.raises(ValueError, match="window must be an integer >= 1"):
        _policy(window=True)


def test_policy_rejects_duplicate_rule_ids() -> None:
    with pytest.raises(ValueError, match="duplicate rule_id"):
        _policy(rules=(_rule(rule_id="dup"), _rule(rule_id="dup")))


def test_policy_allows_no_rules() -> None:
    assert _policy(rules=()).rules == ()


def test_policy_has_no_default_clinical_values() -> None:
    # ADR-003 Decision 2: a policy cannot be half-specified into existence — the
    # clinical fields have no defaults, so omitting them is a TypeError, not a
    # silent fallback to some engineer-chosen constant.
    with pytest.raises(TypeError):
        ProgressPolicy(policy_id="p")  # type: ignore[call-arg]


def test_policy_lookup_returns_rule_or_none() -> None:
    policy = _policy(rules=(_rule(rule_id="advance"),))
    assert policy.rule("advance") is not None
    assert policy.rule("missing") is None
