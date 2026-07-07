"""erase_family crypto-shreds the per-family key first; content fails closed (§3)."""

from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest

from kathai_chithiram.errors import DecryptionError, PeopleError
from kathai_chithiram.people.erasure import erase_family
from kathai_chithiram.people.models import (
    AgeBand,
    Child,
    Family,
    ParentalConsent,
)
from kathai_chithiram.people.registry import PeopleRegistry
from kathai_chithiram.storage.crypto import AesGcmCipher, generate_key
from kathai_chithiram.storage.deletion import BackupPurgeLog
from kathai_chithiram.storage.store import StoryArtifactStore

_NOW = datetime(2026, 7, 7, tzinfo=timezone.utc)
_SCRIPT = {"schema_version": "1.0", "title": "Calm night", "scenes": []}


def _master() -> AesGcmCipher:
    return AesGcmCipher(base64.urlsafe_b64decode(generate_key()))


def _registry_one_family_two_children():
    reg = PeopleRegistry()
    reg.add_family(Family(family_id="fam-1", owner_id="par-1", member_ids=frozenset({"par-1"})))
    for cid in ("kid-a", "kid-b"):
        reg.add_child(Child(child_id=cid, family_id="fam-1", age_band=AgeBand.AGE_6_8))
        reg.record_consent(ParentalConsent(
            consenting_parent_id="par-1", child_id=cid,
            policy_version="v0", granted_at=_NOW,
        ))
    return reg


def test_erase_family_shreds_family_key_first_and_fails_closed(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_master())
    reg = _registry_one_family_two_children()
    purge = BackupPurgeLog(tmp_path / "purge.log")

    for sid, cid in (("a1", "kid-a"), ("b1", "kid-b")):
        store.create_story(sid, created_at=_NOW, story_text="secret",
                           child_id=cid, family_id="fam-1")
        store.write_scene_script(sid, _SCRIPT)
        store.write_grants(sid, {"child_id": cid})

    # (pre) capture a real backup fragment of kid-a: its wrapped child key + family marker.
    kid_a_dir = store._child_key_path("kid-a").parent
    wrapped_child_key = (kid_a_dir / "_child_key.wrapped").read_bytes()

    receipt = erase_family(reg, store, "fam-1", purge_log=purge)

    # (a) family key destroyed
    assert not store._family_key_path("fam-1").is_file()
    # (b) both stories gone; registry has no family
    assert not store.exists("a1") and not store.exists("b1")
    with pytest.raises(PeopleError):
        reg.get_family("fam-1")
    # (c) crypto-shred proof: restore kid-a's child-key fragment; unwrapping it needs the
    #     family key, which is destroyed → fails closed.
    kid_a_dir.mkdir(parents=True, exist_ok=True)
    (kid_a_dir / "_child_key.wrapped").write_bytes(wrapped_child_key)
    (kid_a_dir / "_family.parent").write_text("fam-1", encoding="utf-8")
    with pytest.raises(DecryptionError):
        store._child_cipher("kid-a")
    # (d) receipt (→ backup-purge log) carries both children + story ids
    assert set(receipt.child_ids) == {"kid-a", "kid-b"}
    assert set(receipt.story_ids) == {"a1", "b1"}
