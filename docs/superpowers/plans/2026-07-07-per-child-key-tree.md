# Per-Child Key Tree (Content-Cascade Crypto-Shred) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insert a per-child key between the master and per-story keys so `erase_child` crypto-shreds all of a child's story content in one operation, independent of `rmtree`.

**Architecture:** A per-child key lives at `<root>/_children/<child_id>/_child_key.wrapped`, wrapped under the master. Child-scoped stories wrap their per-story key under the **child** key (not the master) and carry a `_data_key.parent` marker naming the child. Destroying the child key makes every per-story key beneath it un-unwrappable. Legacy/non-child stories (master-wrapped, no marker) are untouched.

**Tech Stack:** Python 3.12, AES-256-GCM via `storage/crypto.py` (`generate_data_key`/`wrap_data_key`/`unwrap_data_key`), `pytest`.

## Global Constraints

- No behaviour change for non-child stories (master-wrapped, no `_data_key.parent`) or plaintext stores (no master cipher → all new methods no-op / return `None`).
- Everything fails closed: a missing or un-unwrappable key raises `DecryptionError(artifact)` (single-arg: a safe file-name label, never key/content).
- Child ids are path components → validate with `_validate_story_id` (charset `^[A-Za-z0-9_-]+$`, same as the people-model id charset) before use.
- Synthetic identities only; no DOB, no names; registry stays plaintext (out of scope).
- Every new function ships a test; tests mirror source layout; no real child data.
- Crypto-shred must be the **first** destructive act in `erase_child` (before `rmtree`), per RETENTION_ERASURE_DESIGN §3 property 3.

## Module constants (add to `src/kathai_chithiram/storage/store.py` near `_WRAPPED_KEY_FILE = "_data_key.wrapped"`)

```python
_CHILDREN_DIR = "_children"
_CHILD_KEY_FILE = "_child_key.wrapped"
_PARENT_MARKER_FILE = "_data_key.parent"
```

---

### Task 1: Per-child key layer in the store

**Files:**
- Modify: `src/kathai_chithiram/storage/store.py` (add constants + 5 methods)
- Test: `tests/kathai_chithiram/storage/test_store_child_key_tree.py`

**Interfaces:**
- Consumes: `generate_data_key`, `wrap_data_key`, `unwrap_data_key` (already imported in store.py); `DecryptionError` (import if not already), `StorageCipher`.
- Produces (methods on `StoryArtifactStore`):
  - `_child_key_path(self, child_id: str) -> Path`
  - `_init_child_key(self, child_id: str) -> None`
  - `_child_cipher(self, child_id: str) -> StorageCipher | None`
  - `shred_child_key(self, child_id: str) -> None`  *(public)*
  - `rewrap_child(self, child_id: str, *, new_master: StorageCipher) -> None`  *(public)*

- [ ] **Step 1: Write the failing test**

```python
# tests/kathai_chithiram/storage/test_store_child_key_tree.py
"""Per-child key layer: init, cipher round-trip, crypto-shred, rewrap (KC-10 / §3)."""

from __future__ import annotations

import pytest

from kathai_chithiram.errors import DecryptionError
from kathai_chithiram.storage.crypto import AesGcmCipher, generate_key
from kathai_chithiram.storage.store import StoryArtifactStore


def _cipher() -> AesGcmCipher:
    import base64
    return AesGcmCipher(base64.b64decode(generate_key()))


def test_init_child_key_is_idempotent_and_wraps_under_master(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_child_key("child-1")
    key_path = store._child_key_path("child-1")
    assert key_path.is_file()
    first = key_path.read_bytes()
    store._init_child_key("child-1")  # idempotent — must not regenerate
    assert key_path.read_bytes() == first


def test_child_cipher_round_trips(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_child_key("child-1")
    cipher = store._child_cipher("child-1")
    token = cipher.encrypt(b"hello")
    assert cipher.decrypt(token, artifact="t") == b"hello"


def test_child_cipher_fails_closed_after_shred(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_child_key("child-1")
    store.shred_child_key("child-1")
    assert not store._child_key_path("child-1").is_file()
    with pytest.raises(DecryptionError):
        store._child_cipher("child-1")


def test_shred_is_idempotent(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.shred_child_key("never-created")  # no error


def test_plaintext_store_child_layer_is_noop(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=None)
    store._init_child_key("child-1")
    assert store._child_cipher("child-1") is None
    assert not store._child_key_path("child-1").is_file()


def test_rewrap_child_rotates_under_new_master(tmp_path):
    old = _cipher()
    store = StoryArtifactStore(tmp_path, cipher=old)
    store._init_child_key("child-1")
    plain_cipher = store._child_cipher("child-1")
    probe = plain_cipher.encrypt(b"x")

    new = _cipher()
    store.rewrap_child("child-1", new_master=new)
    # Old master can no longer unwrap; new master can, and yields the SAME data key.
    store._cipher = new
    assert store._child_cipher("child-1").decrypt(probe, artifact="x") == b"x"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/kathai_chithiram/storage/test_store_child_key_tree.py -v`
