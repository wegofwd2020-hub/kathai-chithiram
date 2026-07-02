"""People / family domain for the multi-user platform (ADR-005 parts b/c).

Value types for families, parents, children, and therapists, plus per-child parental
consent. Minimization is built in: children carry an :class:`AgeBand`, never a date of
birth, and every identity is an opaque id, never a name (DPIA addendum A8).
"""

from __future__ import annotations

from kathai_chithiram.people.grants import child_grants
from kathai_chithiram.people.models import (
    AgeBand,
    Child,
    Family,
    Parent,
    ParentalConsent,
    Therapist,
)

__all__ = [
    "AgeBand",
    "Child",
    "Family",
    "ParentalConsent",
    "Parent",
    "Therapist",
    "child_grants",
]
