# Per-Family Key Layer (Family-Cascade Crypto-Shred) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap each per-child key under a per-family key so `erase_family` crypto-shreds all of a family's content in one operation (extends PR #95's per-child cascade one level up).

**Architecture:** `master → <root>/_families/<family_id>/_family_key.wrapped → per-child key (+ <root>/_children/<child_id>/_family.parent marker) → per-story key`. Destroying one family key makes every child key beneath it un-unwrappable. Mirrors the per-child layer exactly, one level up. Legacy PR #95 child keys (master-wrapped, no `_family.parent`) stay untouched.

**Tech Stack:** Python 3.12, AES-256-GCM via `storage/crypto.py` (`generate_data_key`/`wrap_data_key`/`unwrap_data_key`), `pytest`.

## Global Constraints

- No behaviour change for legacy PR #95 child keys (no `_family.parent` marker → wrap/unwrap under master), non-child stories, or plaintext stores (no master cipher → new methods no-op / return `None`).
- Fails closed: missing/un-unwrappable key raises `DecryptionError(artifact)` — single-arg file-name label, never key/content.
- `family_id`/`child_id` validated with `_validate_story_id` (charset `^[A-Za-z0-9_-]+$`) before path building.
- Crypto-shred must be the FIRST destructive act in `erase_family` (before the `erase_child` cascade).
- Registry stays plaintext (registry-record encryption + mixed-rotation helper are explicit follow-ups).
- Synthetic identities only; no DOB/names; every new function ships a test; no real child data.
- Run tests: `.venv/bin/python -m pytest <path>` (bare `pytest` errors — system python3 lacks `wegofwd_video`). Typecheck: `.venv/bin/python -m mypy` (no path args). Lint: `ruff check <paths>`.

## Module constants (add to `src/kathai_chithiram/storage/store.py` near `_CHILD_KEY_FILE`)

```python
_FAMILIES_DIR = "_families"
_FAMILY_KEY_FILE = "_family_key.wrapped"
_FAMILY_MARKER_FILE = "_family.parent"
```

---

### Task 1: Per-family key layer in the store

**Files:**
- Modify: `src/kathai_chithiram/storage/store.py` (add constants + 5 methods after `rewrap_child`)
- Test: `tests/kathai_chithiram/storage/test_store_family_key_layer.py`

**Interfaces:**
- Consumes: `generate_data_key`, `wrap_data_key`, `unwrap_data_key`, `DecryptionError`, `StorageCipher` (all already imported in store.py).
- Produces (methods on `StoryArtifactStore`, direct analogues of `_child_*`):
  - `_family_key_path(self, family_id: str) -> Path`
  - `_init_family_key(self, family_id: str) -> None`
  - `_family_cipher(self, family_id: str) -> StorageCipher | None`
  - `shred_family_key(self, family_id: str) -> None`  *(public)*
  - `rewrap_family(self, family_id: str, *, new_master: StorageCipher) -> None`  *(public)*

- [ ] **Step 1: Write the failing test**

```python
# tests/kathai_chithiram/storage/test_store_family_key_layer.py
"""Per-family key layer: init, cipher round-trip, crypto-shred, rewrap (§3)."""

from __future__ import annotations

import base64

import pytest

from kathai_chithiram.errors import DecryptionError
from kathai_chithiram.storage.crypto import AesGcmCipher, generate_key
from kathai_chithiram.storage.store import StoryArtifactStore


def _cipher() -> AesGcmCipher:
    return AesGcmCipher(base64.urlsafe_b64decode(generate_key()))


def test_init_family_key_is_idempotent_and_wraps_under_master(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_family_key("fam-1")
    key_path = store._family_key_path("fam-1")
    assert key_path.is_file()
    first = key_path.read_bytes()
    store._init_family_key("fam-1")  # idempotent — must not regenerate
    assert key_path.read_bytes() == first


def test_family_cipher_round_trips(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_family_key("fam-1")
    cipher = store._family_cipher("fam-1")
    token = cipher.encrypt(b"hello")
    assert cipher.decrypt(token, artifact="t") == b"hello"


def test_family_cipher_fails_closed_after_shred(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_family_key("fam-1")
    store.shred_family_key("fam-1")
    assert not store._family_key_path("fam-1").is_file()
    with pytest.raises(DecryptionError):
        store._family_cipher("fam-1")


def test_shred_family_is_idempotent(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.shred_family_key("never-created")  # no error


def test_plaintext_store_family_layer_is_noop(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=None)
    store._init_family_key("fam-1")
    assert store._family_cipher("fam-1") is None
    assert not store._family_key_path("fam-1").is_file()


def test_rewrap_family_rotates_under_new_master(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store._init_family_key("fam-1")
    probe = store._family_cipher("fam-1").encrypt(b"x")
    new = _cipher()
    store.rewrap_family("fam-1", new_master=new)
    store._cipher = new
    assert store._family_cipher("fam-1").decrypt(probe, artifact="x") == b"x"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/storage/test_store_family_key_layer.py -v`
