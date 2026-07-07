"""erase_child crypto-shreds the per-child key first; content fails closed (§3/§8)."""

from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest

from kathai_chithiram.errors import DecryptionError
from kathai_chithiram.people.erasure import erase_child
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


def _registry_with_two_children():
    reg = PeopleRegistry()
    reg.add_family(Family(family_id="fam-1", owner_id="par-1", member_ids=frozenset({"par-1"})))
    for cid in ("kid-a", "kid-b"):
        reg.add_child(Child(child_id=cid, family_id="fam-1", age_band=AgeBand.AGE_6_8))
        reg.record_consent(ParentalConsent(
            consenting_parent_id="par-1", child_id=cid,
            policy_version="v0", granted_at=_NOW,
        ))
    return reg


def test_erase_child_shreds_child_key_first_and_fails_closed(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_master())
    reg = _registry_with_two_children()
    purge = BackupPurgeLog(tmp_path / "purge.log")

    for sid, cid in (("a1", "kid-a"), ("b1", "kid-b")):
        store.create_story(sid, created_at=_NOW, story_text="secret", child_id=cid)
        store.write_scene_script(sid, _SCRIPT)
        store.write_grants(sid, {"child_id": cid})

    # (pre) capture a real backup fragment of kid-a's story: its wrapped per-story key.
    a_dir = store.story_dir("a1")
    wrapped_story_key = (a_dir / "_data_key.wrapped").read_bytes()

    receipt = erase_child(reg, store, "kid-a", purge_log=purge)

    # (a) child key destroyed; (b) kid-a gone, kid-b intact and readable
    assert not store._child_key_path("kid-a").is_file()
    assert not store.exists("a1")
    assert store.read_scene_script("b1") == _SCRIPT
    # (c) crypto-shred proof: restore the captured backup fragment (wrapped story key +
    #     parent marker); the per-child key needed to unwrap it is destroyed → fails closed.
    a_dir.mkdir(parents=True, exist_ok=True)
    (a_dir / "_data_key.wrapped").write_bytes(wrapped_story_key)
    (a_dir / "_data_key.parent").write_text("kid-a", encoding="utf-8")
    with pytest.raises(DecryptionError):
        # restored fragment: reads _data_key.parent → shredded child key → fails closed
        store._story_cipher(a_dir)
    # (d) receipt (→ backup-purge log) carries the child + story ids
    assert "a1" in receipt.story_ids and "kid-a" in receipt.child_ids