Expected: FAIL — `AttributeError: 'StoryArtifactStore' object has no attribute '_child_key_path'`.

- [ ] **Step 3: Write minimal implementation**

Add the three constants (see "Module constants" above) near `_WRAPPED_KEY_FILE`. Ensure `from kathai_chithiram.errors import DecryptionError` is present (add to the existing errors import if missing). Then add these methods to `StoryArtifactStore` (place them right after `_init_story_cipher`):

```python
    def _child_key_path(self, child_id: str) -> Path:
        """Path to ``child_id``'s wrapped per-child key (store-managed key material)."""
        return self._root / _CHILDREN_DIR / _validate_story_id(child_id) / _CHILD_KEY_FILE

    def _init_child_key(self, child_id: str) -> None:
        """Create ``child_id``'s per-child key, wrapped under the master (idempotent).

        No-op on a plaintext store (no master cipher). If a wrapped key already
        exists it is left untouched, so re-creating a child's story never orphans
        that child's existing stories.

        Args:
            child_id: Opaque child id (validated).

        Raises:
            ValueError: If ``child_id`` is unsafe.
            OSError: If the key file cannot be written.
        """
        if self._cipher is None:
            return
        key_path = self._child_key_path(child_id)
        if key_path.is_file():
            return
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(wrap_data_key(self._cipher, generate_data_key()))

    def _child_cipher(self, child_id: str) -> StorageCipher | None:
        """Return ``child_id``'s per-child cipher, unwrapped under the master.

        Returns ``None`` on a plaintext store. Fails closed: a missing or
        un-unwrappable wrapped child key raises :class:`DecryptionError` — this is
        what makes shredding the key crypto-shred every story beneath it.

        Args:
            child_id: Opaque child id (validated).

        Raises:
            ValueError: If ``child_id`` is unsafe.
            DecryptionError: If the wrapped child key is missing or cannot be
                unwrapped under the configured master.
        """
        if self._cipher is None:
            return None
        key_path = self._child_key_path(child_id)
        if not key_path.is_file():
            raise DecryptionError(_CHILD_KEY_FILE)
        return unwrap_data_key(
            self._cipher, key_path.read_bytes(), artifact=_CHILD_KEY_FILE
        )

    def shred_child_key(self, child_id: str) -> None:
        """Destroy ``child_id``'s wrapped per-child key (crypto-shred, §3).

        Deleting this single file renders every per-story key wrapped under it
        un-unwrappable, so all of the child's story content becomes undecryptable at
        once — before and independent of ``rmtree`` or the backup cycle. Idempotent:
        absent key is a no-op. No-op on a plaintext store.

        Args:
            child_id: Opaque child id (validated).

        Raises:
            ValueError: If ``child_id`` is unsafe.
        """
        key_path = self._child_key_path(child_id)
        key_path.unlink(missing_ok=True)

    def rewrap_child(self, child_id: str, *, new_master: StorageCipher) -> None:
        """Re-wrap ``child_id``'s per-child key under ``new_master`` (master rotation).

        Unwraps the per-child key with this store's current master, then re-wraps it
        under ``new_master`` in place. Per-story keys (wrapped under the child key)
        and artifact bodies are untouched. No-op on a plaintext store or a child with
        no wrapped key.

        Args:
            child_id: Opaque child id (validated).
            new_master: The master cipher to wrap the child key under going forward.

        Raises:
            ValueError: If ``child_id`` is unsafe.
            DecryptionError: If the existing wrapped key cannot be unwrapped under
                this store's current master.
            OSError: If the key file cannot be rewritten.
        """
        if self._cipher is None:
            return
        key_path = self._child_key_path(child_id)
        if not key_path.is_file():
            return
        data_key = self._cipher.decrypt(key_path.read_bytes(), artifact=_CHILD_KEY_FILE)
        key_path.write_bytes(wrap_data_key(new_master, data_key))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/kathai_chithiram/storage/test_store_child_key_tree.py -v`