Expected: FAIL — `AttributeError: 'StoryArtifactStore' object has no attribute '_family_key_path'`.

- [ ] **Step 3: Write minimal implementation**

Add the three constants (see "Module constants") near `_CHILD_KEY_FILE`. Then add these methods to `StoryArtifactStore`, placed immediately after `rewrap_child`:

```python
    def _family_key_path(self, family_id: str) -> Path:
        """Path to ``family_id``'s wrapped per-family key (store-managed key material)."""
        return self._root / _FAMILIES_DIR / _validate_story_id(family_id) / _FAMILY_KEY_FILE

    def _init_family_key(self, family_id: str) -> None:
        """Create ``family_id``'s per-family key, wrapped under the master (idempotent).

        No-op on a plaintext store (no master cipher). If a wrapped key already
        exists it is left untouched, so re-scoping a child never orphans the
        family's existing children.

        Args:
            family_id: Opaque family id (validated).

        Raises:
            ValueError: If ``family_id`` is unsafe.
            OSError: If the key file cannot be written.
        """
        if self._cipher is None:
            return
        key_path = self._family_key_path(family_id)
        if key_path.is_file():
            return
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(wrap_data_key(self._cipher, generate_data_key()))

    def _family_cipher(self, family_id: str) -> StorageCipher | None:
        """Return ``family_id``'s per-family cipher, unwrapped under the master.

        Returns ``None`` on a plaintext store. Fails closed: a missing or
        un-unwrappable wrapped family key raises :class:`DecryptionError` — this is
        what makes shredding the key crypto-shred every child (and story) beneath it.

        Args:
            family_id: Opaque family id (validated).

        Raises:
            ValueError: If ``family_id`` is unsafe.
            DecryptionError: If the wrapped family key is missing or cannot be
                unwrapped under the configured master.
        """
        if self._cipher is None:
            return None
        key_path = self._family_key_path(family_id)
        if not key_path.is_file():
            raise DecryptionError(_FAMILY_KEY_FILE)
        return unwrap_data_key(
            self._cipher, key_path.read_bytes(), artifact=_FAMILY_KEY_FILE
        )

    def shred_family_key(self, family_id: str) -> None:
        """Destroy ``family_id``'s wrapped per-family key (crypto-shred, §3).

        Deleting this single file renders every per-child key wrapped under it
        un-unwrappable, so all of the family's children's story content becomes
        undecryptable at once — before and independent of ``rmtree`` or the backup
        cycle. Idempotent: absent key is a no-op. No-op on a plaintext store.

        Args:
            family_id: Opaque family id (validated).

        Raises:
            ValueError: If ``family_id`` is unsafe.
        """
        key_path = self._family_key_path(family_id)
        key_path.unlink(missing_ok=True)

    def rewrap_family(self, family_id: str, *, new_master: StorageCipher) -> None:
        """Re-wrap ``family_id``'s per-family key under ``new_master`` (master rotation).

        Unwraps the per-family key with this store's current master, then re-wraps it
        under ``new_master`` in place. Per-child keys (wrapped under the family key)
        and everything beneath are untouched. No-op on a plaintext store or a family
        with no wrapped key.

        Args:
            family_id: Opaque family id (validated).
            new_master: The master cipher to wrap the family key under going forward.

        Raises:
            ValueError: If ``family_id`` is unsafe.
            DecryptionError: If the existing wrapped key cannot be unwrapped under
                this store's current master.
            OSError: If the key file cannot be rewritten.
        """
        if self._cipher is None:
            return
        key_path = self._family_key_path(family_id)
        if not key_path.is_file():
            return
        data_key = self._cipher.decrypt(key_path.read_bytes(), artifact=_FAMILY_KEY_FILE)
        key_path.write_bytes(wrap_data_key(new_master, data_key))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/storage/test_store_family_key_layer.py -v`
