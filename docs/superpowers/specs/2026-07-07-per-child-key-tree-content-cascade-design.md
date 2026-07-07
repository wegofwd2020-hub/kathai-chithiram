# Per-child key tree — content-cascade crypto-shred — design

**Date:** 2026-07-07 · **Status:** approved (brainstorm) · **Owner:** WeGoFwd2020

## Problem

`docs/RETENTION_ERASURE_DESIGN.md §3` proposes a key tree
`master → per-family → per-child → per-story` so that destroying one node's key
crypto-shreds everything beneath it in a single operation, independent of the
`rmtree`/backup cycle (target property 3).

Current state:
- **Stories** (KC-10): each story has a per-story data key wrapped by the **master**
  directly (`<story_dir>/_data_key.wrapped`); `delete_story` crypto-shreds it.
- **Registry**: a single **plaintext** JSON (age-bands, consents, assignments,
  programs — no DOB, no names; already minimized per DPIA A8).
- **`erase_child`**: crypto-shreds each per-story key one by one, then removes the
  plaintext registry records.

Gap: per-story keys wrap under the master, not under a per-child key, so there is no
**single-key cascade shred** for a child's content — the shred is a per-story loop.
Because the A8 ruling means **DOB is never stored** (age-band only), the registry is
low-sensitivity; the bulk sensitive content is the story artifacts. So this slice
targets the **content** cascade and leaves registry-record encryption as a follow-up.

## Scope

**In:** a per-child key layer in the store; child-scoped stories wrap their per-story
key under the **child** key; `erase_child` shreds one per-child key to render all that
child's story content undecryptable in one op; a KC-10-grade cascade-shred test.

**Out:** per-family keys; encrypting the plaintext registry records; the full §3 tree;
any DOB storage. All remain follow-ups. No production email login, no gate crossing —
this is hardening on the already-built synthetic platform (b/c, PRs #84–92).

## Non-goal / gating note

`RETENTION_ERASURE_DESIGN.md` says "no code ships before the ADR-005 D7 / addendum A6
gate clears." That predates the owner ruling the A8 gates (DOB→age-band, basis→parental
consent, auth→local accounts), after which platform b/c was built against **synthetic
identities**. This slice is further hardening on that same synthetic platform — it adds
no new personal-data category (no DOB, no names, no account email) and crosses no open
DPO gate. It must be built and tested against synthetic identities only.

## Architecture

Insert a per-child key between the master and the per-story keys, **for child-scoped
stories only**.

```
master key (KC_STORAGE_KEY)
├─ per-child key   <root>/_children/<child_id>/_child_key.wrapped   (wrapped by master)
│  └─ per-story key  <story_dir>/_data_key.wrapped
│                    <story_dir>/_data_key.parent = <child_id>      (parent marker)
└─ legacy / non-child story:  _data_key.wrapped wrapped by master, NO _data_key.parent
```

Destroying `_child_key.wrapped` makes every per-story key beneath it un-unwrappable, so
every one of that child's story bodies is undecryptable at once — even from a stale
backup ciphertext — before and independent of `rmtree`.

## Components

### 1. `storage/crypto.py`
No new primitives. Reuse existing `generate_data_key()`, `wrap_data_key(master, key)`,
`unwrap_data_key(master, wrapped)` to (a) wrap a per-child key under the master and
(b) wrap a per-story key under the per-child cipher.

### 2. `storage/store.py` — per-child key layer + parent marker

New module constants:
- `_CHILDREN_DIR = "_children"`
- `_CHILD_KEY_FILE = "_child_key.wrapped"`
- `_PARENT_MARKER_FILE = "_data_key.parent"`

New methods on `StoryArtifactStore`:
- `_child_key_path(child_id) -> Path` → `root / _CHILDREN_DIR / child_id / _CHILD_KEY_FILE`.
- `_init_child_key(child_id) -> None` — if no master cipher, no-op; else generate a
  data key, wrap under master, write to the child-key path (idempotent: skip if the
  file exists). Mirrors `_init_story_cipher`.
