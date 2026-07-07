"""The authorization model: actions, per-story grants, and the deny-by-default policy.

ADR-004 Decision 1/2: access to a story's content is granted only by an explicit
role, never by omission. This module holds the pure decision logic — given a
principal, a story's grants, and an action, is it allowed? — with **no** I/O, no
identity source, and no audit. Enforcement (raising, decrypting, logging) is layered
on top at the store boundary; keeping the decision pure makes the whole grant table
unit-testable in isolation.

The grant table (:data:`_ROLE_ACTIONS`) is the initial cut of ADR-004 Decision 2 and
is expected to be refined in review and with the ADR-002 collaborator (Decision 7),
since the reviewer/therapist boundaries touch the confidentiality questions ADR-001
Decision 4.3 and ADR-002 Decision 5 flag.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from kathai_chithiram.access.principal import Principal, Role
from kathai_chithiram.errors import AccessDeniedError

__all__ = [
    "Action",
    "AccessPolicy",
    "ChildGrants",
    "ChildGrantsSource",
    "Grants",
    "StoryGrants",
]

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class Action(Enum):
    """An operation on a story's artifacts that must be authorized (ADR-004 D1)."""

    READ_CONTENT = "read_content"  # scene script, media, artifact bytes
    WRITE_CONTENT = "write_content"  # store the story / scene script / media
    READ_INTAKE = "read_intake"  # intake + consent record
    WRITE_REVIEW = "write_review"  # record a human-review decision (KC-7)
    READ_FEEDBACK = "read_feedback"  # session feedback / evidence view (ADR-002)
    WRITE_FEEDBACK = "write_feedback"  # append a session feedback primitive
    READ_SUGGESTIONS = "read_suggestions"  # premise suggestions (ADR-002)
    DECIDE_SUGGESTION = "decide_suggestion"  # record accept / edit / dismiss
    MANAGE_STORY = "manage_story"  # create, assign roles, mark delivered, delete


#: The initial per-role action grants (ADR-004 Decision 2). Deny-by-default: any
#: (role, action) pair not listed here is refused. Reviewed, not engineer-final.
_ROLE_ACTIONS: dict[Role, frozenset[Action]] = {
    Role.FAMILY_OWNER: frozenset(
        {
            Action.READ_CONTENT,
            Action.WRITE_CONTENT,
            Action.READ_INTAKE,
            Action.WRITE_FEEDBACK,
            Action.WRITE_REVIEW,
            Action.MANAGE_STORY,
        }
    ),
    Role.REVIEWER: frozenset(
        {
            Action.READ_CONTENT,
            Action.READ_INTAKE,
            Action.WRITE_REVIEW,
        }
    ),
    Role.THERAPIST: frozenset(
        {
            Action.READ_CONTENT,
            Action.READ_FEEDBACK,
            Action.READ_SUGGESTIONS,
            Action.DECIDE_SUGGESTION,
        }
    ),
}


@runtime_checkable
class Grants(Protocol):
    """The one thing an :class:`AccessPolicy` decision needs: a principal → role map.

    Both :class:`StoryGrants` (per-story, ADR-004) and :class:`ChildGrants`
    (child-scoped, ADR-005 D3) satisfy this, so the pure policy works against either
    without knowing whether authority is granted at the story or the child level.
    """

    def role_of(self, principal: Principal) -> Role | None:
        """Return the principal's role for this resource, or ``None`` if it has none."""
        ...


@runtime_checkable
class ChildGrantsSource(Protocol):
    """Resolves a child's grants + consent for the enforcement boundary (ADR-005 D3).

    The store layer authorizes a child-scoped story by asking this source for the
    child's live :class:`Grants` and whether parental consent is on record — without
    depending on the ``people`` package (which depends on this one). The concrete
    ``PeopleRegistry`` satisfies it structurally.
    """

    def child_grants(self, child_id: str) -> Grants:
        """Return the child's grants, or raise if the child is unknown."""
        ...

    def has_consent(self, child_id: str) -> bool:
        """Whether parental consent is on record for the child."""
        ...

    def family_id_of(self, child_id: str) -> str:
        """Return the child's family id, or raise if the child is unknown."""
        ...


