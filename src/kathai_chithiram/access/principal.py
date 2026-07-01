"""The identity primitives of the access-control layer (ADR-004, KC-11).

A :class:`Principal` is an authenticated identity — an opaque id, never a name (a
child's real name is a render-time substitution only; CLAUDE.md). A :class:`Role` is
what a principal *is relative to a particular story*, not an intrinsic property: the
same person may own one family's story and be a reviewer on another. The mapping from
a principal to a role for a given story lives in that story's grants
(:class:`~kathai_chithiram.access.policy.StoryGrants`), so identity here carries no
authority on its own — authority is always evaluated against a specific story.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

__all__ = ["Principal", "Role"]

#: Opaque-id charset for principal ids — matches the store's story-id rules and the
#: other primitives; no whitespace or punctuation that could smuggle a name or free
#: text into an identity.
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class Role(Enum):
    """What a principal is *relative to a story* (ADR-004 Decision 2).

    Aligned to the actor model (``BRAND.md`` §7) and the existing review (KC-7) and
    progress (ADR-002) reviewers. A principal with no role for a story has no access
    to it (deny-by-default).

    Members:
        FAMILY_OWNER: The family/parent who submitted the story. Only ever the
            story's owner — never an assignment.
        REVIEWER: A human assigned to review a draft before delivery (KC-7).
        THERAPIST: A clinician assigned to the story's goal/feedback (ADR-002).
    """

    FAMILY_OWNER = "family_owner"
    REVIEWER = "reviewer"
    THERAPIST = "therapist"

    @property
    def is_assignable(self) -> bool:
        """Whether this role is granted by assignment (vs. being the story owner)."""
        return self is not Role.FAMILY_OWNER


@dataclass(frozen=True)
class Principal:
    """An authenticated identity — an opaque id, carrying no authority by itself.

    Args:
        principal_id: The opaque identity id (safe charset). Never a name or any
            personal identifier.

    Raises:
        ValueError: If ``principal_id`` is empty or contains unsafe characters.
    """

    principal_id: str

    def __post_init__(self) -> None:
        if not _ID_PATTERN.match(self.principal_id):
            raise ValueError("principal_id must be a non-empty opaque id (^[A-Za-z0-9_-]+$)")
