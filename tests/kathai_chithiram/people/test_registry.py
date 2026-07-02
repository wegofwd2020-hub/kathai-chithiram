"""Tests for the PeopleRegistry domain service (ADR-005 parts b/c)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kathai_chithiram.access import AccessPolicy, Action, Principal, Role
from kathai_chithiram.errors import PeopleError
from kathai_chithiram.people import (
    AgeBand,
    Child,
    Family,
    ParentalConsent,
    PeopleRegistry,
    Therapist,
)


def _seed() -> PeopleRegistry:
    reg = PeopleRegistry()
    reg.add_family(Family(family_id="fam", owner_id="mum", member_ids=frozenset({"mum", "dad"})))
    reg.add_child(Child(child_id="kid", family_id="fam", age_band=AgeBand.AGE_6_8))
    reg.add_therapist(Therapist(principal_id="ot"))
    return reg


def test_child_grants_resolve_family_and_assignment():
    reg = _seed()
    reg.assign("kid", "ot", Role.THERAPIST)
    grants = reg.child_grants("kid")
    policy = AccessPolicy()
    assert policy.is_allowed(Principal("dad"), grants, Action.WRITE_CONTENT)  # a parent owns
    assert policy.is_allowed(Principal("ot"), grants, Action.READ_FEEDBACK)  # the therapist
    assert grants.role_of(Principal("stranger")) is None


def test_add_child_needs_a_known_family():
    reg = PeopleRegistry()
    with pytest.raises(PeopleError, match="unknown family"):
        reg.add_child(Child(child_id="kid", family_id="ghost", age_band=AgeBand.AGE_3_5))


def test_duplicate_registration_is_rejected():
    reg = _seed()
    with pytest.raises(PeopleError, match="already exists"):
        reg.add_child(Child(child_id="kid", family_id="fam", age_band=AgeBand.AGE_9_11))


def test_unknown_lookups_fail_closed():
    reg = PeopleRegistry()
    with pytest.raises(PeopleError, match="unknown child"):
        reg.get_child("nobody")
    with pytest.raises(PeopleError, match="unknown child"):
        reg.child_grants("nobody")


def test_assigning_an_unregistered_therapist_is_rejected():
    reg = _seed()
    with pytest.raises(PeopleError, match="unknown therapist"):
        reg.assign("kid", "not-registered", Role.THERAPIST)


def test_a_family_member_cannot_be_assigned():
    reg = _seed()
    with pytest.raises(PeopleError, match="family member cannot be assigned"):
        reg.assign("kid", "dad", Role.THERAPIST)


def test_only_a_family_member_may_consent():
    reg = _seed()
    ok = ParentalConsent(
        consenting_parent_id="mum", child_id="kid", policy_version="v1",
        granted_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )
    reg.record_consent(ok)
    assert reg.has_consent("kid")

    stranger = ParentalConsent(
        consenting_parent_id="outsider", child_id="kid", policy_version="v1",
        granted_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )
    with pytest.raises(PeopleError, match="only a family member may consent"):
        reg.record_consent(stranger)


def test_has_consent_is_false_until_recorded():
    reg = _seed()
    assert reg.has_consent("kid") is False


# ── persistence ───────────────────────────────────────────────────────────────────
def test_save_load_roundtrip(tmp_path):
    reg = _seed()
    reg.assign("kid", "ot", Role.THERAPIST)
    reg.record_consent(ParentalConsent(
        consenting_parent_id="mum", child_id="kid", policy_version="v1",
        granted_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
    ))
    path = tmp_path / "people.json"
    reg.save(path)

    loaded = PeopleRegistry.load(path)
    assert loaded.child_grants("kid").role_of(Principal("ot")) is Role.THERAPIST
    assert loaded.child_grants("kid").role_of(Principal("mum")) is Role.FAMILY_OWNER
    assert loaded.has_consent("kid")


def test_load_missing_file_is_an_empty_registry(tmp_path):
    reg = PeopleRegistry.load(tmp_path / "absent.json")
    with pytest.raises(PeopleError):
        reg.get_child("anyone")


def test_load_bad_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(PeopleError, match="not valid JSON"):
        PeopleRegistry.load(path)
