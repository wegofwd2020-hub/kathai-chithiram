"""Tests for programs (ADR-005 D5): model, registry integration, erasure cascade."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kathai_chithiram.access import Role
from kathai_chithiram.errors import PeopleError
from kathai_chithiram.people import (
    AgeBand,
    Child,
    Family,
    PeopleRegistry,
    Program,
    Therapist,
)

_AT = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _seed() -> PeopleRegistry:
    reg = PeopleRegistry()
    reg.add_family(Family(family_id="fam", owner_id="mum", member_ids=frozenset({"mum"})))
    reg.add_child(Child(child_id="kid", family_id="fam", age_band=AgeBand.AGE_6_8))
    reg.add_therapist(Therapist(principal_id="ot"))
    reg.assign("kid", "ot", Role.THERAPIST)
    return reg


def _program() -> Program:
    return Program(program_id="prog", child_id="kid", therapist_id="ot",
                   goal_ids=frozenset({"goal-brush"}), created_at=_AT)


# ── model ─────────────────────────────────────────────────────────────────────────
def test_program_needs_a_goal_and_tz_aware_time():
    with pytest.raises(ValueError, match="at least one goal"):
        Program(program_id="p", child_id="c", therapist_id="t",
                goal_ids=frozenset(), created_at=_AT)
    with pytest.raises(ValueError, match="timezone-aware"):
        Program(program_id="p", child_id="c", therapist_id="t",
                goal_ids=frozenset({"g"}), created_at=datetime(2026, 6, 1))


# ── registry integration ──────────────────────────────────────────────────────────
def test_add_program_requires_an_assigned_therapist():
    reg = _seed()
    reg.add_program(_program())
    assert reg.programs_for_child("kid") == ["prog"]
    assert reg.get_program("prog").therapist_id == "ot"


def test_program_therapist_must_be_assigned_to_the_child():
    reg = _seed()
    reg.add_therapist(Therapist(principal_id="ot2"))  # registered but not assigned to kid
    with pytest.raises(PeopleError, match="assigned to the child"):
        reg.add_program(Program(program_id="p2", child_id="kid", therapist_id="ot2",
                                goal_ids=frozenset({"g"}), created_at=_AT))


def test_program_needs_a_known_child():
    reg = _seed()
    with pytest.raises(PeopleError, match="unknown child"):
        reg.add_program(Program(program_id="p", child_id="ghost", therapist_id="ot",
                                goal_ids=frozenset({"g"}), created_at=_AT))


# ── erasure + persistence ──────────────────────────────────────────────────────────
def test_removing_a_child_removes_its_programs():
    reg = _seed()
    reg.add_program(_program())
    reg.remove_child("kid")
    with pytest.raises(PeopleError, match="unknown program"):
        reg.get_program("prog")


def test_programs_survive_a_save_load_roundtrip(tmp_path):
    reg = _seed()
    reg.add_program(_program())
    path = tmp_path / "people.json"
    reg.save(path)
    loaded = PeopleRegistry.load(path)
    assert loaded.get_program("prog").goal_ids == frozenset({"goal-brush"})
