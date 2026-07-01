"""Human-review gate: review a rendered draft, then approve or reject it (KC-7).

Codifies the deliver-gate of CONTENT_SAFETY.md §6. Approving a draft is what
promotes it from an undelivered draft to a delivered animation (and shields it
from the retention sweep); rejecting it leaves it for retention. The decision is
recorded non-sensitively in the story directory, so a hard-delete removes it too.
"""

from __future__ import annotations

from kathai_chithiram.review.schema import ReviewDecision, ReviewRecord
from kathai_chithiram.review.service import (
    ReviewBundle,
    load_review_bundle,
    review_story,
)

__all__ = [
    "ReviewBundle",
    "ReviewDecision",
    "ReviewRecord",
    "load_review_bundle",
    "review_story",
]
