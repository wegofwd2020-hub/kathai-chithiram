"""M1 progress track — ships-inert scaffolding around a gated engine (ADR-002).

The progress **measure** (% independent over K, mastery flags, mood trends) and
the logic that would **generate** a premise suggestion are GATED behind ADR-002
Decision 7 (a professional collaborator must define the signal first) and are
**not** in this package. What lives here is only what engineering may own before
the gate opens:

* :func:`build_evidence` / :func:`build_goal_evidence` — a read-only view of the
  raw captured primitives for a goal over a window. Computes no measure
  (Decision 7.2 explainability substrate).
* :class:`PremiseSuggestion` / :class:`SuggestionDecision` + :func:`record_suggestion`
  / :func:`decide_suggestion` — the therapist accept / edit / dismiss plumbing
  (Decision 7.3). Records a decision and triggers nothing (Decisions 3/4/8).
"""

from __future__ import annotations

from kathai_chithiram.progress.evidence import (
    EvidenceBundle,
    EvidenceRow,
    build_evidence,
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
    "EvidenceBundle",
    "EvidenceRow",
    "PremiseSuggestion",
    "SuggestionDecision",
    "SuggestionStatus",
    "build_evidence",
    "build_goal_evidence",
    "decide_suggestion",
    "open_suggestions",
    "record_suggestion",
]
