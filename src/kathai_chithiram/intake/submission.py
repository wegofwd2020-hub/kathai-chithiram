"""The parent-facing intake model: a vetted story submission.

Intake is the product's front door and its legal-basis checkpoint. A
:class:`ParentSubmission` carries only the **minimum** data needed to make the
animation (PRIVACY.md §2/§3): the free-form story, the child's first name (and
optional nickname), and the parent's explicit :class:`Consent`. It deliberately
has no field for a surname, date of birth, address, diagnosis, or any other
out-of-scope identifier — minimization is enforced by the shape of what we
collect, not by trusting the caller to omit it.

Two checks live here:

* :meth:`ParentSubmission.missing_consents` / :meth:`Consent.granted` — the hard
  gate. A submission cannot be processed until every consent is granted
  (enforced in :mod:`kathai_chithiram.intake.service`).
* :func:`minimization_warnings` — a *best-effort, advisory* scan that flags
  shapes which look like out-of-scope personal data the parent need not share
  (a multi-word name, a date of birth, a phone number, an address). It is a
  nudge, never a block, and never echoes the matched text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["Consent", "ParentSubmission", "minimization_warnings"]

#: Stable keys for the three required consents, in display order.
REQUIRED_CONSENTS: tuple[str, ...] = ("is_guardian", "ai_processing", "human_review_ack")


@dataclass(frozen=True)
class Consent:
    """The explicit consents a parent must grant before intake proceeds.

    Each flag maps to a PRIVACY.md commitment; all three are required (the
    legal basis is parental consent, §8).

    Args:
        is_guardian: The submitter is the child's parent or legal guardian
            (§2 parental control).
        ai_processing: The story may be sent to an LLM provider configured for
            no-training / zero-retention (§4/§6).
        human_review_ack: The submitter understands the animation is reviewed by
            a human before it reaches the child (CLAUDE.md review gate).
    """

    is_guardian: bool
    ai_processing: bool
    human_review_ack: bool

    def missing(self) -> tuple[str, ...]:
        """Return the keys of any required consent not granted, in order."""
        values = {
            "is_guardian": self.is_guardian,
            "ai_processing": self.ai_processing,
            "human_review_ack": self.human_review_ack,
        }
        return tuple(key for key in REQUIRED_CONSENTS if not values[key])

    @property
    def granted(self) -> bool:
        """Whether every required consent has been granted."""
        return not self.missing()

    def as_record(self) -> dict[str, bool]:
        """Return a non-sensitive dict of the consent flags (safe to store/log)."""
        return {
            "is_guardian": self.is_guardian,
            "ai_processing": self.ai_processing,
            "human_review_ack": self.human_review_ack,
        }


@dataclass(frozen=True)
class ParentSubmission:
    """One parent's vetted story submission — the minimal intake payload.

    Args:
        story_text: The free-form parent-authored story.
        child_first_name: The child's first name, used only to build the
            pseudonymization mapping (stripped before any provider call,
            reinserted into captions at render time). Never stored in the scene
            script.
        consent: The parent's explicit consents.
        child_nickname: An optional second identifier to strip as well.

    Raises:
        ValueError: If the story text or first name is blank.
    """

    story_text: str
    child_first_name: str
    consent: Consent
    child_nickname: str | None = None

    def __post_init__(self) -> None:
        if not self.story_text or not self.story_text.strip():
            raise ValueError("story_text must be a non-empty story")
        if not self.child_first_name or not self.child_first_name.strip():
            raise ValueError("child_first_name must be a non-empty name")

    def missing_consents(self) -> tuple[str, ...]:
        """Return the keys of any required consent not yet granted."""
        return self.consent.missing()


# Advisory minimization patterns. Each entry is (compiled regex, message). The
# message is fixed text — it must never embed the matched substring, so the
# warning is always safe to store and show.
_MINIMIZATION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
        "The story may contain a date of birth. We don't need it — please remove it.",
    ),
    (
        re.compile(r"\bborn on\b", re.IGNORECASE),
        "The story may mention a date of birth. We don't need it — please remove it.",
    ),
    (
        re.compile(r"\b\d{3}[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b"),
        "The story may contain a phone number or ID. We don't need it — please remove it.",
    ),
    (
        re.compile(
            r"\b\d+\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr)\b"
        ),
        "The story may contain a home address. We don't need it — please remove it.",
    ),
    (
        re.compile(
            r"\b(?:diagnos(?:is|ed)|ICD-?10|prescription|medication|dose|mg)\b",
            re.IGNORECASE,
        ),
        "The story may contain medical or diagnostic detail. We only need the "
        "situation in plain words, not medical records.",
    ),
)


def minimization_warnings(submission: ParentSubmission) -> list[str]:
    """Return advisory warnings about out-of-scope personal data in a submission.

    Best-effort only: a heuristic scan to nudge a parent away from sharing more
    than is needed (PRIVACY.md §3). It is **not** authoritative and never blocks
    intake; an empty list does not certify the submission is minimal. The
    returned messages contain no story text.

    Args:
        submission: The submission to scan.

    Returns:
        A list of human-readable advisory messages (empty if nothing matched).
    """
    warnings: list[str] = []

    # A first-name field that contains whitespace is likely a full name; we only
    # want the first name (no surname — §3).
    if len(submission.child_first_name.split()) > 1:
        warnings.append(
            "We only need the child's first name (no surname). Please enter just "
            "the first name."
        )

    for pattern, message in _MINIMIZATION_PATTERNS:
        if pattern.search(submission.story_text):
            warnings.append(message)

    return warnings
