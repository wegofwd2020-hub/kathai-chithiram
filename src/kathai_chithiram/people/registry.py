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
from kathai_chithiram.errors import DecryptionError, PeopleError
from kathai_chithiram.people.grants import child_grants
from kathai_chithiram.people.models import (
    AgeBand,
    Child,
    Family,
    ParentalConsent,
    Program,
    Therapist,
)
from kathai_chithiram.storage.crypto import StorageCipher

__all__ = ["PeopleRegistry"]

#: Safe artifact label for a registry decrypt failure (no key/content).
_REGISTRY_ARTIFACT = "people-registry"


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
        self._programs: dict[str, Program] = {}

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

    def family_id_of(self, child_id: str) -> str:
        """Return the child's family id (satisfies ``ChildGrantsSource`` structurally).

        Raises:
            PeopleError: If the child is unknown.
        """
        return self.get_child(child_id).family_id

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

    # ── programs (ADR-005 D5) ──────────────────────────────────────────────────────
    def add_program(self, program: Program) -> None:
        """Register a therapist's program for a child (child-scoped, ADR-005 D5).

        Raises:
            PeopleError: If the program id is taken, the child is unknown, or the
                owning therapist is not assigned to the child (only an assigned
                therapist may run a program for that child).
        """
        if program.program_id in self._programs:
            raise PeopleError(f"program {program.program_id!r} already exists")
        self.get_child(program.child_id)  # fail closed if unknown
        assigned = self._assignments.get(program.child_id, {}).get(program.therapist_id)
        if assigned is not Role.THERAPIST:
            raise PeopleError("program therapist must be assigned to the child")
        self._programs[program.program_id] = program

    def get_program(self, program_id: str) -> Program:
        """Return a registered program or raise :class:`PeopleError`."""
        try:
            return self._programs[program_id]
        except KeyError:
            raise PeopleError(f"unknown program {program_id!r}") from None

    def programs_for_child(self, child_id: str) -> list[str]:
        """Return the ids of every program for a child (empty if none)."""
        return [p.program_id for p in self._programs.values() if p.child_id == child_id]

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
        for program_id in self.programs_for_child(child_id):
            del self._programs[program_id]

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
            "programs": [
                {"program_id": p.program_id, "child_id": p.child_id,
                 "therapist_id": p.therapist_id, "goal_ids": sorted(p.goal_ids),
                 "created_at": p.created_at.isoformat()}
                for p in self._programs.values()
            ],
        }

    def save(self, path: Path, *, cipher: StorageCipher | None = None) -> None:
        """Write the registry to ``path`` (creating parent dirs).

        With ``cipher`` the JSON is encrypted at rest under the master (KC-5 parity);
        without it the file is plaintext (the documented non-production fallback),
        byte-compatible with earlier releases.

        Args:
            path: Destination file.
            cipher: Optional master cipher; when set the file is written encrypted.

        Raises:
            OSError: If the file cannot be written.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2, sort_keys=True).encode("utf-8")
        path.write_bytes(cipher.encrypt(payload) if cipher is not None else payload)

    @classmethod
    def load(cls, path: Path, *, cipher: StorageCipher | None = None) -> PeopleRegistry:
        """Load a registry from ``path``; return an empty one if the file is absent.

        With a ``cipher`` the file is expected encrypted (KC-5 parity): the bytes are
        decrypted first, and only if that fails are they treated as legacy plaintext
        JSON (automatic migration on the next :meth:`save`). Without a cipher the bytes
        must be plaintext JSON. Fails closed — an encrypted file cannot be read without
        the right key.

        Args:
            path: Source file.
            cipher: Optional master cipher; when set, decryption is attempted first.

        Raises:
            PeopleError: If the file exists but cannot be decrypted and is not valid
                registry JSON (fails closed on a missing/wrong key).
        """
        if not path.exists():
            return cls()
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise PeopleError(f"registry file could not be read: {exc}") from exc

        text: str | None = None
        if cipher is not None:
            try:
                text = cipher.decrypt(raw, artifact=_REGISTRY_ARTIFACT).decode("utf-8")
            except (DecryptionError, UnicodeDecodeError):
                text = None  # fall back to legacy plaintext (migration)
        if text is None:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise PeopleError(f"registry file is not valid JSON: {exc}") from exc

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PeopleError(f"registry file is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise PeopleError("registry file is not a valid registry object")
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
            for p in data.get("programs", []):
                reg.add_program(Program(
                    program_id=p["program_id"], child_id=p["child_id"],
                    therapist_id=p["therapist_id"], goal_ids=frozenset(p["goal_ids"]),
                    created_at=datetime.fromisoformat(p["created_at"]),
                ))
        except (KeyError, ValueError) as exc:
            raise PeopleError(f"malformed registry record: {exc}") from exc
        return reg
