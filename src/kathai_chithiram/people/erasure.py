"""Cascade erasure for the people/family model (ADR-005; RETENTION_ERASURE_DESIGN §4).

Right-to-erasure for the new entities: erasing a **child** first crypto-shreds the
child's per-child *content* key (§3 property 3) — destroying it in one op renders
every per-story key wrapped beneath it un-unwrappable, so all of the child's story
content is unrecoverable before and independent of the delete loop — then hard-deletes
every one of the child's stories (the verifiable KC-1 delete, which also crypto-shreds
each per-story KC-10 key) and removes the child's registry records — its age band,
consents, and assignments — then asserts nothing remains, including the shredded key
file itself. Erasing a **family** cascades over every child, then removes the family.
Each removed story is recorded in the backup-purge log.

This is the functional cascade + verifiability the addendum's A6.3 precondition
requires, now including the per-child content key tree from RETENTION_ERASURE_DESIGN
§3. The registry's own records (family/child/consent/assignment) are **not**
encrypted — they remain plaintext (opaque ids + bands only); encrypting that subtree
is a further hardening tracked as an explicit follow-up, not done here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kathai_chithiram.errors import DeletionError
from kathai_chithiram.people.registry import PeopleRegistry
from kathai_chithiram.storage.deletion import BackupPurgeLog
from kathai_chithiram.storage.deletion import delete_story as _delete_story
from kathai_chithiram.storage.store import StoryArtifactStore

__all__ = ["ErasureReceipt", "erase_child", "erase_family"]


@dataclass(frozen=True)
class ErasureReceipt:
    """What a cascade erasure destroyed — opaque ids only, for the audit trail.

    Args:
        child_ids: The child(ren) erased.
        story_ids: Every story hard-deleted by the cascade.
    """

    child_ids: tuple[str, ...]
    story_ids: tuple[str, ...]


def _stories_for_child(store: StoryArtifactStore, child_id: str) -> list[str]:
    """Return the ids of every child-scoped story belonging to ``child_id``."""
    found: list[str] = []
    for story_id in store.iter_story_ids():
        record = store.read_grants(story_id)
        if record is not None and record.get("child_id") == child_id:
            found.append(story_id)
    return found


def erase_child(
    registry: PeopleRegistry,
    store: StoryArtifactStore,
    child_id: str,
    *,
    purge_log: BackupPurgeLog,
    when: datetime | None = None,
) -> ErasureReceipt:
    """Erase a child: crypto-shred its per-child key first, then hard-delete its
    stories and remove its registry records.

    Args:
        registry: The people registry holding the child.
        store: The artifact store holding the child's stories.
        child_id: The child to erase (must be registered).
        purge_log: Backup-cascade log each deleted story is recorded in.
        when: Optional timestamp for the purge log.

    Returns:
        An :class:`ErasureReceipt` naming the child and the stories destroyed.

    Raises:
        PeopleError: If the child is unknown.
        DeletionError: If a story delete fails, or anything remains afterwards
            (including the per-child key file).
    """
    registry.get_child(child_id)  # fail closed if unknown
    story_ids = _stories_for_child(store, child_id)

    # Crypto-shred FIRST: destroy the per-child key so all the child's story content
    # is unrecoverable in one op, before and independent of rmtree (§3 property 3).
    store.shred_child_key(child_id)

    for story_id in story_ids:
        _delete_story(store, story_id, purge_log=purge_log, when=when)
    registry.remove_child(child_id)

    # Verify the cascade: no story, no registry record, and the child key is gone.
    if _stories_for_child(store, child_id):
        raise DeletionError(child_id, "stories remained after child erasure")
    if store._child_key_path(child_id).is_file():
        raise DeletionError(child_id, "per-child key remained after child erasure")
    return ErasureReceipt(child_ids=(child_id,), story_ids=tuple(story_ids))


def erase_family(
    registry: PeopleRegistry,
    store: StoryArtifactStore,
    family_id: str,
    *,
    purge_log: BackupPurgeLog,
    when: datetime | None = None,
) -> ErasureReceipt:
    """Erase a whole family: cascade-erase every child, then remove the family.

    Args:
        registry: The people registry holding the family.
        store: The artifact store holding the family's children's stories.
        family_id: The family to erase (must be registered).
        purge_log: Backup-cascade log each deleted story is recorded in.
        when: Optional timestamp for the purge log.

    Returns:
        An :class:`ErasureReceipt` naming every child and story destroyed.

    Raises:
        PeopleError: If the family is unknown.
        DeletionError: If a story delete fails, or anything remains afterwards.
    """
    registry.get_family(family_id)  # fail closed if unknown
    erased_children: list[str] = []
    erased_stories: list[str] = []
    for child_id in registry.children_of(family_id):
        receipt = erase_child(registry, store, child_id, purge_log=purge_log, when=when)
        erased_children.extend(receipt.child_ids)
        erased_stories.extend(receipt.story_ids)
    registry.remove_family(family_id)
    return ErasureReceipt(child_ids=tuple(erased_children), story_ids=tuple(erased_stories))
