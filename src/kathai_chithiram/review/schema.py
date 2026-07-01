"""The human-review decision — the deliver-gate record of KC-7.

A :class:`ReviewRecord` is the durable, non-sensitive proof that a person
looked at a rendered draft and made a call (CONTENT_SAFETY.md §6): who reviewed
it, the decision, when, an optional operator-authored reason, and a
*fingerprint* of what was reviewed. Approving a draft is what promotes it from
an undelivered draft to a delivered animation; rejecting it leaves it for the
retention sweep.

Like the intake/consent record, this is deliberately **non-sensitive**: it holds
opaque ids, enums, counts, and the provider posture — never story text, a
caption, narration, or a child's name (PRIVACY.md §6). The ``reason`` is
operator-authored review notes (e.g. "scene 3 flashes too fast"), not story
content. The record lives in the story directory, so a verifiable hard-delete
removes it along with everything else.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

__all__ = ["REQUIRED_REVIEW_KEYS", "ReviewDecision", "ReviewRecord"]

#: Keys a serialized review record must carry.
REQUIRED_REVIEW_KEYS: tuple[str, ...] = (
    "story_id",
    "decision",
    "reviewer",
    "decided_at",
    "reason",
    "reviewed",
)


class ReviewDecision(str, Enum):
    """The outcome of a human review of a rendered draft.

    ``APPROVED`` promotes the draft to delivered; ``REJECTED`` leaves it
    undelivered (and therefore eligible for the retention sweep).
    """

    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ReviewRecord:
    """One human-review decision for a story's rendered draft.

    Args:
        story_id: The story reviewed (opaque id).
        decision: Approve or reject.
        reviewer: An identifier for the person who reviewed (a name or handle).
            Recorded for the audit trail; must be non-empty.
        decided_at: When the decision was made (timezone-aware recommended).
        reason: Operator-authored review notes. Required for a rejection,
            optional for an approval. Never story text.
        reviewed: A non-sensitive fingerprint of what was reviewed (e.g. scene
            count, duration, media file names, provider posture). Empty dict if
            not supplied.

    Raises:
        ValueError: If the reviewer is empty, a rejection has no reason, or a
            field has the wrong type.
    """

    story_id: str
    decision: ReviewDecision
    reviewer: str
    decided_at: datetime
    reason: str | None = None
    reviewed: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.decision, ReviewDecision):
            raise ValueError("decision must be a ReviewDecision")
        if not self.reviewer or not self.reviewer.strip():
            raise ValueError("reviewer must be a non-empty identifier")
        if not isinstance(self.decided_at, datetime):
            raise ValueError("decided_at must be a datetime")
        if self.decision is ReviewDecision.REJECTED and not (self.reason or "").strip():
            raise ValueError("a rejection must include a reason")

    @property
    def approved(self) -> bool:
        """Whether this decision approves the draft for delivery."""
        return self.decision is ReviewDecision.APPROVED

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-serializable record (enum as its stored value)."""
        return {
            "story_id": self.story_id,
            "decision": self.decision.value,
            "reviewer": self.reviewer,
            "decided_at": self.decided_at.isoformat(),
            "reason": self.reason,
            "reviewed": self.reviewed,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ReviewRecord:
        """Parse and validate a stored review record.

        Args:
            record: A decoded review record (e.g. ``review.json``).

        Returns:
            The validated :class:`ReviewRecord`.

        Raises:
            ValueError: If a key is missing or a value is malformed.
        """
        if not isinstance(record, Mapping):
            raise ValueError(f"review record must be a mapping, got {type(record).__name__}")
        missing = [key for key in REQUIRED_REVIEW_KEYS if key not in record]
        if missing:
            raise ValueError(f"review record missing keys: {', '.join(missing)}")

        try:
            decision = ReviewDecision(record["decision"])
        except ValueError as exc:
            raise ValueError("decision is not a valid review decision") from exc

        try:
            decided_at = datetime.fromisoformat(record["decided_at"])
        except (TypeError, ValueError) as exc:
            raise ValueError("decided_at must be an ISO-8601 timestamp") from exc

        reviewed = record["reviewed"]
        if not isinstance(reviewed, Mapping):
            raise ValueError("reviewed must be a mapping")

        return cls(
            story_id=record["story_id"],
            decision=decision,
            reviewer=record["reviewer"],
            decided_at=decided_at,
            reason=record["reason"],
            reviewed=dict(reviewed),
        )
