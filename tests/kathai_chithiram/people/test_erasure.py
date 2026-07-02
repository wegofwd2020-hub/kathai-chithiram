"""Cascade-erasure tests (ADR-005; RETENTION_ERASURE_DESIGN §8 / DPIA A6.3)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from kathai_chithiram.access import GuardedStore, Principal, Role
from kathai_chithiram.errors import PeopleError
from kathai_chithiram.people import (
    AgeBand,
    Child,
    Family,
    ParentalConsent,
    PeopleRegistry,
    Therapist,
    erase_child,
    erase_family,
)
from kathai_chithiram.storage import StoryArtifactStore
from kathai_chithiram.storage.deletion import BackupPurgeLog

_AT = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _registry() -> PeopleRegistry:
    reg = PeopleRegistry()
    reg.add_family(Family(family_id="fam", owner_id="mum", member_ids=frozenset({"mum"})))
    reg.add_child(Child(child_id="kid1", family_id="fam", age_band=AgeBand.AGE_6_8))
    reg.add_child(Child(child_id="kid2", family_id="fam", age_band=AgeBand.AGE_3_5))
    reg.add_therapist(Therapist(principal_id="ot"))
    reg.assign("kid1", "ot", Role.THERAPIST)
    for kid in ("kid1", "kid2"):
        reg.record_consent(ParentalConsent(
            consenting_parent_id="mum", child_id=kid, policy_version="v1", granted_at=_AT,
        ))
    return reg


def _seed_stories(store: StoryArtifactStore, reg: PeopleRegistry) -> None:
    mum = GuardedStore(store, Principal("mum"), registry=reg)
    mum.create_story_for_child("s1a", child_id="kid1", created_at=_AT, story_text="a")
    mum.create_story_for_child("s1b", child_id="kid1", created_at=_AT, story_text="b")
    mum.create_story_for_child("s2", child_id="kid2", created_at=_AT, story_text="c")


def test_erase_family_destroys_every_child_and_story(tmp_path: Path) -> None:
    reg = _registry()
    store = StoryArtifactStore(tmp_path / "store")
    _seed_stories(store, reg)
    log = BackupPurgeLog(tmp_path / "purge.jsonl")

    receipt = erase_family(reg, store, "fam", purge_log=log)

    # Every story is hard-deleted and nothing remains in the store.
    assert set(receipt.story_ids) == {"s1a", "s1b", "s2"}
    assert list(store.iter_story_ids()) == []
    # The family, children, consents, and assignments are all gone from the registry.
    with pytest.raises(PeopleError):
        reg.get_family("fam")
    for kid in ("kid1", "kid2"):
        with pytest.raises(PeopleError):
            reg.get_child(kid)
        assert reg.has_consent(kid) is False


def test_erase_child_leaves_siblings_intact(tmp_path: Path) -> None:
    reg = _registry()
    store = StoryArtifactStore(tmp_path / "store")
    _seed_stories(store, reg)
    log = BackupPurgeLog(tmp_path / "purge.jsonl")

    receipt = erase_child(reg, store, "kid1", purge_log=log)

    assert set(receipt.story_ids) == {"s1a", "s1b"}
    assert list(store.iter_story_ids()) == ["s2"]  # the sibling's story survives
    with pytest.raises(PeopleError):
        reg.get_child("kid1")
    reg.get_child("kid2")  # still present


def test_erase_unknown_child_or_family_fails_closed(tmp_path: Path) -> None:
    reg = _registry()
    store = StoryArtifactStore(tmp_path / "store")
    log = BackupPurgeLog(tmp_path / "purge.jsonl")
    with pytest.raises(PeopleError):
        erase_child(reg, store, "ghost", purge_log=log)
    with pytest.raises(PeopleError):
        erase_family(reg, store, "ghost", purge_log=log)


def test_unassign_therapist_leaves_family_content(tmp_path: Path) -> None:
    reg = _registry()
    reg.unassign_therapist("ot")
    # The therapist no longer has a role on the child, but the child + family remain.
    assert reg.child_grants("kid1").role_of(Principal("ot")) is None
    reg.get_child("kid1")
    with pytest.raises(PeopleError):
        reg.unassign_therapist("ot")  # already gone
