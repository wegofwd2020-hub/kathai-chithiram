"""The progress-engine interpreter — pure, deterministic ``measure`` + ``suggest``.

ADR-003 Decision 1 designs the engine as two side-effect-free stages layered on the
existing evidence substrate (:mod:`kathai_chithiram.progress.evidence`):

1. :func:`measure` — ``(EvidenceBundle, ProgressPolicy) -> ProgressIndicator``.
   Computes the transparent metrics for the window and applies the policy's rules to
   reach a verdict.
2. :func:`suggest` — ``(ProgressIndicator, ProgressPolicy) -> PremiseSuggestion |
   None``. Turns a *present, actionable* signal into the suggestion its fired rule
   describes, or returns ``None``.

Both are pure: no clock, no randomness, no I/O, no model. The same evidence and
policy always yield the same indicator and the same suggestion, so a therapist can
reproduce and audit any result (ADR-003 Decisions 1/3). :func:`suggest` takes the
suggestion id and timestamp as arguments rather than minting them, which keeps it
deterministic and leaves the one side effect the ADR permits — recording the
suggestion via the existing therapist-in-the-loop seam — to its caller (Decision 5).

**Still gated.** These mechanics are engineering-ownable and buildable now (ADR-003
Decision 7), but they run against a *real* policy only once the ADR-002 Decision 7
preconditions are met. This module ships no policy and wires to no recording path; on
its own it computes and returns values and does nothing else.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from kathai_chithiram.errors import PolicyError
from kathai_chithiram.feedback.schema import PromptLevel
from kathai_chithiram.progress.evidence import EvidenceBundle
from kathai_chithiram.progress.policy import Comparator, Condition, Metric, ProgressPolicy
from kathai_chithiram.progress.suggestion import PremiseSuggestion

__all__ = [
    "IndicatorState",
    "ProgressIndicator",
    "compute_metrics",
    "measure",
    "suggest",
]

#: Tolerance for threshold comparisons, so a boundary such as ``2/3 >= 0.6667`` is
#: not lost to floating-point representation. Metric values are simple ratios/means,
#: so a tiny epsilon is ample.
_EPS = 1e-9

_COMPARATORS: dict[Comparator, Callable[[float, float], bool]] = {
    Comparator.GE: lambda value, threshold: value >= threshold - _EPS,
    Comparator.GT: lambda value, threshold: value > threshold + _EPS,
    Comparator.LE: lambda value, threshold: value <= threshold + _EPS,
    Comparator.LT: lambda value, threshold: value < threshold - _EPS,
}


class IndicatorState(Enum):
    """The verdict an indicator carries (ADR-003 Decision 4).

    Only :attr:`SIGNAL_PRESENT` may yield a suggestion; the other two suppress it —
    the engine stays silent when there is too little data or nothing actionable,
    which is the guard against reading ordinary variance as a signal.

    Members:
        INSUFFICIENT_DATA: Fewer than the policy's ``min_sessions`` in the window.
        NO_SIGNAL: Enough data, but no rule matched (or the policy is disabled).
        SIGNAL_PRESENT: A rule matched; :attr:`ProgressIndicator.fired_rule_id`
            names it.
    """

    INSUFFICIENT_DATA = "insufficient_data"
    NO_SIGNAL = "no_signal"
    SIGNAL_PRESENT = "signal_present"


@dataclass(frozen=True)
class ProgressIndicator:
    """A transparent verdict plus the exact inputs behind it (ADR-003 Decision 3).

    Explainability is a payload, not a report generated after the fact: the indicator
    carries the evidence it was computed from and the raw metric values, so a
    suggestion can always be traced back to the sessions and numbers that produced it.

    Args:
        goal_id: The goal this verdict is about (from the evidence).
        policy_id: The policy that produced it.
        state: The verdict (see :class:`IndicatorState`).
        evidence: The evidence bundle the verdict was computed from.
        metrics: The metric values computed for the window. Trend metrics are absent
            when the window has fewer than two sessions.
        fired_rule_id: The id of the rule that matched, or ``None`` unless the state
            is :attr:`IndicatorState.SIGNAL_PRESENT`.
        signal: The fired rule's signal label, or ``None`` unless signal present.
    """

    goal_id: str
    policy_id: str
    state: IndicatorState
    evidence: EvidenceBundle
    metrics: Mapping[Metric, float]
    fired_rule_id: str | None
    signal: str | None


def compute_metrics(evidence: EvidenceBundle) -> dict[Metric, float]:
    """Compute the transparent metrics for an evidence window.

    Every metric is a deterministic function of the raw primitives (ADR-003
    Decision 1); nothing here is a score or a verdict. Rate and mean metrics need at
    least one session; the trend metrics need at least two and are omitted below that,
    so a condition on an uncomputable trend simply does not match (it never matches
    spuriously).

    Args:
        evidence: The window to summarise.

    Returns:
        A mapping of each computable :class:`Metric` to its value. Empty when the
        window has no sessions.
    """
    n = evidence.session_count
    metrics: dict[Metric, float] = {}
    if n == 0:
        return metrics

    counts = evidence.prompt_level_counts
    metrics[Metric.INDEPENDENCE_RATE] = counts[PromptLevel.INDEPENDENT] / n
    metrics[Metric.REFUSAL_RATE] = counts[PromptLevel.REFUSED] / n
    metrics[Metric.COMPLETION_RATE] = evidence.completed_count / n
    metrics[Metric.MEAN_MOOD] = sum(int(r.mood_checkin) for r in evidence.rows) / n

    if n >= 2:
        half = n // 2
        older = evidence.rows[:half]
        newer = evidence.rows[n - half :]  # equal-sized halves; drops the middle if odd
        older_mood = sum(int(r.mood_checkin) for r in older) / len(older)
        newer_mood = sum(int(r.mood_checkin) for r in newer) / len(newer)
        metrics[Metric.MOOD_TREND] = newer_mood - older_mood
        older_comp = sum(1 for r in older if r.completed) / len(older)
        newer_comp = sum(1 for r in newer if r.completed) / len(newer)
        metrics[Metric.COMPLETION_TREND] = newer_comp - older_comp

    return metrics


def measure(evidence: EvidenceBundle, policy: ProgressPolicy) -> ProgressIndicator:
    """Apply ``policy`` to ``evidence`` and return the resulting indicator.

    Deterministic and side-effect-free (ADR-003 Decision 1). The verdict is:
    *insufficient data* below ``policy.min_sessions`` (or *no signal* if the policy is
    disabled), otherwise *signal present* for the first rule whose conditions all hold,
    else *no signal*. The computed metrics ride along on the indicator either way, so
    even a suppressed verdict is explainable.

    Args:
        evidence: The window to reason over. Its ``window`` must equal ``policy.window``
            — a policy's thresholds are calibrated for its own K, so applying them to a
            differently sized window is a configuration error, not a silent best-effort.
        policy: The collaborator-authored policy to interpret.

    Returns:
        The :class:`ProgressIndicator` for this goal and policy.

    Raises:
        PolicyError: If ``evidence.window`` does not equal ``policy.window``.
    """
    if evidence.window != policy.window:
        raise PolicyError(
            policy.policy_id,
            f"evidence window {evidence.window} does not match policy window {policy.window}",
        )

    metrics = compute_metrics(evidence)

    def indicator(
        state: IndicatorState,
        *,
        fired_rule_id: str | None = None,
        signal: str | None = None,
    ) -> ProgressIndicator:
        return ProgressIndicator(
            goal_id=evidence.goal_id,
            policy_id=policy.policy_id,
            state=state,
            evidence=evidence,
            metrics=metrics,
            fired_rule_id=fired_rule_id,
            signal=signal,
        )

    if not policy.enabled:
        return indicator(IndicatorState.NO_SIGNAL)
    if evidence.session_count < policy.min_sessions:
        return indicator(IndicatorState.INSUFFICIENT_DATA)

    for rule in policy.rules:
        if all(_condition_holds(cond, metrics) for cond in rule.conditions):
            return indicator(
                IndicatorState.SIGNAL_PRESENT,
                fired_rule_id=rule.rule_id,
                signal=rule.signal,
            )
    return indicator(IndicatorState.NO_SIGNAL)


def suggest(
    indicator: ProgressIndicator,
    policy: ProgressPolicy,
    *,
    suggestion_id: str,
    created_at: datetime,
) -> PremiseSuggestion | None:
    """Build the premise suggestion an indicator's fired rule describes, or ``None``.

    Deterministic (ADR-003 Decisions 1/4): a suggestion is produced **only** for a
    :attr:`IndicatorState.SIGNAL_PRESENT` indicator whose fired rule carries suggestion
    copy; insufficient-data, no-signal, and signal-without-copy all return ``None``.
    The copy is the collaborator-authored premise and rationale, passed through
    verbatim (Decision 6). ``suggestion_id`` and ``created_at`` are supplied by the
    caller so this function mints nothing and stays pure; recording the returned
    suggestion (the one permitted side effect) is the caller's job via the existing
    therapist-in-the-loop seam (Decision 5).

    Args:
        indicator: The verdict to act on (typically from :func:`measure`).
        policy: The policy the indicator was produced with; the fired rule is looked
            up here for its suggestion copy.
        suggestion_id: The id to assign the suggestion (opaque; see
            :class:`~kathai_chithiram.progress.suggestion.PremiseSuggestion`).
        created_at: The timestamp to record on the suggestion.

    Returns:
        A :class:`~kathai_chithiram.progress.suggestion.PremiseSuggestion`, or ``None``
        when no suggestion is warranted.

    Raises:
        ValueError: If ``suggestion_id`` or ``created_at`` is invalid for a
            :class:`~kathai_chithiram.progress.suggestion.PremiseSuggestion`.
    """
    if indicator.state is not IndicatorState.SIGNAL_PRESENT or indicator.fired_rule_id is None:
        return None
    rule = policy.rule(indicator.fired_rule_id)
    if rule is None or rule.suggested_premise is None or rule.rationale is None:
        return None
    return PremiseSuggestion(
        suggestion_id=suggestion_id,
        goal_id=indicator.goal_id,
        suggested_premise=rule.suggested_premise,
        rationale=rule.rationale,
        created_at=created_at,
    )


def _condition_holds(condition: Condition, metrics: Mapping[Metric, float]) -> bool:
    """Return whether ``condition`` holds given the computed ``metrics``.

    A condition on a metric that was not computable for the window (absent from
    ``metrics``) does not hold, so a rule never matches on missing data.
    """
    value = metrics.get(condition.metric)
    if value is None:
        return False
    return _COMPARATORS[condition.comparator](value, condition.threshold)