Expected: PASS (6 tests). Then `ruff check src/kathai_chithiram/storage/store.py tests/kathai_chithiram/storage/test_store_child_key_tree.py` — fix any lint.

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/storage/store.py tests/kathai_chithiram/storage/test_store_child_key_tree.py
git commit -m "feat(storage): per-child key layer (init/cipher/shred/rewrap)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Wire child-scoped stories to the child key

**Files:**
- Modify: `src/kathai_chithiram/storage/store.py` (`_story_cipher`, `_init_story_cipher`, `create_story`; add `_wrapping_cipher`)
- Modify: `src/kathai_chithiram/access/guarded_store.py` (`create_story_for_child`)
- Test: `tests/kathai_chithiram/storage/test_store_child_key_tree.py` (append)

**Interfaces:**
- Consumes: Task 1's `_init_child_key`, `_child_cipher`, `shred_child_key`; the constants.
- Produces:
  - `_wrapping_cipher(self, story_dir: Path) -> StorageCipher | None` — the cipher a story's data key is wrapped under: the per-child key if `_data_key.parent` is present, else the master.
  - `create_story(self, story_id, *, created_at, story_text, delivered=False, child_id: str | None = None) -> StoryMetadata` — new `child_id` kwarg.

- [ ] **Step 1: Write the failing test**

The store has **no public raw-text reader** (`story.txt` is write-only via the API); the envelope tests prove round-trip through `write_scene_script`/`read_scene_script`, so these tests do the same. `_SCRIPT` mirrors the envelope test's constant (no contract validation on write).

```python
# append to tests/kathai_chithiram/storage/test_store_child_key_tree.py
from datetime import datetime, timezone

_NOW = datetime(2026, 7, 7, tzinfo=timezone.utc)
_SCRIPT = {"schema_version": "1.0", "title": "Calm night", "scenes": []}


def test_child_scoped_story_wraps_under_child_key_and_reads_back(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="a tale", child_id="child-1")
    store.write_scene_script("s1", _SCRIPT)
    # Parent marker written; child key exists; body round-trips through the child key.
    assert (store.story_dir("s1") / "_data_key.parent").read_text().strip() == "child-1"
    assert store._child_key_path("child-1").is_file()
    assert store.read_scene_script("s1") == _SCRIPT


def test_non_child_story_stays_master_wrapped(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s2", created_at=_NOW, story_text="plain")
    store.write_scene_script("s2", _SCRIPT)
    assert not (store.story_dir("s2") / "_data_key.parent").exists()
    assert store.read_scene_script("s2") == _SCRIPT


def test_shredding_child_key_makes_its_story_unreadable(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="secret", child_id="child-1")
    store.write_scene_script("s1", _SCRIPT)
    store.shred_child_key("child-1")
    with pytest.raises(DecryptionError):
        store.read_scene_script("s1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/kathai_chithiram/storage/test_store_child_key_tree.py -k child_scoped -v`
Expected: FAIL — `create_story()` got an unexpected keyword argument `child_id`.

- [ ] **Step 3: Write minimal implementation**

In `store.py`, replace `_story_cipher` and `_init_story_cipher` so both resolve the wrapping cipher through one helper, and add `_wrapping_cipher`:

