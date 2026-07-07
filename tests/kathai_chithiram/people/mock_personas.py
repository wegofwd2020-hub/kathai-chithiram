"""Synthetic test personas for the people/family domain.

A test-only layer (CLAUDE.md: no real data in fixtures). Pairs each domain
opaque id with an email-shaped ``login_handle``; the domain model itself holds
no email. Committed handles are always ``@example.test`` — the owner's real
inboxes are supplied at runtime via the git-ignored ``personas.local.json``
override (see :mod:`resolve_handles`), never committed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from kathai_chithiram.access.principal import Role
from kathai_chithiram.people.models import (
    AgeBand,
    Child,
    Family,
    ParentalConsent,
    Therapist,
)
from kathai_chithiram.people.registry import PeopleRegistry

__all__ = [
    "Persona",
    "PARENT",
    "CHILD",
    "THERAPIST",
    "FAMILY_ID",
    "POLICY_VERSION",
    "mock_family",
    "mock_registry",
]

#: Opaque family id shared by the mock personas.
FAMILY_ID = "fam-mock-001"

#: Synthetic consent policy version (not a real notice version).
POLICY_VERSION = "v0-mock"


@dataclass(frozen=True)
class Persona:
    """A synthetic test identity: a domain opaque id plus a login handle.

    Attributes:
        key: The override-lookup key (``"parent"`` / ``"child"`` / ``"therapist"``).
        subject_id: The opaque id used in the domain layer (a principal id for the
            parent/therapist, the child id for the child).
        login_handle: An email-shaped handle. Committed value ends in
            ``@example.test``; the owner's real inbox overrides it at runtime only.
    """

    key: str
    subject_id: str
    login_handle: str


#: The owning parent of the mock family.
PARENT = Persona("parent", "parent-mock-001", "parent@example.test")

#: The child in the mock family (addressed via the guardian inbox for delivery E2E).
CHILD = Persona("child", "child-mock-001", "child@example.test")

#: A therapist assigned to the mock child.
THERAPIST = Persona("therapist", "therapist-mock-001", "therapist@example.test")


def mock_family() -> Family:
    """Return the synthetic :class:`Family` for the mock personas.

    Returns:
        A one-parent family owned by :data:`PARENT`.
    """
    return Family(
        family_id=FAMILY_ID,
        owner_id=PARENT.subject_id,
        member_ids=frozenset({PARENT.subject_id}),
    )


def mock_registry() -> PeopleRegistry:
    """Return a :class:`PeopleRegistry` with the mock family fully wired.

    The family, child, and therapist are registered; the therapist is assigned to
    the child (``Role.THERAPIST``); and parental consent is recorded so the child's
    content is consent-gated.

    Returns:
        A ready-to-use registry for consent-gated, grant-wired tests.
    """
    reg = PeopleRegistry()
    reg.add_family(mock_family())
    reg.add_child(
        Child(
            child_id=CHILD.subject_id,
            family_id=FAMILY_ID,
            age_band=AgeBand.AGE_6_8,
        )
    )
    reg.add_therapist(Therapist(principal_id=THERAPIST.subject_id))
    reg.assign(CHILD.subject_id, THERAPIST.subject_id, Role.THERAPIST)
    reg.record_consent(
        ParentalConsent(
            consenting_parent_id=PARENT.subject_id,
            child_id=CHILD.subject_id,
            policy_version=POLICY_VERSION,
            granted_at=datetime.now(timezone.utc),
        )
    )
    return reg
