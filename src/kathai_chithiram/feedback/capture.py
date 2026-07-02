"""Capture and load per-session feedback through the artifact store.

Thin seam between the :class:`SessionFeedback` contract and the store's feedback
log. This is the whole of the capture track (ADR-002): record a session's
primitives, read them back. No progress is computed and no premise is suggested
here — that engine is gated behind ADR-002 Decision 7.
"""

from __future__ import annotations

from kathai_chithiram.feedback.schema import SessionFeedback
from kathai_chithiram.storage import StoryStore

__all__ = ["load_session_feedback", "record_session_feedback"]


def record_session_feedback(
    *, store: StoryStore, story_id: str, feedback: SessionFeedback
) -> None:
    """Append one session's feedback to ``story_id``'s log.

    Args:
        store: The artifact store holding the story.
        story_id: The story the session used.
        feedback: The validated feedback primitive to record.

    Raises:
        StoryNotFoundError: If the story does not exist.
        ValueError: If ``story_id`` is unsafe.
        OSError: If the log cannot be written.
    """
    store.append_session_feedback(story_id, feedback.to_record())


def load_session_feedback(
    *, store: StoryStore, story_id: str
) -> list[SessionFeedback]:
    """Return every captured :class:`SessionFeedback` for ``story_id``, in order.

    Args:
        store: The artifact store holding the story.
        story_id: The story to read feedback for.

    Returns:
        The parsed feedback records (empty if none were captured).

    Raises:
        StoryNotFoundError: If the story does not exist.
        ValueError: If ``story_id`` is unsafe, or a stored record is malformed.
    """
    return [
        SessionFeedback.from_record(record)
        for record in store.read_session_feedback(story_id)
    ]
