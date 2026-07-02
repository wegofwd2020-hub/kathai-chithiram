"""The people/family registry — a domain service over the ADR-005 identity model.

Holds the families, children, therapists, per-child assignments, and parental
consents of the multi-user platform, and resolves a child's
:class:`~kathai_chithiram.access.policy.ChildGrants` (ADR-005 D3). Like
:class:`~kathai_chithiram.storage.StoryArtifactStore`, it is an **unguarded** domain
service: *who* may create a family or assign a therapist is enforced one layer up (the
CLI / a guarded wrapper), not here. It stores only opaque ids, age bands, and consent
records — never a name or a date of birth.

This is an in-memory registry; durable, encrypted persistence and cascade erasure
follow the per-child key tree in ``docs/RETENTION_ERASURE_DESIGN.md`` (a later slice).
"""

from __future__ import annotations

from kathai_chithiram.access.policy import ChildGrants
from kathai_chithiram.access.principal import Role
from kathai_chithiram.errors import PeopleError
from kathai_chithiram.people.grants import child_grants
from kathai_chithiram.people.models import Child, Family, ParentalConsent, Therapist

__all__ = ["PeopleRegistry"]


class PeopleRegistry:
    """An in-memory registry of families, children, therapists, and consents.

    All lookups fail closed with :class:`~kathai_chithiram.errors.PeopleError` (never a
    silent default), and every write rejects a duplicate, unknown, or cross-family
    record so the identity graph stays consistent.
    """

    def __init__(self) -> None:
        self._families: dict[str, Family] = {}
        self._children: dict[str, Child] = {}
        self._therapists: dict[str, Therapist] = {}
        self._assignments: dict[str, dict[str, Role]] = {}
        self._consents: dict[str, list[ParentalConsent]] = {}

    # ── registration ─────────────────────────────────────────────────────────────
    def add_family(self, family: Family) -> None:
        """Register a family. Raises :class:`PeopleError` if the id is already taken."""
        if family.family_id in self._families:
            raise PeopleError(f"family {family.family_id!r} already exists")
        self._families[family.family_id] = family

    def add_child(self, child: Child) -> None:
        """Register a child in an existing family.

        Raises:
            PeopleError: If the child id is taken or its family is not registered.
        """
        if child.child_id in self._children:
            raise PeopleError(f"child {child.child_id!r} already exists")
        if child.family_id not in self._families:
            raise PeopleError(f"unknown family {child.family_id!r} for child")
        self._children[child.child_id] = child

    def add_therapist(self, therapist: Therapist) -> None:
        """Register a therapist. Raises :class:`PeopleError` on a duplicate id."""
        if therapist.principal_id in self._therapists:
            raise PeopleError(f"therapist {therapist.principal_id!r} already exists")
        self._therapists[therapist.principal_id] = therapist

    # ── lookups ──────────────────────────────────────────────────────────────────
    def get_family(self, family_id: str) -> Family:
        """Return a registered family or raise :class:`PeopleError`."""
        try:
            return self._families[family_id]
        except KeyError:
            raise PeopleError(f"unknown family {family_id!r}") from None

    def get_child(self, child_id: str) -> Child:
        """Return a registered child or raise :class:`PeopleError`."""
        try:
            return self._children[child_id]
        except KeyError:
            raise PeopleError(f"unknown child {child_id!r}") from None

    # ── assignment ───────────────────────────────────────────────────────────────
    def assign(self, child_id: str, principal_id: str, role: Role) -> None:
        """Assign a therapist/reviewer to a child (child-scoped grant, ADR-005 D3).

        Args:
            child_id: The child to assign to (must be registered).
            principal_id: The therapist/reviewer principal.
            role: An assignable role (``THERAPIST`` / ``REVIEWER``).

        Raises:
            PeopleError: If the child is unknown, the role is not assignable, a
                ``THERAPIST`` is not a registered therapist, or the principal is a
                member of the child's own family (a role conflict).
        """
        child = self.get_child(child_id)
        if not role.is_assignable:
            raise PeopleError("family_owner is granted by family membership, not assignment")
        family = self._families[child.family_id]
        if principal_id in family.member_ids:
            raise PeopleError("a family member cannot be assigned as therapist/reviewer")
        if role is Role.THERAPIST and principal_id not in self._therapists:
            raise PeopleError(f"unknown therapist {principal_id!r}")
        self._assignments.setdefault(child_id, {})[principal_id] = role

    # ── consent (the lawful basis) ───────────────────────────────────────────────
    def record_consent(self, consent: ParentalConsent) -> None:
        """Record a parent's consent for a child.

        Raises:
            PeopleError: If the child is unknown, or the consenting principal is not a
                member of the child's family (only a parent may consent for the child).
        """
        child = self.get_child(consent.child_id)
        family = self._families[child.family_id]
        if consent.consenting_parent_id not in family.member_ids:
            raise PeopleError("only a family member may consent for the child")
        self._consents.setdefault(consent.child_id, []).append(consent)

    def has_consent(self, child_id: str) -> bool:
        """Whether any parental consent is on record for the child."""
        return bool(self._consents.get(child_id))

    # ── grant resolution ─────────────────────────────────────────────────────────
    def child_grants(self, child_id: str) -> ChildGrants:
        """Resolve the child-scoped grants a story/program inherits (ADR-005 D3).

        Args:
            child_id: The child whose grants to build (must be registered).

        Returns:
            A :class:`ChildGrants`: the child's family members as owners, plus any
            therapist/reviewer assigned to the child.

        Raises:
            PeopleError: If the child is unknown.
        """
        child = self.get_child(child_id)
        family = self._families[child.family_id]
        return child_grants(child, family, assignments=self._assignments.get(child_id, {}))
