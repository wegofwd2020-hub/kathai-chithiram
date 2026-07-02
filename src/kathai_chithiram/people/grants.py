"""Derive a child's access grants from the people/family model (ADR-005 D3).

The pure authorization layer (:mod:`kathai_chithiram.access.policy`) knows only
opaque ids; this bridges the domain types to it, building the
:class:`~kathai_chithiram.access.policy.ChildGrants` a story or program inherits from
its child: every parent in the child's family is an owner, plus any therapist/reviewer
assigned to that child.
"""

from __future__ import annotations

from collections.abc import Mapping

from kathai_chithiram.access.policy import ChildGrants
from kathai_chithiram.access.principal import Role
from kathai_chithiram.people.models import Child, Family

__all__ = ["child_grants"]


def child_grants(
    child: Child,
    family: Family,
    *,
    assignments: Mapping[str, Role] | None = None,
) -> ChildGrants:
    """Build the child-scoped grants for a child in its family.

    Args:
        child: The child whose content the grants govern.
        family: The child's family; its members become the child's owners.
        assignments: Optional map of principal id to an assignable role
            (``THERAPIST`` / ``REVIEWER``) assigned to this child.

    Returns:
        A :class:`ChildGrants` whose ``family_member_ids`` are the family's parents and
        whose ``assignments`` are the child-scoped therapist/reviewer grants.

    Raises:
        ValueError: If ``child`` does not belong to ``family`` (mismatched
            ``family_id``), or the resulting grants are invalid (e.g. an assignee is
            also a family member).
    """
    if child.family_id != family.family_id:
        raise ValueError("child does not belong to this family (family_id mismatch)")
    return ChildGrants(
        child_id=child.child_id,
        family_member_ids=family.member_ids,
        assignments=dict(assignments or {}),
    )
