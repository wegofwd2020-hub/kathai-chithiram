"""Tests for the synthetic test-persona harness."""

from __future__ import annotations

from tests.kathai_chithiram.people import mock_personas as mp

from kathai_chithiram.access.principal import Role
from kathai_chithiram.people.models import AgeBand, Family


def test_personas_have_stable_ids_and_placeholder_handles():
    assert mp.PARENT.subject_id == "parent-mock-001"
    assert mp.CHILD.subject_id == "child-mock-001"
    assert mp.THERAPIST.subject_id == "therapist-mock-001"
    for persona in (mp.PARENT, mp.CHILD, mp.THERAPIST):
        assert persona.login_handle.endswith("@example.test")


def test_mock_family_is_valid():
    family = mp.mock_family()
    assert isinstance(family, Family)
    assert family.owner_id == mp.PARENT.subject_id
    assert mp.PARENT.subject_id in family.member_ids


def test_mock_registry_wires_consent_and_therapist_grant():
    reg = mp.mock_registry()
    assert reg.has_consent(mp.CHILD.subject_id) is True
    grants = reg.child_grants(mp.CHILD.subject_id)
    assert grants.assignments.get(mp.THERAPIST.subject_id) == Role.THERAPIST
    assert mp.PARENT.subject_id in grants.family_member_ids


def test_child_persona_uses_an_age_band_not_a_dob():
    reg = mp.mock_registry()
    child = reg.get_child(mp.CHILD.subject_id)
    assert isinstance(child.age_band, AgeBand)
