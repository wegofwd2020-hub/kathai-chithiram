# Registry At-Rest Encryption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `PeopleRegistry.save`/`load` cipher-aware so `people.json` is encrypted at rest under the master key when one is configured, opt-in and backward-compatible.

**Architecture:** Whole-file encryption under the master (`KC_STORAGE_KEY`), mirroring the KC-5 store fallback: no key → plaintext (byte-identical to today); key present → encrypted blob; legacy plaintext auto-migrates on next save. `load` decrypts-first and falls back to plaintext (migration). The CLI threads the master cipher via `load_cipher_from_env()`.

**Tech Stack:** Python 3.12, AES-256-GCM via `storage/crypto.py` `StorageCipher`, `pytest`.

## Global Constraints

- Opt-in + backward-compatible: `cipher=None` writes/reads plaintext exactly as today; a legacy plaintext `people.json` still loads under a configured cipher and migrates on next save.
- Fails closed: no key or wrong key never yields a partial/garbled registry — it raises `PeopleError` (an encrypted file cannot be read without the right key).
- `DecryptionError`/errors carry only a safe artifact label (`_REGISTRY_ARTIFACT = "people-registry"`) — never key bytes or record content.
- `to_dict`/`from_dict` unchanged: still no name, no DOB (DPIA A8) — only opaque ids, bands, consent timestamps.
- Not a crypto-shred cascade (whole-blob under master, not per-child keys) — that's an explicit deferred follow-up.
- Every new/changed function ships a test; tests mirror source layout; no real child data.
- Run tests: `.venv/bin/python -m pytest <path>` (bare `pytest` errors — system python3 lacks `wegofwd_video`). Typecheck: `.venv/bin/python -m mypy` (no path args). Lint: `ruff check <paths>`.

---

### Task 1: Cipher-aware `PeopleRegistry.save`/`load`

**Files:**
- Modify: `src/kathai_chithiram/people/registry.py` (imports + constant + `save`/`load`)
- Test: `tests/kathai_chithiram/people/test_registry_encryption.py`

**Interfaces:**
- Consumes: `StorageCipher` (Protocol) + `DecryptionError` from the storage/errors seams; existing `to_dict`/`from_dict`.
- Produces:
  - `save(self, path: Path, *, cipher: StorageCipher | None = None) -> None`
  - `load(cls, path: Path, *, cipher: StorageCipher | None = None) -> PeopleRegistry`
  - Module constant `_REGISTRY_ARTIFACT = "people-registry"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/kathai_chithiram/people/test_registry_encryption.py
"""At-rest encryption for the people registry (opt-in, master cipher)."""

from __future__ import annotations

import base64
import json

import pytest

from kathai_chithiram.errors import PeopleError
from kathai_chithiram.people.models import AgeBand, Child, Family
from kathai_chithiram.people.registry import PeopleRegistry
from kathai_chithiram.storage.crypto import AesGcmCipher, generate_key


def _cipher() -> AesGcmCipher:
    return AesGcmCipher(base64.urlsafe_b64decode(generate_key()))


def _sample() -> PeopleRegistry:
    reg = PeopleRegistry()
    reg.add_family(Family(family_id="fam-1", owner_id="par-1", member_ids=frozenset({"par-1"})))
    reg.add_child(Child(child_id="kid-1", family_id="fam-1", age_band=AgeBand.AGE_6_8))
    return reg


def test_encrypted_round_trip(tmp_path):
    path = tmp_path / "people.json"
    cipher = _cipher()
    _sample().save(path, cipher=cipher)
    raw = path.read_bytes()
    # Real encryption: not JSON-parseable and the age-band token is absent on disk.
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw)
    assert b"6-8" not in raw
    loaded = PeopleRegistry.load(path, cipher=cipher)
    assert loaded.get_child("kid-1").age_band is AgeBand.AGE_6_8


def test_plaintext_round_trip_unchanged(tmp_path):
    path = tmp_path / "people.json"
    _sample().save(path)  # cipher=None
    raw = path.read_bytes()
    json.loads(raw)  # valid JSON, as before
    loaded = PeopleRegistry.load(path)
    assert loaded.get_child("kid-1").age_band is AgeBand.AGE_6_8


def test_legacy_plaintext_loads_under_a_cipher_then_migrates(tmp_path):
    path = tmp_path / "people.json"
    _sample().save(path)  # legacy plaintext on disk
    cipher = _cipher()
    loaded = PeopleRegistry.load(path, cipher=cipher)  # decrypt-first fails → plaintext fallback
    assert loaded.get_child("kid-1").age_band is AgeBand.AGE_6_8
    loaded.save(path, cipher=cipher)  # migrate
    with pytest.raises(json.JSONDecodeError):
        json.loads(path.read_bytes())


def test_encrypted_file_fails_closed_without_key(tmp_path):
    path = tmp_path / "people.json"
    _sample().save(path, cipher=_cipher())
    with pytest.raises(PeopleError):
        PeopleRegistry.load(path)  # no key → cannot read → fails closed


def test_wrong_key_fails_closed(tmp_path):
    path = tmp_path / "people.json"
    _sample().save(path, cipher=_cipher())
    with pytest.raises(PeopleError):
        PeopleRegistry.load(path, cipher=_cipher())  # different random key


def test_absent_file_is_empty_registry(tmp_path):
    reg = PeopleRegistry.load(tmp_path / "missing.json", cipher=_cipher())
    assert list(reg.children_of("fam-1")) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/people/test_registry_encryption.py -v`
