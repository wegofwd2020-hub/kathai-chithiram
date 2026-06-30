"""The per-session feedback primitive — the capture-track contract of ADR-002.

This is the *low-risk capture layer* that ADR-002 green-lights: a small, fixed,
quantifiable record of how one viewing went, so longitudinal data can accrue.
It is deliberately **not** the progress engine — there is no computed measure
and no premise suggestion here (those are gated behind ADR-002 Decision 7).

Design (ADR-002 Decision 1):

* A record is keyed to a therapist-owned ``goal_id`` and the ``story_id`` it
  pertains to — both opaque ids (safe character set), never free text.
* The captured primitives are exactly: ``prompt_level``
  (refused / prompted / independent), ``completed``, and ``mood_checkin`` (a
  short, calm ordinal scale), plus the time it was recorded.
* There is **no free-text / clinical-notes field** — that would invite PII or
  disclosure capture and clinical-record creep, against minimization
  (PRIVACY.md §2/§3). The data is High-sensitivity behavioral child data and
  inherits the privacy regime (retention, verifiable hard-delete, no-training).

The record is a raw capture, not a judgement: interpreting it (trends,
thresholds, mastery) is the gated engine's job and must be designed with a
professional collaborator (ADR-002 Decision 7).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any

__all__ = [
    "REQUIRED_FEEDBACK_KEYS",
    "MoodCheckin",
    "PromptLevel",
    "SessionFeedback",
]

# Opaque-id charset for goal/story ids: no whitespace or punctuation that could
# smuggle free text (and matches the store's story-id rules).
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

#: Keys a serialized feedback record must carry.
REQUIRED_FEEDBACK_KEYS: tuple[str, ...] = (
    "goal_id",
    "story_id",
    "prompt_level",
    "completed",
    "mood_checkin",
    "recorded_at",
)


class PromptLevel(str, Enum):
    """How much help the child needed to do the target behaviour this session.

    Ordered from most to least support. The raw observation only — no score is
    derived from it here.
    """

    REFUSED = "refused"
    PROMPTED = "prompted"
    INDEPENDENT = "independent"


class MoodCheckin(IntEnum):
    """A short, calm 5-point ordinal mood check-in (1 = most upset, 5 = happiest).

    A gentle self/observed scale, stored as its ordinal. It is a raw capture,
    not a clinical or emotional assessment (ADR-002 Decision 2).
    """

    VERY_UNHAPPY = 1
    UNHAPPY = 2
    NEUTRAL = 3
    HAPPY = 4
    VERY_HAPPY = 5


@dataclass(frozen=True)
class SessionFeedback:
    """One session's feedback primitive, keyed to a goal and a story.

    Args:
        goal_id: The therapist-owned goal this session worked toward (opaque id).
        story_id: The story/animation the session used (opaque id).
        prompt_level: How much support the child needed.
        completed: Whether the child completed the target behaviour.
        mood_checkin: The session mood check-in.
        recorded_at: When the feedback was captured (timezone-aware recommended).

    Raises:
        ValueError: If an id is empty or unsafe, or a field has the wrong type.
    """

    goal_id: str
    story_id: str
    prompt_level: PromptLevel
    completed: bool
    mood_checkin: MoodCheckin
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not _ID_PATTERN.match(self.goal_id):
            raise ValueError("goal_id must be a non-empty opaque id (^[A-Za-z0-9_-]+$)")
        if not _ID_PATTERN.match(self.story_id):
            raise ValueError("story_id must be a non-empty opaque id (^[A-Za-z0-9_-]+$)")
        if not isinstance(self.prompt_level, PromptLevel):
            raise ValueError("prompt_level must be a PromptLevel")
        # bool is an int subclass; guard against passing 0/1 or a mood by mistake.
        if not isinstance(self.completed, bool):
            raise ValueError("completed must be a bool")
        if not isinstance(self.mood_checkin, MoodCheckin):
            raise ValueError("mood_checkin must be a MoodCheckin")
        if not isinstance(self.recorded_at, datetime):
            raise ValueError("recorded_at must be a datetime")

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-serializable record (enums as their stored values)."""
        return {
            "goal_id": self.goal_id,
            "story_id": self.story_id,
            "prompt_level": self.prompt_level.value,
            "completed": self.completed,
            "mood_checkin": int(self.mood_checkin),
            "recorded_at": self.recorded_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> SessionFeedback:
        """Parse and validate a stored/external feedback record.

        Args:
            record: A decoded record (e.g. one line of the feedback log).

        Returns:
            The validated :class:`SessionFeedback`.

        Raises:
            ValueError: If a key is missing or a value is malformed.
        """
        if not isinstance(record, Mapping):
            raise ValueError(f"feedback record must be a mapping, got {type(record).__name__}")
        missing = [key for key in REQUIRED_FEEDBACK_KEYS if key not in record]
        if missing:
            raise ValueError(f"feedback record missing keys: {', '.join(missing)}")

        try:
            prompt_level = PromptLevel(record["prompt_level"])
        except ValueError as exc:
            raise ValueError("prompt_level is not a valid level") from exc

        completed = record["completed"]
        if not isinstance(completed, bool):
            raise ValueError("completed must be a bool")

        mood_raw = record["mood_checkin"]
        if isinstance(mood_raw, bool) or not isinstance(mood_raw, int):
            raise ValueError("mood_checkin must be an integer 1-5")
        try:
            mood = MoodCheckin(mood_raw)
        except ValueError as exc:
            raise ValueError("mood_checkin must be an integer 1-5") from exc

        try:
            recorded_at = datetime.fromisoformat(record["recorded_at"])
        except (TypeError, ValueError) as exc:
            raise ValueError("recorded_at must be an ISO-8601 timestamp") from exc

        return cls(
            goal_id=record["goal_id"],
            story_id=record["story_id"],
            prompt_level=prompt_level,
            completed=completed,
            mood_checkin=mood,
            recorded_at=recorded_at,
        )