```python
    def _wrapping_cipher(self, story_dir: Path) -> StorageCipher | None:
        """The cipher that wraps this story's per-story data key.

        The per-child key if the story is child-scoped (a ``_data_key.parent`` marker
        names the child), else the master. ``None`` on a plaintext store.

        Raises:
            DecryptionError: If the named per-child key is missing/un-unwrappable.
        """
        if self._cipher is None:
            return None
        marker = story_dir / _PARENT_MARKER_FILE
        if marker.is_file():
            return self._child_cipher(marker.read_text().strip())
        return self._cipher

    def _story_cipher(self, story_dir: Path) -> StorageCipher | None:
        """Return the cipher that encrypts ``story_dir``'s artifact bodies (KC-10 / §3).

        * No master cipher → ``None`` (plaintext store).
        * ``_data_key.wrapped`` present → the per-story data key, unwrapped under its
          wrapping cipher: the per-child key when a ``_data_key.parent`` marker is
          present, else the master.
        * No wrapped-key file → the master itself (a legacy KC-5 store).

        Raises:
            DecryptionError: If a wrapped key (per-story or per-child) cannot be
                unwrapped under the configured master.
        """
        if self._cipher is None:
            return None
        key_path = story_dir / _WRAPPED_KEY_FILE
        if not key_path.is_file():
            return self._cipher
        return unwrap_data_key(
            self._wrapping_cipher(story_dir),
            key_path.read_bytes(),
            artifact=_WRAPPED_KEY_FILE,
        )

    def _init_story_cipher(self, story_dir: Path) -> StorageCipher | None:
        """Create (or load) ``story_dir``'s per-story cipher at story creation.

        The new per-story data key is wrapped under the story's wrapping cipher (the
        per-child key if a ``_data_key.parent`` marker is present, else the master).
        Idempotent: an existing wrapped key is loaded, never regenerated.

        Raises:
            DecryptionError: If an existing/needed wrapping key cannot be resolved.
            OSError: If the wrapped-key file cannot be written.
        """
        if self._cipher is None:
            return None
        key_path = story_dir / _WRAPPED_KEY_FILE
        if key_path.is_file():
            return self._story_cipher(story_dir)
        wrapping = self._wrapping_cipher(story_dir)
        key_path.write_bytes(wrap_data_key(wrapping, generate_data_key()))
        return self._story_cipher(story_dir)
```

Then update `create_story` to accept and honour `child_id` (write the child key + marker **before** the story cipher is initialised, so `_init_story_cipher` wraps under the child key):

```python
    def create_story(
        self,
        story_id: str,
        *,
        created_at: datetime,
        story_text: str,
        delivered: bool = False,
        child_id: str | None = None,
    ) -> StoryMetadata:
        """Create a story directory with its raw text and metadata.

        Args:
            story_id: Opaque story identifier.
            created_at: Creation timestamp recorded in metadata.
            story_text: The raw parent-authored story.
            delivered: Initial delivered flag (default ``False``).
            child_id: If given, the story is child-scoped: its per-story key is
                wrapped under the child's key (not the master) and a
                ``_data_key.parent`` marker is written, so erasing the child
                crypto-shreds this story's content (RETENTION_ERASURE_DESIGN §3).

        Returns:
            The written :class:`StoryMetadata`.

        Raises:
            ValueError: If ``story_id`` or ``child_id`` is unsafe.
            OSError: If the files cannot be written.
        """
        story_dir = self.story_dir(story_id)
        story_dir.mkdir(parents=True, exist_ok=True)
        if child_id is not None and self._cipher is not None:
            self._init_child_key(child_id)
            (story_dir / _PARENT_MARKER_FILE).write_text(
                _validate_story_id(child_id), encoding="utf-8"
            )
        cipher = self._init_story_cipher(story_dir)
        (story_dir / _STORY_TEXT_FILE).write_bytes(
            self._seal(story_text.encode("utf-8"), cipher)
        )
        metadata = StoryMetadata(
            story_id=story_id, created_at=created_at, delivered=delivered
        )
        self._write_metadata(story_dir, metadata)
        return metadata
```

In `access/guarded_store.py`, pass `child_id` through in `create_story_for_child` (the `self._store.create_story(...)` call, currently around line 150):

```python
        metadata = self._store.create_story(
            story_id,
            created_at=created_at,
            story_text=story_text,
            delivered=delivered,
            child_id=child_id,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/kathai_chithiram/storage/test_store_child_key_tree.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Regression — existing storage + access suites still green**

Run: `pytest tests/kathai_chithiram/storage/ tests/kathai_chithiram/access/ -q`
Expected: all PASS (envelope, rotation, guarded-store, erasure tests unchanged). Then `ruff check src/kathai_chithiram/storage/store.py src/kathai_chithiram/access/guarded_store.py`.

- [ ] **Step 6: Commit**

```bash
git add src/kathai_chithiram/storage/store.py src/kathai_chithiram/access/guarded_store.py tests/kathai_chithiram/storage/test_store_child_key_tree.py
git commit -m "feat(storage): wrap child-scoped story keys under the per-child key

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `erase_child` cascade crypto-shred + proof test

