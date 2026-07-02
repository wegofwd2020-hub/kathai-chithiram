"""Tests for deriving a child's grants from the family model (ADR-005 D3)."""

from __future__ import annotations

import pytest

from kathai_chithiram.access import AccessPolicy, Action, Principal, Role
from kathai_chithiram.people import AgeBand, Child, Family, child_grants


def _family() -> Family:
    return Family(family_id="fam-1", owner_id="mum-1", member_ids=frozenset({"mum-1", "dad-1"}))


def _child() -> Child:
    return Child(child_id="kid-1", family_id="fam-1", age_band=AgeBand.AGE_6_8)


def test_builds_child_grants_from_family_and_assignments():
    grants = child_grants(_child(), _family(), assignments={"ot-1": Role.THERAPIST})
    assert grants.family_member_ids == frozenset({"mum-1", "dad-1"})
    policy = AccessPolicy()
    assert policy.is_allowed(Principal("dad-1"), grants, Action.WRITE_CONTENT)  # a parent
    assert policy.is_allowed(Principal("ot-1"), grants, Action.READ_FEEDBACK)  # the therapist
    assert grants.role_of(Principal("stranger")) is None


def test_rejects_a_child_from_a_different_family():
    other = Family(family_id="fam-2", owner_id="x-1", member_ids=frozenset({"x-1"}))
    with pytest.raises(ValueError, match="does not belong to this family"):
        child_grants(_child(), other)


def test_assignments_default_to_none():
    grants = child_grants(_child(), _family())
    assert dict(grants.assignments) == {}