Expected: PASS (6 tests). Then `ruff check src/kathai_chithiram/storage/store.py tests/kathai_chithiram/storage/test_store_family_key_layer.py` and `.venv/bin/python -m mypy`.

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/storage/store.py tests/kathai_chithiram/storage/test_store_family_key_layer.py
git commit -m "feat(storage): per-family key layer (init/cipher/shred/rewrap)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Wrap child keys under the family key

**Files:**
- Modify: `src/kathai_chithiram/storage/store.py` (add `_child_key_wrapping_cipher`; change `_init_child_key`, `_child_cipher`, `rewrap_child`, `create_story`, `iter_story_ids`)
- Modify: `src/kathai_chithiram/access/guarded_store.py` (`create_story_for_child`)
- Test: `tests/kathai_chithiram/storage/test_store_family_key_layer.py` (append)

**Interfaces:**
- Consumes: Task 1's `_init_family_key`/`_family_cipher`; the constants.
- Produces:
  - `_child_key_wrapping_cipher(self, child_id: str) -> StorageCipher | None` — the cipher a child key is wrapped under: the per-family key if the child's `_family.parent` marker is present, else the master.
  - `_init_child_key(self, child_id: str, family_id: str | None = None) -> None` — new `family_id` param.
  - `create_story(self, story_id, *, created_at, story_text, delivered=False, child_id=None, family_id: str | None = None)` — new `family_id` kwarg.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/kathai_chithiram/storage/test_store_family_key_layer.py
from datetime import datetime, timezone

_NOW = datetime(2026, 7, 7, tzinfo=timezone.utc)
_SCRIPT = {"schema_version": "1.0", "title": "Calm night", "scenes": []}


def test_family_scoped_child_key_wraps_under_family_key(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="a tale",
                       child_id="kid-1", family_id="fam-1")
    store.write_scene_script("s1", _SCRIPT)
    # Family marker written in the child dir; family key exists; body round-trips.
    child_dir = store._child_key_path("kid-1").parent
    assert (child_dir / "_family.parent").read_text().strip() == "fam-1"
    assert store._family_key_path("fam-1").is_file()
    assert store.read_scene_script("s1") == _SCRIPT


