"""M1 progress track — a gated engine plus the plumbing engineering may own.

ADR-002 gates the progress **measure** and the logic that would **generate** a
premise suggestion behind its Decision 7 (a professional collaborator must define
the signal first). ADR-003 then designs that engine as a deterministic interpreter
over a collaborator-authored policy, and draws the line for what is buildable before
the gate opens. This package holds exactly that buildable part:

* :func:`build_evidence` / :func:`build_goal_evidence` — a read-only view of the raw
  captured primitives for a goal over a window (Decision 7.2 explainability
  substrate). Computes no measure.
* :class:`ProgressPolicy` (+ :class:`Metric`, :class:`Comparator`, :class:`Condition`,
  :class:`ThresholdRule`) — the *schema* for the clinical configuration the
  collaborator authors. Ships no policy instance and no default clinical values
  (ADR-003 Decision 2).
* :func:`measure` / :func:`suggest` (+ :class:`ProgressIndicator`,
  :class:`IndicatorState`) — the pure, deterministic interpreter (ADR-003 Decision 1).
  These run against a *real* policy only once the ADR-002 Decision 7 gate opens; the
  package neither loads a policy nor wires the result to any recording path.
* :class:`PremiseSuggestion` / :class:`SuggestionDecision` + :func:`record_suggestion`
  / :func:`decide_suggestion` — the therapist accept / edit / dismiss plumbing
  (Decision 7.3). Records a decision and triggers nothing (Decisions 3/4/8).
"""

from __future__ import annotations

from kathai_chithiram.progress.engine import (
    IndicatorState,
    ProgressIndicator,
    compute_metrics,
    measure,
    suggest,
)
from kathai_chithiram.progress.evidence import (
    EvidenceBundle,
    EvidenceRow,
    build_evidence,
)
from kathai_chithiram.progress.policy import (
    Comparator,
    Condition,
    Metric,
    ProgressPolicy,
    ThresholdRule,
)
from kathai_chithiram.progress.review import (
    build_goal_evidence,
    decide_suggestion,
    open_suggestions,
    record_suggestion,
)
from kathai_chithiram.progress.suggestion import (
    PremiseSuggestion,
    SuggestionDecision,
    SuggestionStatus,
)

__all__ = [
    "Comparator",
    "Condition",
    "EvidenceBundle",
    "EvidenceRow",
    "IndicatorState",
    "Metric",
    "PremiseSuggestion",
    "ProgressIndicator",
    "ProgressPolicy",
    "SuggestionDecision",
    "SuggestionStatus",
    "ThresholdRule",
    "build_evidence",
    "build_goal_evidence",
    "compute_metrics",
    "decide_suggestion",
    "measure",
    "open_suggestions",
    "record_suggestion",
    "suggest",
]
