# Registry at-rest encryption — design

**Date:** 2026-07-07 · **Status:** approved (brainstorm) · **Owner:** WeGoFwd2020

## Problem

`PeopleRegistry` persists to a single plaintext `people.json` (`save`/`load` over
`to_dict`/`from_dict`). It holds family structure, age **bands** (no DOB, DPIA A8),
consent timestamps, role assignments, and program/goal ids — the least-sensitive data
in the system, but still special-category-adjacent (it records that a child participates
and that consent was given). Stories and their per-story/child/family keys are already
encrypted + crypto-shreddable (KC-5/KC-10, PR #95/#96); the registry file is the last
piece sitting in plaintext on disk.

## Scope

**In:** make `PeopleRegistry.save`/`load` cipher-aware — whole-file encryption under the
master (`KC_STORAGE_KEY`), opt-in and backward-compatible, mirroring the KC-5 store
fallback; thread the master cipher from the CLI.

**Out (explicit non-goal):** per-child crypto-shred cascade of registry records (the
"true §3" option — encrypt each child's payload under its child key). Ruled out this
slice: the registry is minimized (bands/timestamps/ids, no DOB/names), erasure already
deletes records, and per-child registry encryption would re-architect persistence +
couple the registry to the store's cipher layer for low marginal value. Left as a
documented future item. No new personal-data category; synthetic identities only.

## Architecture

Encryption-at-rest for the one registry file, opt-in like KC-5:

- **No master cipher** (no `KC_STORAGE_KEY`) → plaintext `people.json`, byte-identical
  to today. The documented non-production fallback.
- **Master cipher present** → `people.json` is the JSON blob encrypted under the master
  (`StorageCipher.encrypt`). A legacy plaintext file still loads and auto-migrates to
  ciphertext on the next `save`.

This is at-rest protection for the registry, **not** a crypto-shred cascade (the blob is
under the master, not per-child keys) — consistent with the ruled scope.

## Components

### 1. `people/registry.py`

Imports (new): `StorageCipher` (Protocol) and `DecryptionError` from the storage/errors
seams. `people` already depends on `storage` (see `people/erasure.py`), so this adds no
new layering direction.

- `save(self, path: Path, *, cipher: StorageCipher | None = None) -> None`
  - `payload = json.dumps(self.to_dict(), indent=2, sort_keys=True).encode("utf-8")`
  - `data = cipher.encrypt(payload) if cipher is not None else payload`
  - `path.parent.mkdir(...); path.write_bytes(data)`
  - With `cipher=None` the written bytes are the same JSON as the current `write_text`
    output (UTF-8) — backward-compatible on disk.

- `load(cls, path: Path, *, cipher: StorageCipher | None = None) -> PeopleRegistry`
  - Absent file → empty registry (unchanged).
  - Read bytes. **Decrypt-first when a cipher is present** (encrypted is the expected
    state): try `plaintext = cipher.decrypt(raw, artifact=_REGISTRY_ARTIFACT)`; on
    `DecryptionError`, fall back to treating `raw` as legacy plaintext JSON (migration).
  - No cipher: treat `raw` as plaintext JSON only.
  - Parse `json.loads(plaintext)` → `from_dict`. A malformed/undecryptable file with no
    valid fallback raises `PeopleError` (fails closed — an encrypted file cannot be read
    without the key; a wrong key surfaces as the wrapped decrypt failure).
  - New module constant `_REGISTRY_ARTIFACT = "people-registry"` — the single-arg
    `DecryptionError` label (no key/content).

`to_dict`/`from_dict` are unchanged (still no name/DOB).

### 2. `cli.py`

Two helpers mirroring `_open_store` (which already resolves the cipher via
`load_cipher_from_env()`):

- `_load_people(path: Path) -> PeopleRegistry` → `PeopleRegistry.load(path, cipher=load_cipher_from_env())`
- `_save_people(reg: PeopleRegistry, path: Path) -> None` → `reg.save(path, cipher=load_cipher_from_env())`

Replace every `PeopleRegistry.load(args.people_file)` with `_load_people(args.people_file)`
and every `reg.save(args.people_file)` with `_save_people(reg, args.people_file)` (the
family-create / child-add / therapist-add / assign-child / consent / program-create /
erase-child / erase-family paths).

## Tests

Registry (`tests/kathai_chithiram/people/test_registry_encryption.py`):
- Encrypted round-trip: `save(cipher=c)` → the on-disk bytes are **not** JSON-parseable
  and do not contain a known plaintext token (e.g. an age-band string) → proves real
  encryption; `load(cipher=c)` returns an equal registry.
- Plaintext round-trip (`cipher=None`) unchanged; on-disk bytes are valid JSON.
- Legacy migration: write a plaintext `people.json`, `load(cipher=c)` succeeds
  (decrypt-first fails → plaintext fallback), then `save(cipher=c)` re-writes ciphertext.
- Fails closed: `load(cipher=None)` on an encrypted file → `PeopleError`; `load(cipher=wrong)`
  → the decrypt failure is not silently swallowed (no plaintext fallback yields a valid
  registry, so it raises).

CLI (`tests/kathai_chithiram/test_cli.py` or a focused file): with `KC_STORAGE_KEY` set,
a `family-create` then `child-add` writes a `people.json` whose bytes are not
JSON-parseable, and a subsequent read (e.g. `assign-child`/`consent`) round-trips.

## Constraints held

- Opt-in + backward-compatible (no key → plaintext, exactly as now; legacy files migrate).
- Fails closed: no key or wrong key never yields a partial/garbled registry
  (`DecryptionError`/`PeopleError`), never falls back to treating ciphertext as plaintext
  in a way that corrupts data.
- `DecryptionError` carries only the `_REGISTRY_ARTIFACT` label — no key/content.
- No DOB/names (unchanged); synthetic identities only; every new/changed function ships a
  test; no real child data.

## Follow-ups (not this slice)
- Per-child crypto-shred cascade of registry records (the "true §3" option): plaintext
  skeleton + per-child payload under the child key.
- Mixed master-rotation helper (registry blob + family/child/story keys in one pass) —
  note that `rewrap_*` covers keys; the registry blob re-encrypts on the next `save`
  under a rotated master, so registry rotation = re-save (document in the rotation note).
