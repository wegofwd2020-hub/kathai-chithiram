"""The ``ProgressPolicy`` schema — collaborator-owned configuration for the engine.

ADR-003 designs the M1 progress engine as a deterministic interpreter over a
**policy**: every clinical parameter (the window K, the thresholds, the trend
definitions, the uncertainty floor, the per-goal on/off switch) lives in a
:class:`ProgressPolicy` that a *trained professional collaborator* authors
(ADR-002 Decision 7.1). Engineering owns the *schema and its validation*; it does
**not** own the values.

Two boundaries this module holds deliberately (ADR-003 Decision 2):

* **No default clinical values.** :class:`ProgressPolicy`, :class:`ThresholdRule`,
  and :class:`Condition` have **no field defaults** for K, thresholds, or minimum
  sessions — every one must be supplied by whoever constructs the policy. There is
  no ``DEFAULT_K`` and no fallback threshold anywhere in this package, so an
  engineer's cutoff cannot reach a child by omission.
* **No policy instance ships here.** This module defines the *type*; it never
  constructs a production policy and never loads one. Until the collaborator
  authors one (and the ADR-002 Decision 7 gate opens), the engine has nothing to
  run. Any policy in tests is synthetic and explicitly non-clinical.

The vocabulary a policy composes over is a small, fixed set of **transparent,
deterministic metrics** (:class:`Metric`) computed from the raw feedback
primitives — "% independent over the window", "mean mood", a simple mood/completion
trend. *Which* metrics matter and at *what* threshold is the collaborator's clinical
judgment (the policy); *how* each metric is defined mechanically from the primitives
is engineering's (see :mod:`kathai_chithiram.progress.engine`).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "Comparator",
    "Condition",
    "Metric",
    "ProgressPolicy",
    "ThresholdRule",
]

#: Opaque-id charset for policy/rule ids — matches the store's id rules and the
#: feedback/suggestion primitives; no whitespace or punctuation that could smuggle
#: free text into an id.
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class Metric(str, Enum):
    """A transparent, deterministic quantity derived from the evidence window.

    Each metric is a mechanical function of the raw feedback primitives over the
    sessions in the window (see :func:`kathai_chithiram.progress.engine.measure`).
    It is *not* a progress score or a clinical verdict — it is one raw, explainable
    number a policy rule may threshold against. The metric *definitions* are
    engineering's; *which* to use and at *what* value is the collaborator's clinical
    judgment (ADR-003 Decision 2).

    Members:
        INDEPENDENCE_RATE: Fraction of window sessions with ``prompt_level ==
            independent`` (0.0–1.0).
        COMPLETION_RATE: Fraction of window sessions where ``completed`` is true
            (0.0–1.0).
        REFUSAL_RATE: Fraction of window sessions with ``prompt_level == refused``
            (0.0–1.0).
        MEAN_MOOD: Mean of the window's ``mood_checkin`` ordinals (1.0–5.0).
        MOOD_TREND: Mean mood over the newer half of the window minus the older
            half (-4.0–4.0); needs at least two sessions.
        COMPLETION_TREND: Completion rate over the newer half minus the older half
            (-1.0–1.0); needs at least two sessions.
    """

    INDEPENDENCE_RATE = "independence_rate"
    COMPLETION_RATE = "completion_rate"
    REFUSAL_RATE = "refusal_rate"
    MEAN_MOOD = "mean_mood"
    MOOD_TREND = "mood_trend"
    COMPLETION_TREND = "completion_trend"

    @property
    def value_range(self) -> tuple[float, float]:
        """The inclusive ``(low, high)`` a valid threshold for this metric lies in.

        The range is a definitional property of the metric (a rate is 0–1, a mean
        of a 1–5 ordinal is 1–5), so validating a threshold against it catches a
        config typo without expressing any clinical judgment.
        """
        return _METRIC_RANGES[self]


#: Definitional value range per metric (used only to reject out-of-range thresholds).
_METRIC_RANGES: dict[Metric, tuple[float, float]] = {
    Metric.INDEPENDENCE_RATE: (0.0, 1.0),
    Metric.COMPLETION_RATE: (0.0, 1.0),
    Metric.REFUSAL_RATE: (0.0, 1.0),
    Metric.MEAN_MOOD: (1.0, 5.0),
    Metric.MOOD_TREND: (-4.0, 4.0),
    Metric.COMPLETION_TREND: (-1.0, 1.0),
}


class Comparator(str, Enum):
    """How a :class:`Condition` compares a metric value to its threshold."""

    GE = ">="
    GT = ">"
    LE = "<="
    LT = "<"


@dataclass(frozen=True)
class Condition:
    """One metric-threshold test — the atom a :class:`ThresholdRule` is built from.

    A condition holds when the metric is computable for the evidence and its value
    stands in ``comparator`` relation to ``threshold``. A condition on a metric that
    cannot be computed for the given window (e.g. a trend with fewer than two
    sessions) does not hold — it never matches spuriously.

    Args:
        metric: The derived quantity to test.
        comparator: The comparison to apply.
        threshold: The value to compare against. Must be a finite number within the
            metric's definitional :attr:`Metric.value_range`.

    Raises:
        ValueError: If the metric/comparator has the wrong type, or the threshold is
            not a finite number within the metric's range.
    """

    metric: Metric
    comparator: Comparator
    threshold: float

    def __post_init__(self) -> None:
        if not isinstance(self.metric, Metric):
            raise ValueError("metric must be a Metric")
        if not isinstance(self.comparator, Comparator):
            raise ValueError("comparator must be a Comparator")
        # bool is an int subclass; reject it so ``True`` can't pose as a threshold.
        if isinstance(self.threshold, bool) or not isinstance(self.threshold, (int, float)):
            raise ValueError("threshold must be a number")
        if not math.isfinite(self.threshold):
            raise ValueError("threshold must be a finite number")
        low, high = self.metric.value_range
        if not (low <= self.threshold <= high):
            raise ValueError(
                f"threshold {self.threshold} is outside {self.metric.value} range [{low}, {high}]"
            )


@dataclass(frozen=True)
class ThresholdRule:
    """A conjunction of conditions and the signal (and optional suggestion) it fires.

    A rule matches when **every** condition holds (logical AND); express alternatives
    (OR) as separate rules in :attr:`ProgressPolicy.rules`, which are tried in order.
    A matched rule always marks the evidence as *signal present*. It additionally
    yields a premise suggestion **only** if it carries suggestion copy — a rule may
    deliberately signal without suggesting.

    All suggestion copy is collaborator-authored (ADR-003 Decision 6); the engine
    passes it through verbatim and never authors clinical language of its own. The
    numbers behind a suggestion live in the indicator's evidence, not in this copy.

    Args:
        rule_id: Opaque id, unique within a policy; recorded as the fired rule so a
            therapist can trace which rule produced a verdict (ADR-003 Decision 3).
        conditions: The conditions that must all hold. Must be non-empty — a rule
            with no conditions would match everything.
        signal: A short, opaque label for the rule's meaning (e.g. ``"advance"``,
            ``"hold"``). The engine records it but does not interpret it.
        suggested_premise: The premise text to propose when the rule fires, or
            ``None`` to signal without suggesting. If set, ``rationale`` must be set
            too.
        rationale: Plain-text reason for the suggestion (no child identifiers), or
            ``None``. Must be set iff ``suggested_premise`` is set.

    Raises:
        ValueError: If an id is empty/unsafe, ``conditions`` is empty, ``signal`` is
            blank, or the suggestion copy is inconsistent (only one of premise /
            rationale set, or a set field is blank).
    """

    rule_id: str
    conditions: tuple[Condition, ...]
    signal: str
    suggested_premise: str | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not _ID_PATTERN.match(self.rule_id):
            raise ValueError("rule_id must be a non-empty opaque id (^[A-Za-z0-9_-]+$)")
        if not isinstance(self.conditions, tuple) or not self.conditions:
            raise ValueError("conditions must be a non-empty tuple")
        if not all(isinstance(c, Condition) for c in self.conditions):
            raise ValueError("every condition must be a Condition")
        if not self.signal or not self.signal.strip():
            raise ValueError("signal must be a non-empty label")
        if (self.suggested_premise is None) != (self.rationale is None):
            raise ValueError("suggested_premise and rationale must both be set or both be None")
        if self.suggested_premise is not None and not self.suggested_premise.strip():
            raise ValueError("suggested_premise must be non-empty when set")
        if self.rationale is not None and not self.rationale.strip():
            raise ValueError("rationale must be non-empty when set")

    @property
    def suggests(self) -> bool:
        """Whether a match should yield a premise suggestion (copy is present)."""
        return self.suggested_premise is not None


@dataclass(frozen=True)
class ProgressPolicy:
    """A collaborator-authored configuration the progress engine interprets.

    This is the whole clinical judgment of the M1 engine, expressed as data: the
    window it reasons over, how much data it needs before saying anything, and the
    ordered rules that turn metric patterns into signals and suggestions. Engineering
    provides the type and its validation; the collaborator provides every value
    (ADR-002 Decision 7.1, ADR-003 Decision 2). It has **no field defaults** — a
    policy cannot be half-specified into existence.

    Args:
        policy_id: Opaque id/version of this policy, recorded on every indicator and
            suggestion so a verdict is traceable to the exact policy that produced it.
        window: The number of most-recent sessions to reason over (K); must be >= 1.
            Evidence passed to the engine must have been gathered over this same
            window.
        min_sessions: The fewest sessions required before the engine reports anything
            other than *insufficient data* (the uncertainty floor). Must be >= 1 and
            <= ``window``.
        rules: The rules to try in order; the first that matches fires. May be empty
            (a policy that never signals).
        enabled: The per-goal on/off switch. When false the engine reports no signal
            for this goal regardless of the data.

    Raises:
        ValueError: If ``policy_id`` is empty/unsafe, ``window`` < 1, ``min_sessions``
            is out of ``[1, window]``, ``rules`` is not a tuple of
            :class:`ThresholdRule`, or two rules share a ``rule_id``.
    """

    policy_id: str
    window: int
    min_sessions: int
    rules: tuple[ThresholdRule, ...]
    enabled: bool

    def __post_init__(self) -> None:
        if not _ID_PATTERN.match(self.policy_id):
            raise ValueError("policy_id must be a non-empty opaque id (^[A-Za-z0-9_-]+$)")
        # bool is an int subclass; reject it so a stray flag can't pose as a count.
        if isinstance(self.window, bool) or not isinstance(self.window, int) or self.window < 1:
            raise ValueError("window must be an integer >= 1")
        if (
            isinstance(self.min_sessions, bool)
            or not isinstance(self.min_sessions, int)
            or self.min_sessions < 1
        ):
            raise ValueError("min_sessions must be an integer >= 1")
        if self.min_sessions > self.window:
            raise ValueError("min_sessions must not exceed window")
        if not isinstance(self.rules, tuple) or not all(
            isinstance(r, ThresholdRule) for r in self.rules
        ):
            raise ValueError("rules must be a tuple of ThresholdRule")
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a bool")
        seen: set[str] = set()
        for rule in self.rules:
            if rule.rule_id in seen:
                raise ValueError(f"duplicate rule_id: {rule.rule_id!r}")
            seen.add(rule.rule_id)

    def rule(self, rule_id: str) -> ThresholdRule | None:
        """Return the rule with ``rule_id``, or ``None`` if the policy has none."""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None
