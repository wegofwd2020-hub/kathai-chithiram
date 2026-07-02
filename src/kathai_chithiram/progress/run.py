"""Run the M1 engine end to end: measure → suggest → record (the gated wire-up).

This is the small enabling wire-up ADR-002/003 leave for once the Decision 7 gate
opens: given a collaborator-authored policy and a goal's evidence, it produces the
indicator, mints the suggestion the fired rule describes (if any), and records it
through the existing therapist-in-the-loop seam. Recording a suggestion is the only
effect and it is **inert** (ADR-002 Decisions 3/4/8): nothing is auto-authored,
generated, or delivered — a therapist decides via :func:`decide_suggestion`, and any
accepted premise still re-enters the full safety pipeline. Evidence gathering (a
cross-story read) is the caller's responsibility to run in a privileged context.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kathai_chithiram.progress.engine import ProgressIndicator, measure, suggest
from kathai_chithiram.progress.evidence import EvidenceBundle
from kathai_chithiram.progress.policy import ProgressPolicy
from kathai_chithiram.progress.review import record_suggestion
from kathai_chithiram.progress.suggestion import PremiseSuggestion
from kathai_chithiram.storage.protocol import StoryStore

__all__ = ["ProgressOutcome", "run_progress"]


@dataclass(frozen=True)
class ProgressOutcome:
    """The result of one engine run.

    Args:
        indicator: The measured indicator (state + metrics + fired rule).
        suggestion: The suggestion produced, or ``None`` when none was warranted.
        recorded: Whether a suggestion was recorded (True iff ``suggestion`` is set).
    """

    indicator: ProgressIndicator
    suggestion: PremiseSuggestion | None
    recorded: bool


def run_progress(
    store: StoryStore,
    *,
    evidence: EvidenceBundle,
    policy: ProgressPolicy,
    story_id: str,
    suggestion_id: str,
    created_at: datetime,
) -> ProgressOutcome:
    """Measure ``evidence`` under ``policy``, and record any suggestion it yields.

    Args:
        store: The store to record a suggestion into (per-story authorization
            applies when this is a guarded store).
        evidence: The goal's evidence window (its window must equal the policy's).
        policy: The collaborator-authored policy to interpret.
        story_id: The story a recorded suggestion is filed under for review.
        suggestion_id: The opaque id to assign a produced suggestion.
        created_at: The timestamp to stamp on a produced suggestion.

    Returns:
        A :class:`ProgressOutcome`.

    Raises:
        PolicyError: If the evidence window does not match the policy window.
        StoryNotFoundError: If ``story_id`` does not exist (when recording).
        AccessDeniedError: If a guarded store denies the record.
        OSError: If the record cannot be written.
    """
    indicator = measure(evidence, policy)
    suggestion = suggest(
        indicator, policy, suggestion_id=suggestion_id, created_at=created_at
    )
    if suggestion is not None:
        record_suggestion(store, story_id, suggestion)
    return ProgressOutcome(
        indicator=indicator, suggestion=suggestion, recorded=suggestion is not None
    )
