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

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from kathai_chithiram.access.policy import ChildGrants
from kathai_chithiram.access.principal import Role
from kathai_chithiram.errors import PeopleError
from kathai_chithiram.people.grants import child_grants
from kathai_chithiram.people.models import AgeBand, Child, Family, ParentalConsent, Therapist

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

    # ── removal (erasure cascade; RETENTION_ERASURE_DESIGN §4) ─────────────────────
    def children_of(self, family_id: str) -> list[str]:
        """Return the ids of every child in a family (empty if none/unknown)."""
        return [c.child_id for c in self._children.values() if c.family_id == family_id]

    def remove_child(self, child_id: str) -> None:
        """Remove a child and its assignments + consents (its DOB band goes with it).

        Raises:
            PeopleError: If the child is unknown.
        """
        if child_id not in self._children:
            raise PeopleError(f"unknown child {child_id!r}")
        del self._children[child_id]
        self._assignments.pop(child_id, None)
        self._consents.pop(child_id, None)

    def remove_family(self, family_id: str) -> None:
        """Remove a family record. Its children must already be removed (no orphans).

        Raises:
            PeopleError: If the family is unknown or still has children.
        """
        if family_id not in self._families:
            raise PeopleError(f"unknown family {family_id!r}")
        if self.children_of(family_id):
            raise PeopleError("family still has children; erase them first")
        del self._families[family_id]

    def unassign_therapist(self, principal_id: str) -> None:
        """Unassign a therapist from every child and remove their account.

        Family content is untouched (a therapist never owned it), matching the
        RETENTION_ERASURE_DESIGN §4 therapist rule.

        Raises:
            PeopleError: If the therapist is unknown.
        """
        if principal_id not in self._therapists:
            raise PeopleError(f"unknown therapist {principal_id!r}")
        for grants in self._assignments.values():
            grants.pop(principal_id, None)
        del self._therapists[principal_id]

    # ── persistence (interim plaintext; encryption + key tree = the erasure slice) ──
    def to_dict(self) -> dict[str, Any]:
        """Serialize the registry to a JSON-safe dict of opaque ids + bands + consent.

        Contains no name and no date of birth — only opaque ids, age bands, roles, and
        consent timestamps (DPIA addendum A8). Durable encryption and the per-child key
        tree follow ``docs/RETENTION_ERASURE_DESIGN.md``.
        """
        return {
            "families": [
                {"family_id": f.family_id, "owner_id": f.owner_id,
                 "member_ids": sorted(f.member_ids)}
                for f in self._families.values()
            ],
            "children": [
                {"child_id": c.child_id, "family_id": c.family_id, "age_band": c.age_band.value}
                for c in self._children.values()
            ],
            "therapists": [t.principal_id for t in self._therapists.values()],
            "assignments": {
                child_id: {pid: role.value for pid, role in grants.items()}
                for child_id, grants in self._assignments.items()
            },
            "consents": {
                child_id: [
                    {"consenting_parent_id": c.consenting_parent_id,
                     "policy_version": c.policy_version, "granted_at": c.granted_at.isoformat()}
                    for c in consents
                ]
                for child_id, consents in self._consents.items()
            },
        }

    def save(self, path: Path) -> None:
        """Write the registry to ``path`` as JSON (creating parent dirs)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> PeopleRegistry:
        """Load a registry from ``path``; return an empty one if the file is absent.

        Raises:
            PeopleError: If the file exists but is not valid registry JSON.
        """
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PeopleError(f"registry file is not valid JSON: {exc}") from exc
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PeopleRegistry:
        """Rebuild a registry from :meth:`to_dict` output, revalidating every record.

        Raises:
            PeopleError: If a record is malformed (each is re-run through its model's
                validation and the registry's own invariants).
        """
        reg = cls()
        try:
            for f in data.get("families", []):
                reg.add_family(Family(
                    family_id=f["family_id"], owner_id=f["owner_id"],
                    member_ids=frozenset(f["member_ids"]),
                ))
            for c in data.get("children", []):
                reg.add_child(Child(
                    child_id=c["child_id"], family_id=c["family_id"],
                    age_band=AgeBand(c["age_band"]),
                ))
            for pid in data.get("therapists", []):
                reg.add_therapist(Therapist(principal_id=pid))
            for child_id, grants in data.get("assignments", {}).items():
                for pid, role in grants.items():
                    reg.assign(child_id, pid, Role(role))
            for child_id, consents in data.get("consents", {}).items():
                for c in consents:
                    reg.record_consent(ParentalConsent(
                        consenting_parent_id=c["consenting_parent_id"], child_id=child_id,
                        policy_version=c["policy_version"],
                        granted_at=datetime.fromisoformat(c["granted_at"]),
                    ))
        except (KeyError, ValueError) as exc:
            raise PeopleError(f"malformed registry record: {exc}") from exc
        return reg