**Files:**
- Modify: `src/kathai_chithiram/people/erasure.py` (`erase_child`)
- Test: `tests/kathai_chithiram/people/test_erasure_crypto_shred.py`

**Interfaces:**
- Consumes: Task 1's `store.shred_child_key`, `store._child_cipher`; Task 2's `create_story(child_id=...)`.
- Produces: no new public symbol — `erase_child` now shreds the per-child key first and verifies it is gone.

- [ ] **Step 1: Write the failing test (the §8 proof, child-scoped)**

```python
# tests/kathai_chithiram/people/test_erasure_crypto_shred.py
"""erase_child crypto-shreds the per-child key first; content fails closed (§3/§8)."""

from __future__ import annotations

import base64
from datetime import date, datetime, timezone

import pytest

from kathai_chithiram.errors import DecryptionError
from kathai_chithiram.people.erasure import erase_child
from kathai_chithiram.people.models import (
    AgeBand, Child, Family, ParentalConsent,
)
from kathai_chithiram.people.registry import PeopleRegistry
from kathai_chithiram.storage.crypto import AesGcmCipher, generate_key
from kathai_chithiram.storage.deletion import BackupPurgeLog
from kathai_chithiram.storage.store import StoryArtifactStore

_NOW = datetime(2026, 7, 7, tzinfo=timezone.utc)
_SCRIPT = {"schema_version": "1.0", "title": "Calm night", "scenes": []}


def _master() -> AesGcmCipher:
    return AesGcmCipher(base64.b64decode(generate_key()))


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
        store._child_cipher("kid-a")
    # (d) receipt (→ backup-purge log) carries the child + story ids
    assert "a1" in receipt.story_ids and "kid-a" in receipt.child_ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/kathai_chithiram/people/test_erasure_crypto_shred.py -v`
Expected: FAIL — after erasure the child key file still exists (shred not wired yet), so `assert not ...is_file()` fails.

- [ ] **Step 3: Write minimal implementation**

In `src/kathai_chithiram/people/erasure.py`, in `erase_child`, shred the per-child key **first** (after collecting `story_ids`, before the delete loop) and add it to the post-erasure verification. Replace the body from the `story_ids = ...` line through the `return`:

```python
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
```

Update the `erase_child` docstring's summary line to note the per-child key is crypto-shredded first, and the module docstring's "key tree ... is a further hardening ... plaintext for now" paragraph to note the per-child **content** key tree now cascades (registry records still plaintext). Keep it accurate — do not claim the registry is encrypted.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/kathai_chithiram/people/test_erasure_crypto_shred.py -v`
Expected: PASS.

- [ ] **Step 5: Full regression + lint + typecheck**

Run: `pytest tests/kathai_chithiram/people/ tests/kathai_chithiram/storage/ tests/kathai_chithiram/access/ -q`
Expected: all PASS. Then `ruff check src/kathai_chithiram/people/erasure.py tests/kathai_chithiram/people/test_erasure_crypto_shred.py` and `.venv/bin/python -m mypy` (canonical, no path args — uses pyproject `packages=["kathai_chithiram"]`).

- [ ] **Step 6: Commit**

```bash
git add src/kathai_chithiram/people/erasure.py tests/kathai_chithiram/people/test_erasure_crypto_shred.py
git commit -m "feat(people): erase_child crypto-shreds the per-child key first (§3 cascade)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- Run the full suite with `.venv/bin/python -m pytest` (system `python` is absent; bare `pytest` uses system `python3` which lacks the `wegofwd_video` git-dep and errors on collecting `test_cli.py`/`video/test_video.py` — pre-existing, unrelated).
- The store has no public raw-text reader; round-trips are proven via `write_scene_script`/`read_scene_script` (confirmed against `store.py` + the envelope tests). Add no new accessor.
- Do not touch the registry's plaintext persistence, add per-family keys, or store any DOB — all are explicit follow-ups in the spec.