Expected: FAIL — `save()` got an unexpected keyword argument `cipher`.

- [ ] **Step 3: Write minimal implementation**

Add to `registry.py` imports (near the existing `from kathai_chithiram.errors import PeopleError`):

```python
from kathai_chithiram.errors import DecryptionError, PeopleError
from kathai_chithiram.storage.crypto import StorageCipher
```

Add a module constant near `__all__`:

```python
#: Safe artifact label for a registry decrypt failure (no key/content).
_REGISTRY_ARTIFACT = "people-registry"
```

Replace `save` and `load` with:

```python
    def save(self, path: Path, *, cipher: StorageCipher | None = None) -> None:
        """Write the registry to ``path`` (creating parent dirs).

        With ``cipher`` the JSON is encrypted at rest under the master (KC-5 parity);
        without it the file is plaintext (the documented non-production fallback),
        byte-compatible with earlier releases.

        Args:
            path: Destination file.
            cipher: Optional master cipher; when set the file is written encrypted.

        Raises:
            OSError: If the file cannot be written.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2, sort_keys=True).encode("utf-8")
        path.write_bytes(cipher.encrypt(payload) if cipher is not None else payload)

    @classmethod
    def load(cls, path: Path, *, cipher: StorageCipher | None = None) -> PeopleRegistry:
        """Load a registry from ``path``; return an empty one if the file is absent.

        With a ``cipher`` the file is expected encrypted (KC-5 parity): the bytes are
        decrypted first, and only if that fails are they treated as legacy plaintext
        JSON (automatic migration on the next :meth:`save`). Without a cipher the bytes
        must be plaintext JSON. Fails closed — an encrypted file cannot be read without
        the right key.

        Args:
            path: Source file.
            cipher: Optional master cipher; when set, decryption is attempted first.

        Raises:
            PeopleError: If the file exists but cannot be decrypted and is not valid
                registry JSON (fails closed on a missing/wrong key).
        """
        if not path.exists():
            return cls()
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise PeopleError(f"registry file could not be read: {exc}") from exc

        text: str | None = None
        if cipher is not None:
            try:
                text = cipher.decrypt(raw, artifact=_REGISTRY_ARTIFACT).decode("utf-8")
            except DecryptionError:
                text = None  # fall back to legacy plaintext (migration)
        if text is None:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise PeopleError(f"registry file is not valid JSON: {exc}") from exc

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PeopleError(f"registry file is not valid JSON: {exc}") from exc
        return cls.from_dict(data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/people/test_registry_encryption.py -v`
Expected: PASS (6 tests). Then `ruff check src/kathai_chithiram/people/registry.py tests/kathai_chithiram/people/test_registry_encryption.py` and `.venv/bin/python -m mypy`.

- [ ] **Step 5: Regression — existing people suite**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/people/ -q`
Expected: all PASS (the existing `test_registry.py` round-trip tests still pass — they call `save`/`load` with no cipher).

- [ ] **Step 6: Commit**

```bash
git add src/kathai_chithiram/people/registry.py tests/kathai_chithiram/people/test_registry_encryption.py
git commit -m "feat(people): opt-in at-rest encryption for the registry

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Thread the master cipher from the CLI

**Files:**
- Modify: `src/kathai_chithiram/cli.py` (add 3 helpers; replace 16 call sites)
- Test: `tests/kathai_chithiram/people/test_registry_encryption.py` (append CLI-helper tests)