- `_child_cipher(child_id) -> StorageCipher | None` — `None` if no master cipher;
  else unwrap the child key under the master into a per-child cipher. Raises
  `DecryptionError` if the wrapped child key is missing or cannot be unwrapped
  (fails closed).
- `shred_child_key(child_id) -> None` — delete the wrapped child-key file if present
  (idempotent). This is the single crypto-shred.
- `rewrap_child(child_id, *, new_master) -> None` — unwrap the per-child key under the
  current master and rewrap under `new_master` (bodies and per-story keys untouched).

Changed methods:
- `create_story(..., child_id: str | None = None)` — when `child_id` is given and a
  master cipher is configured: `_init_child_key(child_id)`, generate the per-story data
  key, wrap it under `_child_cipher(child_id)` (not the master), write
  `_data_key.wrapped`, and write `_data_key.parent` = `child_id`. When `child_id` is
  `None`: unchanged (master-wrapped, no marker).
- `_story_cipher(story_dir)` — if `_data_key.parent` exists, read the child id and
  unwrap the story key under `_child_cipher(child_id)`; else the existing behaviour
  (wrapped-under-master, or legacy master-direct). `_init_story_cipher` gains an
  internal wrapping-cipher parameter so `create_story` can direct it to the child
  cipher; its no-arg behaviour is unchanged.

### 3. `access/guarded_store.py`
`create_story_for_child(...)` passes `child_id` through to the underlying
`create_story(child_id=child_id)`. Authorization is unchanged (still consent-gated,
still authorizes before touching the store).

### 4. `people/erasure.py`
`erase_child` calls `store.shred_child_key(child_id)` **first** — the one-op content
shred — then runs the existing per-story `delete_story` loop (rmtree + verify +
backup-log) and `registry.remove_child`. Verification gains: after erasure the child
key is gone and `_child_cipher(child_id)` raises. `erase_family` is unchanged (it
cascades over `erase_child`).

## The crypto-shred proof (test — §8 lifted to child scope)

A cipher-backed store + a registry with one family and **two children**, each with
**≥1 child-scoped story**. Before erasure, capture for a story of child A: the wrapped
per-story key bytes and a story-body ciphertext (a real backup fragment). Then
`erase_child(childA)`. Assert:
- **(a)** child A's `_child_key.wrapped` no longer exists;
- **(b)** child A's stories are gone (rmtree + KC-1 verify); child B's key and stories
  are untouched and still decryptable;
- **(c)** reconstructing a fresh store with the master + writing back the captured
  wrapped story-key and ciphertext, `read_*`/decryption **fails closed** — the per-child
  key needed to unwrap the story key is destroyed (crypto-shred proven, as KC-10's test
  proves per story);
- **(d)** the backup-purge log contains child A + each of its story ids.

## Backward compatibility

- Legacy stories (`_data_key.wrapped` under master, no `_data_key.parent`) — unchanged.
- Plain `create_story` with no `child_id` — master-wrapped, no marker, unchanged.
- Only child-scoped stories created via `create_story_for_child` get the per-child
  parent. Existing envelope, rotation, and erasure tests keep passing.
- `rewrap_story` stays for master-wrapped stories; `rewrap_child` covers the new
  per-child keys. (Master rotation over a store with both must call both — noted for the
  rotation-procedure doc; a mixed-rotation helper is a follow-up, not this slice.)

## Constraints held

- Synthetic identities only; no DOB, no names, no account email; registry stays
  plaintext (age-bands) — out of this slice.
- No behaviour change for non-child stories.
- Fails closed on any missing/!unwrappable key (`DecryptionError`).
- Every new function ships a test (CLAUDE.md); tests mirror source layout; no real child
  data.

## Follow-ups (not this slice)
- Per-family key layer (full §3 tree).
- Encrypt the registry records (bands/consents/programs) under the child key.
- A mixed master-rotation helper that rewraps both per-child and legacy per-story keys.