@dataclass(frozen=True)
class ChildGrants:
    """Who may act on a child's content: family members plus child-scoped assignments.

    ADR-005 Decision 3 lifts the grant unit from a single story to the **child** — a
    child's stories and program inherit these grants. Every parent in the child's
    family is an owner of the child's content (``FAMILY_OWNER``); therapists/reviewers
    are assigned to the *child*, so one assignment covers all of that child's stories.

    Args:
        child_id: The child this binding is for (log-safe context).
        family_member_ids: Opaque principal ids of the child's family parents (at
            least one); each holds ``FAMILY_OWNER``.
        assignments: Map of principal id to an **assignable** role
            (``REVIEWER`` / ``THERAPIST``) assigned to this child. May be empty.

    Raises:
        ValueError: If an id is empty/unsafe, ``family_member_ids`` is empty, an
            assignment uses a non-assignable role, or a family member also appears as
            an assignee (a role conflict on the same child).
    """

    child_id: str
    family_member_ids: frozenset[str]
    assignments: Mapping[str, Role]

    def __post_init__(self) -> None:
        if not _ID_PATTERN.match(self.child_id):
            raise ValueError("child_id must be a non-empty opaque id (^[A-Za-z0-9_-]+$)")
        if not self.family_member_ids:
            raise ValueError("a child must have at least one family member")
        for member in self.family_member_ids:
            if not _ID_PATTERN.match(member):
                raise ValueError("family member id must be a non-empty opaque id")
        if not isinstance(self.assignments, Mapping):
            raise ValueError("assignments must be a mapping of principal id to Role")
        for principal_id, role in self.assignments.items():
            if not _ID_PATTERN.match(principal_id):
                raise ValueError("assignment principal id must be a non-empty opaque id")
            if not isinstance(role, Role):
                raise ValueError("assignment role must be a Role")
            if not role.is_assignable:
                raise ValueError("family_owner is granted by family membership, not assignment")
            if principal_id in self.family_member_ids:
                raise ValueError("a family member must not also be an assignee for the same child")

    def role_of(self, principal: Principal) -> Role | None:
        """Return the principal's role for this child, or ``None`` if it has none."""
        if principal.principal_id in self.family_member_ids:
            return Role.FAMILY_OWNER
        return self.assignments.get(principal.principal_id)


@dataclass(frozen=True)
class StoryGrants:
    """Who may act on one story: its owner plus any role assignments (ADR-004 D4).

    This is the binding an :class:`AccessPolicy` decision is evaluated against. It
    holds only opaque principal ids — never names — so it inherits the minimization
    and hard-delete regime when persisted in store metadata.

    Args:
        owner_id: The owning principal (the family/parent). Always
            :attr:`~kathai_chithiram.access.principal.Role.FAMILY_OWNER`.
        assignments: Map of principal id to an **assignable** role
            (``REVIEWER`` / ``THERAPIST``). May be empty.

    Raises:
        ValueError: If an id is empty/unsafe, an assignment uses a non-assignable
            role (``FAMILY_OWNER``), or the owner also appears as an assignee.
    """

    owner_id: str
    assignments: Mapping[str, Role]

    def __post_init__(self) -> None:
        if not _ID_PATTERN.match(self.owner_id):
            raise ValueError("owner_id must be a non-empty opaque id (^[A-Za-z0-9_-]+$)")
        if not isinstance(self.assignments, Mapping):
            raise ValueError("assignments must be a mapping of principal id to Role")
        for principal_id, role in self.assignments.items():
            if not _ID_PATTERN.match(principal_id):
                raise ValueError("assignment principal id must be a non-empty opaque id")
            if not isinstance(role, Role):
                raise ValueError("assignment role must be a Role")
            if not role.is_assignable:
                raise ValueError("family_owner is the story owner, not an assignable role")
            if principal_id == self.owner_id:
                raise ValueError("the owner must not also appear as an assignee")

    def role_of(self, principal: Principal) -> Role | None:
        """Return the principal's role for this story, or ``None`` if it has none."""
        if principal.principal_id == self.owner_id:
            return Role.FAMILY_OWNER
        return self.assignments.get(principal.principal_id)


class AccessPolicy:
    """The deny-by-default authorization decision (ADR-004 Decision 1/2).

    Stateless and pure: it maps ``(principal, grants, action)`` to allow/deny using
    the fixed role→actions table. It performs no I/O and writes no audit — the caller
    at the enforcement boundary does that.
    """

    def role_for(self, principal: Principal, grants: Grants) -> Role | None:
        """Return the principal's role for the story, or ``None`` if unrelated."""
        return grants.role_of(principal)

    def is_allowed(self, principal: Principal, grants: Grants, action: Action) -> bool:
        """Return whether ``principal`` may perform ``action`` on the story.

        Args:
            principal: The authenticated identity requesting access.
            grants: The story's owner + assignments.
            action: The operation being attempted.

        Returns:
            ``True`` only if the principal has a role for the story and that role's
            grant set includes ``action``; ``False`` otherwise (deny-by-default).
        """
        role = grants.role_of(principal)
        if role is None:
            return False
        return action in _ROLE_ACTIONS.get(role, frozenset())

    def authorize(
        self,
        principal: Principal,
        grants: Grants,
        action: Action,
        *,
        story_id: str,
    ) -> Role:
        """Authorize ``action`` or raise; return the principal's role on success.

        Args:
            principal: The authenticated identity requesting access.
            grants: The story's owner + assignments.
            action: The operation being attempted.
            story_id: The story id, for the error's log-safe context.

        Returns:
            The role the principal holds for the story (useful to the caller).

        Raises:
            AccessDeniedError: If the principal has no role for the story, or its
                role does not grant ``action``. Fails closed — the caller must not
                proceed to read, decrypt, or write.
        """
        role = grants.role_of(principal)
        if role is None:
            raise AccessDeniedError(
                action.value,
                "principal has no role for this story",
                principal_id=principal.principal_id,
                story_id=story_id,
            )
        if action not in _ROLE_ACTIONS.get(role, frozenset()):
            raise AccessDeniedError(
                action.value,
                f"role {role.value!r} does not grant this action",
                principal_id=principal.principal_id,
                story_id=story_id,
            )
        return role