def test_legacy_child_key_without_family_stays_master_wrapped(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    # child_id but NO family_id → PR #95 behaviour: child key wrapped under master.
    store.create_story("s2", created_at=_NOW, story_text="plain", child_id="kid-2")
    store.write_scene_script("s2", _SCRIPT)
    assert not (store._child_key_path("kid-2").parent / "_family.parent").exists()
    assert store.read_scene_script("s2") == _SCRIPT


def test_shredding_family_key_makes_child_scoped_story_unreadable(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="secret",
                       child_id="kid-1", family_id="fam-1")
    store.write_scene_script("s1", _SCRIPT)
    store.shred_family_key("fam-1")
    with pytest.raises(DecryptionError):
        store.read_scene_script("s1")  # story key ← child key ← shredded family key


def test_iter_story_ids_excludes_reserved_dirs(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="x",
                       child_id="kid-1", family_id="fam-1")
    ids = list(store.iter_story_ids())
    assert "s1" in ids
    assert "_children" not in ids
    assert "_families" not in ids


def test_rewrap_child_is_noop_for_family_wrapped_child(tmp_path):
    store = StoryArtifactStore(tmp_path, cipher=_cipher())
    store.create_story("s1", created_at=_NOW, story_text="x",
                       child_id="kid-1", family_id="fam-1")
    store.write_scene_script("s1", _SCRIPT)
    before = store._child_key_path("kid-1").read_bytes()
    store.rewrap_child("kid-1", new_master=_cipher())  # family-wrapped → no-op
    assert store._child_key_path("kid-1").read_bytes() == before
    assert store.read_scene_script("s1") == _SCRIPT  # story still readable (key untouched)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/storage/test_store_family_key_layer.py -k "family_scoped or shredding_family or excludes_reserved or noop_for_family or legacy_child" -v`
Expected: FAIL — `create_story()` got an unexpected keyword argument `family_id`.

- [ ] **Step 3: Write minimal implementation**

Add `_child_key_wrapping_cipher` (place just before `_child_key_path`):

```python
    def _child_key_wrapping_cipher(self, child_id: str) -> StorageCipher | None:
        """The cipher that wraps ``child_id``'s per-child key.

        The per-family key if the child has a ``_family.parent`` marker (family
        cascade, §3), else the master (a legacy PR #95 child key). ``None`` on a
        plaintext store.

        Raises:
            DecryptionError: If the named per-family key is missing/un-unwrappable.
        """
        if self._cipher is None:
            return None
        marker = self._child_key_path(child_id).parent / _FAMILY_MARKER_FILE
        if marker.is_file():
            return self._family_cipher(marker.read_text().strip())
        return self._cipher
```

Change `_init_child_key` to accept `family_id` and wrap under the family cipher when given (write the marker BEFORE resolving the wrapping cipher):

```python
    def _init_child_key(self, child_id: str, family_id: str | None = None) -> None:
        """Create ``child_id``'s per-child key (idempotent).

        When ``family_id`` is given, the child key is wrapped under the per-family
        key and a ``_family.parent`` marker is written in the child's directory, so
        erasing the family crypto-shreds this child (§3). Without ``family_id`` the
        key is wrapped under the master (the legacy PR #95 layout). No-op on a
        plaintext store; an existing wrapped key is left untouched.

        Args:
            child_id: Opaque child id (validated).
            family_id: Optional opaque family id (validated) to scope the child key.

        Raises:
            ValueError: If ``child_id``/``family_id`` is unsafe.
            OSError: If the key file cannot be written.
        """
        if self._cipher is None:
            return
        key_path = self._child_key_path(child_id)
        if key_path.is_file():
            return
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if family_id is not None:
            self._init_family_key(family_id)
            (key_path.parent / _FAMILY_MARKER_FILE).write_text(
                _validate_story_id(family_id), encoding="utf-8"
            )
        wrapping = self._child_key_wrapping_cipher(child_id)
        assert wrapping is not None  # self._cipher is non-None (guard above)
        key_path.write_bytes(wrap_data_key(wrapping, generate_data_key()))
```

Change `_child_cipher` to unwrap through the wrapping cipher:

```python
    def _child_cipher(self, child_id: str) -> StorageCipher | None:
        """Return ``child_id``'s per-child cipher.

        Unwrapped under its wrapping cipher — the per-family key when a
        ``_family.parent`` marker is present, else the master. ``None`` on a
        plaintext store. Fails closed: a missing per-child key, or a
        missing/un-unwrappable family key it depends on, raises
        :class:`DecryptionError` — this is what makes shredding a family (or child)
        key crypto-shred everything beneath it.

        Raises:
            ValueError: If ``child_id`` is unsafe.
            DecryptionError: If the child key file is missing, or its wrapping
                (family/master) key cannot be resolved.
        """
        if self._cipher is None:
            return None
        key_path = self._child_key_path(child_id)
        if not key_path.is_file():
            raise DecryptionError(_CHILD_KEY_FILE)
        wrapping = self._child_key_wrapping_cipher(child_id)
        assert wrapping is not None  # self._cipher is non-None (guard above)
        return unwrap_data_key(wrapping, key_path.read_bytes(), artifact=_CHILD_KEY_FILE)
```

Change `rewrap_child` to skip family-wrapped child keys (add after the `if not key_path.is_file(): return` guard):

```python
        # A family-wrapped child key rotates via rewrap_family, not the master.
        if (key_path.parent / _FAMILY_MARKER_FILE).is_file():
            return
```

Change `create_story` to accept `family_id` and pass it through (the existing child block calls `_init_child_key`):

```python
    def create_story(
        self,
        story_id: str,
        *,
        created_at: datetime,
        story_text: str,
        delivered: bool = False,
        child_id: str | None = None,
        family_id: str | None = None,
    ) -> StoryMetadata:
```

Add to its docstring Args: ``family_id``: If given with ``child_id``, the child key is wrapped under the family key (family-cascade crypto-shred, §3). And change the child block's init call:

```python
        if child_id is not None and self._cipher is not None:
            self._init_child_key(child_id, family_id=family_id)
            # Invariant: child_id (and its family) is fixed at story creation. ...
            (story_dir / _PARENT_MARKER_FILE).write_text(
                _validate_story_id(child_id), encoding="utf-8"
            )
```

Change `iter_story_ids` to skip both reserved dirs:

```python
            if child.is_dir() and child.name not in (_CHILDREN_DIR, _FAMILIES_DIR):
```

In `access/guarded_store.py` `create_story_for_child`, resolve the child's family and pass it. The method already fetches `grants = self._registry.child_grants(child_id)` above the store call; add before the `create_story` call and thread it in:

```python
        family_id = self._registry.get_child(child_id).family_id
        metadata = self._store.create_story(
            story_id,
            created_at=created_at,
            story_text=story_text,
            delivered=delivered,
            child_id=child_id,
            family_id=family_id,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/storage/test_store_family_key_layer.py -v`
Expected: PASS (11 tests).

- [ ] **Step 5: Regression — existing storage + access suites still green**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/storage/ tests/kathai_chithiram/access/ -q`
Expected: all PASS (PR #95's child-key tests, envelope, rotation, guarded-store unchanged). Then `ruff check src/kathai_chithiram/storage/store.py src/kathai_chithiram/access/guarded_store.py` and `.venv/bin/python -m mypy`.

- [ ] **Step 6: Commit**

```bash
git add src/kathai_chithiram/storage/store.py src/kathai_chithiram/access/guarded_store.py tests/kathai_chithiram/storage/test_store_family_key_layer.py
git commit -m "feat(storage): wrap child keys under the per-family key

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `erase_family` cascade crypto-shred + proof test

**Files:**
- Modify: `src/kathai_chithiram/people/erasure.py` (`erase_family`)
- Test: `tests/kathai_chithiram/people/test_erasure_family_shred.py`

**Interfaces:**
- Consumes: Task 1's `store.shred_family_key`, `store._family_key_path`, `store._child_cipher`; Task 2's `create_story(child_id=, family_id=)`.
- Produces: no new public symbol — `erase_family` now shreds the per-family key first and verifies it is gone.

- [ ] **Step 1: Write the failing test (family-cascade proof)**

```python
# tests/kathai_chithiram/people/test_erasure_family_shred.py
"""erase_family crypto-shreds the per-family key first; content fails closed (§3)."""

from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest

from kathai_chithiram.errors import DecryptionError, PeopleError
from kathai_chithiram.people.erasure import erase_family
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/people/test_erasure_family_shred.py -v`
Expected: FAIL — after erasure the family key file still exists (shred not wired), so `assert not ...is_file()` fails.

- [ ] **Step 3: Write minimal implementation**

In `src/kathai_chithiram/people/erasure.py`, in `erase_family`, shred the family key **first** and verify it is gone afterward. Replace the body from `registry.get_family(family_id)` through the `return`:

```python
    registry.get_family(family_id)  # fail closed if unknown

    # Crypto-shred FIRST: destroy the per-family key so every child's key (wrapped
    # under it) and thus all their story content is unrecoverable in one op, before
    # the per-child cascade runs (§3 property 3).
    store.shred_family_key(family_id)

    erased_children: list[str] = []
    erased_stories: list[str] = []
    for child_id in registry.children_of(family_id):
        receipt = erase_child(registry, store, child_id, purge_log=purge_log, when=when)
        erased_children.extend(receipt.child_ids)
        erased_stories.extend(receipt.story_ids)
    registry.remove_family(family_id)

    if store._family_key_path(family_id).is_file():
        raise DeletionError(family_id, "per-family key remained after family erasure")
    return ErasureReceipt(child_ids=tuple(erased_children), story_ids=tuple(erased_stories))
```

Update the `erase_family` docstring summary to note the per-family key is crypto-shredded first, and the module docstring to note the family→child→story content key tree now cascades (registry records still plaintext — do not claim otherwise).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/people/test_erasure_family_shred.py -v`
Expected: PASS.

- [ ] **Step 5: Full regression + lint + typecheck**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/people/ tests/kathai_chithiram/storage/ tests/kathai_chithiram/access/ -q`
Expected: all PASS. Then `ruff check src/kathai_chithiram/people/erasure.py tests/kathai_chithiram/people/test_erasure_family_shred.py` and `.venv/bin/python -m mypy`.

- [ ] **Step 6: Commit**

```bash
git add src/kathai_chithiram/people/erasure.py tests/kathai_chithiram/people/test_erasure_family_shred.py
git commit -m "feat(people): erase_family crypto-shreds the per-family key first (§3 cascade)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- Mirror the merged per-child layer (PR #95) exactly — the family methods are line-for-line analogues one level up. Read `_child_key_path`/`_init_child_key`/`_child_cipher`/`shred_child_key`/`rewrap_child` in `store.py` before writing the family versions.
- `create_story_for_child` in `guarded_store.py` already resolves `grants = self._registry.child_grants(child_id)` and passes `child_id=child_id`; `get_child(child_id).family_id` gives the family (registry is non-None — checked earlier in the method).
- The two type-narrowing `assert wrapping is not None` lines match PR #95's pattern (the `self._cipher is None` guard above already returned), and keep mypy clean.
- Do not encrypt the registry, add a mixed-rotation helper, or store any DOB — all are explicit follow-ups in the spec.
