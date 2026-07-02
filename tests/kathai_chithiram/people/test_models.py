"""Tests for the people / family domain model (ADR-005 D2, DPIA addendum A8)."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timezone

import pytest

from kathai_chithiram.people import (
    AgeBand,
    Child,
    Family,
    Parent,
    ParentalConsent,
    Therapist,
)

_TODAY = date(2026, 7, 2)


# ── AgeBand — the DOB never survives ──────────────────────────────────────────────
@pytest.mark.parametrize(
    "dob,expected",
    [
        (date(2026, 1, 1), AgeBand.AGE_0_2),   # age 0
        (date(2020, 1, 1), AgeBand.AGE_6_8),   # age 6
        (date(2009, 1, 1), AgeBand.AGE_15_17),  # age 17 (upper boundary)
    ],
)
def test_from_dob_maps_to_the_right_band(dob, expected):
    assert AgeBand.from_dob(dob, today=_TODAY) is expected


def test_from_dob_rejects_an_adult():
    # 18+ is not a child; the band model refuses it rather than storing an adult DOB.
    with pytest.raises(ValueError, match="children only"):
        AgeBand.from_dob(date(2008, 1, 1), today=_TODAY)


def test_from_dob_rejects_a_future_date():
    with pytest.raises(ValueError, match="future"):
        AgeBand.from_dob(date(2027, 1, 1), today=_TODAY)


def test_a_persona_labelled_child_but_born_1997_is_rejected():
    # Guards the real-data slip: a "child" DOB of 1997 is an adult and must not pass.
    with pytest.raises(ValueError, match="children only"):
        AgeBand.from_dob(date(1997, 9, 3), today=_TODAY)


# ── minimization guarantees ───────────────────────────────────────────────────────
def test_child_stores_a_band_not_a_date_and_no_name():
    fields = {f.name for f in dataclasses.fields(Child)}
    assert fields == {"child_id", "family_id", "age_band"}  # no dob, no name
    child = Child(child_id="c1", family_id="f1", age_band=AgeBand.AGE_6_8)
    assert isinstance(child.age_band, AgeBand)


def test_child_rejects_a_non_ageband_age():
    with pytest.raises(ValueError, match="AgeBand"):
        Child(child_id="c1", family_id="f1", age_band="6-8")  # type: ignore[arg-type]


# ── Family ────────────────────────────────────────────────────────────────────────
def test_family_valid():
    fam = Family(family_id="f1", owner_id="p1", member_ids=frozenset({"p1", "p2"}))
    assert fam.owner_id in fam.member_ids


def test_family_owner_must_be_a_member():
    with pytest.raises(ValueError, match="owner_id must be one of"):
        Family(family_id="f1", owner_id="p9", member_ids=frozenset({"p1", "p2"}))


def test_family_needs_a_member():
    with pytest.raises(ValueError, match="at least one parent"):
        Family(family_id="f1", owner_id="p1", member_ids=frozenset())


def test_ids_reject_unsafe_characters():
    with pytest.raises(ValueError, match="opaque id"):
        Parent(principal_id="has space", family_id="f1")
    with pytest.raises(ValueError, match="opaque id"):
        Therapist(principal_id="")


# ── ParentalConsent — the lawful basis ────────────────────────────────────────────
def test_parental_consent_valid():
    consent = ParentalConsent(
        consenting_parent_id="p1", child_id="c1", policy_version="2026-07-02",
        granted_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )
    assert consent.child_id == "c1"


def test_parental_consent_requires_tz_aware_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        ParentalConsent(
            consenting_parent_id="p1", child_id="c1", policy_version="v1",
            granted_at=datetime(2026, 7, 2),  # naive
        )


def test_parental_consent_requires_a_version():
    with pytest.raises(ValueError, match="policy_version"):
        ParentalConsent(
            consenting_parent_id="p1", child_id="c1", policy_version="  ",
            granted_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
        )
