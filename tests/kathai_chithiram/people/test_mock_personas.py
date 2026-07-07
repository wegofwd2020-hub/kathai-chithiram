"""Tests for the synthetic test-persona harness."""

from __future__ import annotations

import json
import re
from pathlib import Path

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


def test_resolve_handles_defaults_to_placeholders(tmp_path):
    # Point at a non-existent file so the real personas.local.json can't interfere.
    handles = mp.resolve_handles(tmp_path / "absent.json")
    assert handles == {
        "parent": "parent@example.test",
        "child": "child@example.test",
        "therapist": "therapist@example.test",
    }


def test_resolve_handles_applies_local_override(tmp_path):
    local = tmp_path / "personas.local.json"
    local.write_text(
        json.dumps(
            {
                "parent": "me+parent@gmail.test",
                "therapist": "me+ot@gmail.test",
                "bogus": "ignored@gmail.test",
            }
        )
    )
    handles = mp.resolve_handles(local)
    assert handles["parent"] == "me+parent@gmail.test"
    assert handles["therapist"] == "me+ot@gmail.test"
    # Unspecified key keeps its placeholder; unknown key is dropped.
    assert handles["child"] == "child@example.test"
    assert "bogus" not in handles


def test_committed_module_contains_no_real_email():
    source = Path(mp.__file__).read_text()
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", source)
    assert emails, "expected the placeholder handles to be present"
    for email in emails:
        assert email.endswith("@example.test"), f"non-placeholder email committed: {email}"


def test_resolve_handles_rejects_malformed_and_non_object_json(tmp_path):
    """Test that resolve_handles raises ValueError for invalid JSON or non-dict JSON."""
    import pytest
    bad = tmp_path / "personas.local.json"

    # Test malformed JSON
    bad.write_text("{ not json")
    with pytest.raises(ValueError):
        mp.resolve_handles(bad)

    # Test non-dict JSON (array instead)
    bad.write_text("[]")
    with pytest.raises(ValueError):
        mp.resolve_handles(bad)


def test_committed_example_json_contains_no_real_email():
    """Test that the committed example JSON file contains only placeholder emails."""
    example = Path(mp.__file__).parent / "personas.local.example.json"
    text = example.read_text()
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    assert emails, "expected placeholder handles in the example file"
    for email in emails:
        assert email.endswith("@example.test"), f"non-placeholder email committed: {email}"