**Interfaces:**
- Consumes: Task 1's `PeopleRegistry.save/load(*, cipher=)`; `load_cipher_from_env` (from `kathai_chithiram.storage`); `EncryptionKeyError`.
- Produces (module-level in cli.py):
  - `_people_cipher() -> StorageCipher | None`
  - `_load_people(path: Path) -> PeopleRegistry`
  - `_save_people(reg: PeopleRegistry, path: Path) -> None`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/kathai_chithiram/people/test_registry_encryption.py
from kathai_chithiram.storage import STORAGE_KEY_ENV


def test_cli_helpers_round_trip_encrypted(tmp_path, monkeypatch):
    from kathai_chithiram import cli
    monkeypatch.setenv(STORAGE_KEY_ENV, generate_key())
    path = tmp_path / "people.json"
    cli._save_people(_sample(), path)
    with pytest.raises(json.JSONDecodeError):
        json.loads(path.read_bytes())  # CLI wrote it encrypted
    loaded = cli._load_people(path)
    assert loaded.get_child("kid-1").age_band is AgeBand.AGE_6_8


def test_cli_helpers_plaintext_without_key(tmp_path, monkeypatch):
    from kathai_chithiram import cli
    monkeypatch.delenv(STORAGE_KEY_ENV, raising=False)
    path = tmp_path / "people.json"
    cli._save_people(_sample(), path)
    json.loads(path.read_bytes())  # no key → plaintext
    assert cli._load_people(path).get_child("kid-1").age_band is AgeBand.AGE_6_8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/people/test_registry_encryption.py -k cli_helpers -v`
Expected: FAIL — `AttributeError: module 'kathai_chithiram.cli' has no attribute '_save_people'`.

- [ ] **Step 3: Write minimal implementation**

Add these helpers to `cli.py` (place them next to `_open_store`, ~line 1636). `sys` and `PeopleRegistry` are already imported in cli.py; add a `StorageCipher` import at the top if not present (`from kathai_chithiram.storage.crypto import StorageCipher`).

```python
def _people_cipher() -> StorageCipher | None:
    """Resolve the master cipher for the people registry (KC-5), or exit on a bad key.

    Mirrors :func:`_open_store`: reads ``KC_STORAGE_KEY`` from the environment;
    returns ``None`` for a plaintext registry when unset. A malformed key prints an
    error and exits cleanly rather than raising an opaque traceback.
    """
    from kathai_chithiram.errors import EncryptionKeyError
    from kathai_chithiram.storage import load_cipher_from_env

    try:
        return load_cipher_from_env()
    except EncryptionKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _load_people(path: Path) -> PeopleRegistry:
    """Load the people registry, decrypting at rest when a key is configured."""
    return PeopleRegistry.load(path, cipher=_people_cipher())


def _save_people(reg: PeopleRegistry, path: Path) -> None:
    """Save the people registry, encrypting at rest when a key is configured."""
    reg.save(path, cipher=_people_cipher())
```

Then replace every people-file call site (lines ~1067–1202: family-create, child-add, therapist-add, assign-child, consent, program-create, erase-child, erase-family):

- `reg = PeopleRegistry.load(args.people_file)` → `reg = _load_people(args.people_file)`
- `reg.save(args.people_file)` → `_save_people(reg, args.people_file)`

There are 8 `load` and 8 `save` call sites — replace all 16. (Use a careful find/replace: the load lines are exactly `PeopleRegistry.load(args.people_file)`; the save lines are exactly `reg.save(args.people_file)`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/people/test_registry_encryption.py -v`
Expected: PASS (8 tests). Then `ruff check src/kathai_chithiram/cli.py` and `.venv/bin/python -m mypy`.

- [ ] **Step 5: Regression — CLI + people suites**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/test_cli.py tests/kathai_chithiram/people/ -q`
Expected: all PASS (existing CLI people-command tests run without `KC_STORAGE_KEY`, so they exercise the plaintext path unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/kathai_chithiram/cli.py tests/kathai_chithiram/people/test_registry_encryption.py
git commit -m "feat(cli): encrypt the people registry at rest when a key is set

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- Run tests with `.venv/bin/python -m pytest` (bare `pytest` errors on unrelated `wegofwd_video` collection — pre-existing, system-python only).
- `people` already depends on `storage` (see `people/erasure.py`), so importing `StorageCipher` into `registry.py` adds no new layering direction and no import cycle (`storage/crypto.py` imports only `errors`).
- Do NOT change `to_dict`/`from_dict`, add per-child registry encryption, or store any DOB — all are explicit follow-ups in the spec.
- The wrong-key test asserts `PeopleError` (not `DecryptionError`): decrypt-first raises `DecryptionError`, the plaintext fallback then fails to parse the ciphertext, and `load` surfaces that as `PeopleError` — still fails closed (no valid registry returned).
