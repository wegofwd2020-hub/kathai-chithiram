"""Per-session feedback capture — the low-risk capture track of ADR-002.

Records how one viewing went (``prompt_level``, ``completed``, ``mood_checkin``)
keyed to a therapist-owned goal, so longitudinal data can accrue. This package
is **capture only**: it computes no progress measure and suggests no premise
change — that engine is deliberately gated behind ADR-002 Decision 7.
"""

from __future__ import annotations

from kathai_chithiram.feedback.capture import (
    load_session_feedback,
    record_session_feedback,
)
from kathai_chithiram.feedback.schema import (
    MoodCheckin,
    PromptLevel,
    SessionFeedback,
)

__all__ = [
    "MoodCheckin",
    "PromptLevel",
    "SessionFeedback",
    "load_session_feedback",
    "record_session_feedback",
]
