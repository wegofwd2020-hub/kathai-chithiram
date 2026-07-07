# Per-family key layer — family-cascade crypto-shred — design

**Date:** 2026-07-07 · **Status:** approved (brainstorm) · **Owner:** WeGoFwd2020

## Problem

The content-cascade slice (PR #95) built `master → per-child → per-story`: erasing a
child shreds one per-child key and all that child's story content becomes undecryptable
in one op. The per-child key is wrapped under the **master** directly, so there is no
single-key cascade for a whole **family** — `erase_family` today loops over `erase_child`
(each shred is per-child).

`docs/RETENTION_ERASURE_DESIGN.md §3` proposes the full tree
`master → per-family → per-child → per-story`. This slice adds the **per-family** level:
wrap each per-child key under a **per-family key** (which itself wraps under the master),
so destroying one family key renders every child key — and therefore every story — under
that family un-unwrappable in a single operation.

## Scope

**In:** a per-family key layer in the store, mirroring the per-child layer one level up;
child keys wrap under their family key; `erase_family` shreds one per-family key first;
a proof test.

**Out:** encrypting the plaintext registry records; the mixed master-rotation
orchestration helper (rotating legacy master-wrapped child keys + family keys in one
pass). Both remain explicit follow-ups. No new personal-data category; synthetic
identities only; no gate crossed (hardening on the already-built synthetic platform).

## Architecture

```
master key (KC_STORAGE_KEY)
└─ per-family key   <root>/_families/<family_id>/_family_key.wrapped   (wrapped by master)
   └─ per-child key  <root>/_children/<child_id>/_child_key.wrapped
                     <root>/_children/<child_id>/_family.parent = <family_id>   (marker)
      └─ per-story key  <story_dir>/_data_key.wrapped + _data_key.parent (unchanged, PR #95)
```

Destroying `_family_key.wrapped` makes every child key wrapped under it un-unwrappable,
so every child's stories become undecryptable at once — before and independent of
`rmtree`, exactly as the child-level shred does for one child.

## Components

### 1. `storage/store.py` — per-family key layer (mirrors the per-child layer)

New module constants:
- `_FAMILIES_DIR = "_families"`
- `_FAMILY_KEY_FILE = "_family_key.wrapped"`
- `_FAMILY_MARKER_FILE = "_family.parent"`  (written in the child's directory)

New methods on `StoryArtifactStore` (direct analogues of `_child_*`):
- `_family_key_path(family_id) -> Path` → `root / _FAMILIES_DIR / family_id / _FAMILY_KEY_FILE`
  (`family_id` validated with `_validate_story_id` before path building).
- `_init_family_key(family_id) -> None` — no-op without a master cipher; else generate a
  data key, wrap under the master, write to the family-key path (idempotent).
- `_family_cipher(family_id) -> StorageCipher | None` — `None` on a plaintext store; else
  unwrap the family key under the master. Raises `DecryptionError(_FAMILY_KEY_FILE)` if
  the wrapped key is missing/un-unwrappable (fails closed).
- `shred_family_key(family_id) -> None` — `unlink(missing_ok=True)` the wrapped family key
  (idempotent; the single family-level crypto-shred).
- `rewrap_family(family_id, *, new_master) -> None` — unwrap under the current master,
  re-wrap under `new_master` in place (child keys + bodies untouched).

New helper (mirrors `_wrapping_cipher` for stories):
- `_child_key_wrapping_cipher(child_id) -> StorageCipher | None` — the cipher a child key
  is wrapped under: the per-family key if the child's `_family.parent` marker is present,
  else the master. `None` on a plaintext store. Raises `DecryptionError` if the named
  family key is missing/un-unwrappable.

Changed methods:
- `_init_child_key(child_id, family_id: str | None = None)` — when `family_id` is given
  and a master cipher is configured: `_init_family_key(family_id)`, write the child's
  `_family.parent` marker, and wrap the new per-child key under `_family_cipher(family_id)`
  instead of the master. When `family_id` is `None`: unchanged (master-wrapped, no marker)
  — the legacy path for PR #95 child keys.
- `_child_cipher(child_id)` — unwrap the child key under `_child_key_wrapping_cipher(child_id)`
  (family key when the marker is present, else master). Idempotent guard: still
  `DecryptionError(_CHILD_KEY_FILE)` if the child key file itself is missing.
- `create_story(..., child_id=None, family_id=None)` — new `family_id` kwarg passed
  through to `_init_child_key`.
- `iter_story_ids` — also skip `_FAMILIES_DIR` (already skips `_CHILDREN_DIR`).

### 2. `access/guarded_store.py`
`create_story_for_child` resolves the child's family from the registry
(`registry.get_child(child_id).family_id`) and passes `family_id` to `create_story`.
Authorization is unchanged (still consent-gated, authorizes before touching the store).

### 3. `people/erasure.py`
`erase_family` calls `store.shred_family_key(family_id)` **first** — the one-op
family-wide content shred — then runs the existing cascade over `erase_child` (each shreds
its own child key + deletes stories + backup-log + registry records) and
`registry.remove_family`. Verification gains: after erasure the family key is gone.
`erase_child` is unchanged.

## The crypto-shred proof (test)

A cipher-backed store + a registry with one family and **two children**, each with **≥1
child-scoped story** created via `create_story(child_id=…, family_id=…)`. Before erasure,
capture one child's wrapped **child key** bytes (a real backup fragment). `erase_family`.
Assert:
- **(a)** the `_family_key.wrapped` for the family is gone;
- **(b)** both children's stories are gone (rmtree + KC-1 verify) and the registry has no
  family/children;
- **(c)** restoring the captured child-key fragment (`_child_key.wrapped` + the
  `_family.parent` marker) and calling `_child_cipher(child_id)` **fails closed** — the
  per-family key needed to unwrap the child key is destroyed (crypto-shred proven, one
  level up from PR #95's story-level proof);
- **(d)** the receipt (→ backup-purge log) carries the family's children + story ids.

## Master-rotation nuance

Per-child keys now wrap under the family key, so master rotation rotates **family** keys
via `rewrap_family`. `rewrap_child` stays for **legacy** (PR #95) master-wrapped child
keys and **no-ops when the `_family.parent` marker is present** (that key rotates through
its family, not the master). The full mixed-rotation orchestration helper (walk all
families + legacy children) stays a deferred follow-up.

## Backward compatibility

- Legacy PR #95 child keys (no `_family.parent`, wrapped under master) still resolve via
  the marker-absent fallback in `_child_key_wrapping_cipher`.
- Non-child stories, plaintext stores, and existing envelope/rotation/erasure tests are
  unaffected.
- Registry records stay plaintext (still a follow-up).

## Constraints held

- Synthetic identities only; no DOB/names/account email; registry plaintext (out of slice).
- Fails closed on any missing/un-unwrappable key (`DecryptionError`, single-arg label,
  no key/content).
- `family_id`/`child_id` validated (`_validate_story_id`) before path building.
- Every new function ships a test; tests mirror source layout; no real child data.

## Follow-ups (not this slice)
- Encrypt the registry records under the child key (completes §3 for registry data).
- Mixed master-rotation helper (family keys + legacy per-child/per-story keys in one pass).
- The Minor items carried from PR #95 (redundant wrapping-cipher call; empty
  `_children/<id>/` residue after shred).
