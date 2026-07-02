"""People / family domain for the multi-user platform (ADR-005 parts b/c).

Value types for families, parents, children, and therapists, plus per-child parental
consent. Minimization is built in: children carry an :class:`AgeBand`, never a date of
birth, and every identity is an opaque id, never a name (DPIA addendum A8).
"""

from __future__ import annotations

from kathai_chithiram.people.erasure import ErasureReceipt, erase_child, erase_family
from kathai_chithiram.people.grants import child_grants
from kathai_chithiram.people.models import (
    AgeBand,
    Child,
    Family,
    Parent,
    ParentalConsent,
    Program,
    Therapist,
)
from kathai_chithiram.people.registry import PeopleRegistry

__all__ = [
    "AgeBand",
    "Child",
    "ErasureReceipt",
    "Family",
    "ParentalConsent",
    "Parent",
    "PeopleRegistry",
    "Program",
    "Therapist",
    "child_grants",
    "erase_child",
    "erase_family",
]
