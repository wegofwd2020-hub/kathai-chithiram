"""Premise-suggestion review records — the therapist-in-the-loop path (ADR-002 D3/D7.3).

A **premise suggestion** proposes updating a (therapist-owned) premise for a
child's future stories, with a rationale. ADR-002 is emphatic about the
boundaries this data model encodes:

* **Nothing here generates a suggestion.** The engine that would derive one from a
  progress measure is gated (Decision 6/7). These types are the *shape* such a
  suggestion will take and the record of the therapist's decision on it — no more.
* **The system suggests; the therapist decides** (Decision 3). A
  :class:`SuggestionDecision` records an explicit accept / edit / dismiss by a
  named reviewer. It never edits a premise, generates a story, or schedules one.
* **No closed loop** (Decision 8). Accepting a suggestion records the therapist's
  choice; it triggers nothing. Any resulting story still re-enters the full safety
  pipeline (Decision 4), driven by a human.

The suggestion text and rationale are therapist/operator-authored content (not a
child's words), but the records live under the child's story, so they inherit the
special-category regime: encrypted at rest (KC-5) and verifiably hard-deleted
with the story (KC-1, Decision 5).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

__all__ = [
    "REQUIRED_DECISION_KEYS",
    "REQUIRED_SUGGESTION_KEYS",
    "PremiseSuggestion",
    "SuggestionDecision",
    "SuggestionStatus",
]

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

#: Keys a serialized suggestion record must carry.
REQUIRED_SUGGESTION_KEYS: tuple[str, ...] = (
    "suggestion_id",
    "goal_id",
    "suggested_premise",
    "rationale",
    "created_at",
)

#: Keys a serialized decision record must carry.
REQUIRED_DECISION_KEYS: tuple[str, ...] = (
    "suggestion_id",
    "status",
    "reviewer",
    "decided_at",
    "final_premise",
    "note",
)


class SuggestionStatus(str, Enum):
    """Where a suggestion stands with its therapist reviewer.

    ``PENDING`` is the awaiting-review state; the other three are the explicit
    therapist decisions (Decision 7.3).
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    DISMISSED = "dismissed"

    @property
    def is_decision(self) -> bool:
        """Whether this is a therapist decision (not the pending state)."""
        return self is not SuggestionStatus.PENDING


@dataclass(frozen=True)
class PremiseSuggestion:
    """A proposed premise update awaiting a therapist's decision.

    Args:
        suggestion_id: Opaque id for this suggestion.
        goal_id: The therapist-owned goal it pertains to (opaque id).
        suggested_premise: The proposed premise text (operator/engine-authored).
        rationale: Why it is being suggested (plain text; no child identifiers).
        created_at: When the suggestion was recorded (timezone-aware recommended).

    Raises:
        ValueError: If an id is empty/unsafe, a text field is blank, or a field
            has the wrong type.
    """

    suggestion_id: str
    goal_id: str
    suggested_premise: str
    rationale: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not _ID_PATTERN.match(self.suggestion_id):
            raise ValueError("suggestion_id must be a non-empty opaque id (^[A-Za-z0-9_-]+$)")
        if not _ID_PATTERN.match(self.goal_id):
            raise ValueError("goal_id must be a non-empty opaque id (^[A-Za-z0-9_-]+$)")
        if not self.suggested_premise or not self.suggested_premise.strip():
            raise ValueError("suggested_premise must be non-empty")
        if not self.rationale or not self.rationale.strip():
            raise ValueError("rationale must be non-empty")
        if not isinstance(self.created_at, datetime):
            raise ValueError("created_at must be a datetime")

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-serializable record for the suggestions log."""
        return {
            "kind": "suggestion",
            "suggestion_id": self.suggestion_id,
            "goal_id": self.goal_id,
            "suggested_premise": self.suggested_premise,
            "rationale": self.rationale,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> PremiseSuggestion:
        """Parse and validate a stored suggestion record.

        Raises:
            ValueError: If a key is missing or a value is malformed.
        """
        _require_keys(record, REQUIRED_SUGGESTION_KEYS, "suggestion")
        try:
            created_at = datetime.fromisoformat(record["created_at"])
        except (TypeError, ValueError) as exc:
            raise ValueError("created_at must be an ISO-8601 timestamp") from exc
        return cls(
            suggestion_id=record["suggestion_id"],
            goal_id=record["goal_id"],
            suggested_premise=record["suggested_premise"],
            rationale=record["rationale"],
            created_at=created_at,
        )


@dataclass(frozen=True)
class SuggestionDecision:
    """A therapist's explicit decision on a suggestion (accept / edit / dismiss).

    Args:
        suggestion_id: The suggestion being decided.
        status: The decision — ``ACCEPTED``, ``EDITED``, or ``DISMISSED`` (never
            ``PENDING``).
        reviewer: Who decided (a non-empty identifier; recorded for audit).
        decided_at: When the decision was made (timezone-aware recommended).
        final_premise: For ``ACCEPTED`` / ``EDITED``, the premise the therapist
            approved (required); must be ``None`` for ``DISMISSED``.
        note: Optional reviewer note (e.g. a dismissal reason).

    Raises:
        ValueError: If the status is not a decision, the reviewer is empty, or
            ``final_premise`` is inconsistent with the status.
    """

    suggestion_id: str
    status: SuggestionStatus
    reviewer: str
    decided_at: datetime
    final_premise: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, SuggestionStatus):
            raise ValueError("status must be a SuggestionStatus")
        if not self.status.is_decision:
            raise ValueError("a decision status must be accepted, edited, or dismissed")
        if not self.reviewer or not self.reviewer.strip():
            raise ValueError("reviewer must be a non-empty identifier")
        if not isinstance(self.decided_at, datetime):
            raise ValueError("decided_at must be a datetime")
        accepts = self.status in (SuggestionStatus.ACCEPTED, SuggestionStatus.EDITED)
        if accepts and not (self.final_premise or "").strip():
            raise ValueError("an accepted or edited decision must carry the final premise")
        if self.status is SuggestionStatus.DISMISSED and self.final_premise is not None:
            raise ValueError("a dismissed decision must not carry a final premise")

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-serializable record for the suggestions log."""
        return {
            "kind": "decision",
            "suggestion_id": self.suggestion_id,
            "status": self.status.value,
            "reviewer": self.reviewer,
            "decided_at": self.decided_at.isoformat(),
            "final_premise": self.final_premise,
            "note": self.note,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> SuggestionDecision:
        """Parse and validate a stored decision record.

        Raises:
            ValueError: If a key is missing or a value is malformed.
        """
        _require_keys(record, REQUIRED_DECISION_KEYS, "decision")
        try:
            status = SuggestionStatus(record["status"])
        except ValueError as exc:
            raise ValueError("status is not a valid suggestion status") from exc
        try:
            decided_at = datetime.fromisoformat(record["decided_at"])
        except (TypeError, ValueError) as exc:
            raise ValueError("decided_at must be an ISO-8601 timestamp") from exc
        return cls(
            suggestion_id=record["suggestion_id"],
            status=status,
            reviewer=record["reviewer"],
            decided_at=decided_at,
            final_premise=record["final_premise"],
            note=record["note"],
        )


def _require_keys(record: Mapping[str, Any], keys: tuple[str, ...], kind: str) -> None:
    """Raise ValueError if ``record`` is not a mapping or is missing any key."""
    if not isinstance(record, Mapping):
        raise ValueError(f"{kind} record must be a mapping, got {type(record).__name__}")
    missing = [key for key in keys if key not in record]
    if missing:
        raise ValueError(f"{kind} record missing keys: {', '.join(missing)}")
