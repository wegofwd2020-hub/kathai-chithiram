"""The people / family domain model (ADR-005 Decision 2, parts b/c).

The multi-user platform introduces a real identity domain — families, parents,
children, therapists — on top of the ADR-004 access seam. Two privacy rulings shape
these types (DPIA addendum A8):

- **No child date of birth is stored.** Age-norming needs only a coarse **age band**;
  a DOB, if presented at intake, is turned into an :class:`AgeBand` and discarded. The
  model has no field that can hold a date of birth (data minimization, Art. 5(1)(c)).
- **No real names.** A child's real name is a render-time substitution only
  (CLAUDE.md); every identity here is an **opaque id**, never a name — exactly as
  :class:`~kathai_chithiram.access.principal.Principal` already requires.

These are pure value types: relationships (a therapist assigned to a child) live in the
ADR-004 grant layer, not here, so identity carries no authority on its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

__all__ = ["AgeBand", "Child", "Family", "ParentalConsent", "Parent", "Therapist"]

#: Opaque-id charset — matches :class:`Principal` and the store's id rules, so no name
#: or free text can smuggle into an identity.
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

#: Upper bound (exclusive) of childhood for the age-band model, in years.
_ADULTHOOD_YEARS = 18


def _require_id(value: str, field: str) -> None:
    """Raise ``ValueError`` unless ``value`` is a non-empty opaque id.

    Args:
        value: The candidate id.
        field: The field name, for the error message.

    Raises:
        ValueError: If ``value`` is empty or contains unsafe characters.
    """
    if not _ID_PATTERN.match(value):
        raise ValueError(f"{field} must be a non-empty opaque id (^[A-Za-z0-9_-]+$)")


class AgeBand(Enum):
    """A coarse age band for a child — the *only* age data the platform stores.

    Full date of birth is never persisted (DPIA addendum A8): age-norming needs only
    the band, so a DOB is converted with :meth:`from_dob` at intake and discarded. The
    bands span childhood (0–17); an adult date of birth is rejected, not stored.

    Members:
        AGE_0_2, AGE_3_5, AGE_6_8, AGE_9_11, AGE_12_14, AGE_15_17: three-year bands
            covering ages 0 through 17 inclusive.
    """

    AGE_0_2 = "0-2"
    AGE_3_5 = "3-5"
    AGE_6_8 = "6-8"
    AGE_9_11 = "9-11"
    AGE_12_14 = "12-14"
    AGE_15_17 = "15-17"

    @classmethod
    def from_dob(cls, dob: date, *, today: date) -> AgeBand:
        """Return the age band for a date of birth, then the caller discards the DOB.

        The DOB is an input only — it is used to compute the band and must not be
        stored (that is the whole point of the band). ``today`` is passed explicitly
        (never read from the clock here) so the result is deterministic and testable.

        Args:
            dob: The child's date of birth (used transiently, never persisted).
            today: The reference date to compute age against.

        Returns:
            The :class:`AgeBand` the child falls into.

        Raises:
            ValueError: If ``dob`` is in the future, or the person is 18 or older
                (the band model is for children only).
        """
        years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if years < 0:
            raise ValueError("date of birth is in the future")
        if years >= _ADULTHOOD_YEARS:
            raise ValueError("age band applies to children only (under 18)")
        return list(cls)[years // 3]


@dataclass(frozen=True)
class Family:
    """A family — the account boundary grouping a child's parent(s) (ADR-005 D2).

    Args:
        family_id: Opaque id for the family.
        owner_id: Opaque principal id of the owning parent; must be one of
            ``member_ids``.
        member_ids: Opaque principal ids of the family's parents (at least one,
            including the owner).

    Raises:
        ValueError: If any id is empty/unsafe, ``member_ids`` is empty, or ``owner_id``
            is not among the members.
    """

    family_id: str
    owner_id: str
    member_ids: frozenset[str]

    def __post_init__(self) -> None:
        _require_id(self.family_id, "family_id")
        _require_id(self.owner_id, "owner_id")
        if not self.member_ids:
            raise ValueError("a family must have at least one parent member")
        for member in self.member_ids:
            _require_id(member, "member_ids entry")
        if self.owner_id not in self.member_ids:
            raise ValueError("owner_id must be one of the family's member_ids")


@dataclass(frozen=True)
class Parent:
    """A parent — a member of exactly one family (ADR-005 D2).

    Args:
        principal_id: The parent's opaque principal id.
        family_id: The family they belong to.

    Raises:
        ValueError: If either id is empty or unsafe.
    """

    principal_id: str
    family_id: str

    def __post_init__(self) -> None:
        _require_id(self.principal_id, "principal_id")
        _require_id(self.family_id, "family_id")


@dataclass(frozen=True)
class Child:
    """A child — a data subject belonging to exactly one family (ADR-005 D2/D4).

    Carries no name (render-time only) and no date of birth — only an
    :class:`AgeBand` (DPIA addendum A8). The grant unit for a child's stories and
    program is this ``child_id`` (ADR-005 D3).

    Args:
        child_id: The child's opaque id — the child-scoped grant subject.
        family_id: The family the child belongs to.
        age_band: The child's coarse age band (no DOB is stored).

    Raises:
        ValueError: If either id is empty/unsafe, or ``age_band`` is not an
            :class:`AgeBand`.
    """

    child_id: str
    family_id: str
    age_band: AgeBand

    def __post_init__(self) -> None:
        _require_id(self.child_id, "child_id")
        _require_id(self.family_id, "family_id")
        if not isinstance(self.age_band, AgeBand):
            raise ValueError("age_band must be an AgeBand (no date of birth is stored)")


@dataclass(frozen=True)
class Therapist:
    """A therapist — an independent principal, assigned to children via grants.

    A therapist is not a family member; the child/program assignment lives in the
    ADR-004 grant layer, not on this type (ADR-005 D2).

    Args:
        principal_id: The therapist's opaque principal id.

    Raises:
        ValueError: If ``principal_id`` is empty or unsafe.
    """

    principal_id: str

    def __post_init__(self) -> None:
        _require_id(self.principal_id, "principal_id")


@dataclass(frozen=True)
class ParentalConsent:
    """A parent's consent for a child's data — the lawful basis (DPIA addendum A8).

    The child's data is processed on **parental/guardian consent** (Art. 6(1)(a) +
    9(2)(a)), captured per child and withdrawable per child. This records *which*
    parent consented, for *which* child, under *which* versioned policy, and *when*
    (extending the KC-8 versioned-consent mechanism). No free text, no identifiers.

    Args:
        consenting_parent_id: Opaque principal id of the consenting parent.
        child_id: The child the consent covers.
        policy_version: The privacy-notice/consent version consented to (non-empty).
        granted_at: When consent was granted (timezone-aware).

    Raises:
        ValueError: If an id is empty/unsafe, ``policy_version`` is blank, or
            ``granted_at`` is naive (no timezone).
    """

    consenting_parent_id: str
    child_id: str
    policy_version: str
    granted_at: datetime

    def __post_init__(self) -> None:
        _require_id(self.consenting_parent_id, "consenting_parent_id")
        _require_id(self.child_id, "child_id")
        if not self.policy_version.strip():
            raise ValueError("policy_version must be non-empty")
        if self.granted_at.tzinfo is None:
            raise ValueError("granted_at must be timezone-aware")
