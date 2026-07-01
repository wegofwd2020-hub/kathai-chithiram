"""Parent-facing intake: the product's front door and legal-basis checkpoint.

A parent submits a story; intake captures the minimum data plus explicit
consent (PRIVACY.md §2/§3/§8), then runs the generation pipeline and stores a
review-gated draft. Nothing is delivered to a child here — rendering and the
human-review gate are downstream.

* :class:`ParentSubmission` / :class:`Consent` — the minimal, consented payload.
* :func:`minimization_warnings` — advisory nudges against over-sharing.
* :func:`format_notice_preamble` / :data:`PRIVACY_NOTICE_VERSION` — the
  parent-facing privacy notice shown before consent, and its recorded version.
* :func:`submit_intake` — consent gate -> generate -> store (story + script +
  consent record, incl. the privacy-notice version the consent was given under).
"""

from __future__ import annotations

from kathai_chithiram.intake.privacy_notice import (
    PRIVACY_NOTICE_DOC,
    PRIVACY_NOTICE_SUMMARY,
    PRIVACY_NOTICE_VERSION,
    format_notice_preamble,
)
from kathai_chithiram.intake.service import IntakeResult, submit_intake
from kathai_chithiram.intake.submission import (
    Consent,
    ParentSubmission,
    minimization_warnings,
)

__all__ = [
    "PRIVACY_NOTICE_DOC",
    "PRIVACY_NOTICE_SUMMARY",
    "PRIVACY_NOTICE_VERSION",
    "Consent",
    "IntakeResult",
    "ParentSubmission",
    "format_notice_preamble",
    "minimization_warnings",
    "submit_intake",
]
