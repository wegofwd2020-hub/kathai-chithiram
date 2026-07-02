# KC-10 — Envelope encryption with per-story keys (crypto-shredding on delete)

**Labels:** P2, privacy, security, enhancement
**Status:** ✅ Built — envelope encryption with per-story data keys, crypto-shred on
delete, and incremental master-key rotation are implemented and tested.
**Refs:** `docs/DPIA.md` §4 (R3, R5); `storage/crypto.py`; `storage/store.py`;
TICKETS/KC-5; PRIVACY.md §5, §7

## Why
KC-5 encrypts every artifact with a single master key (`KC_STORAGE_KEY`). That
protects a stolen disk (R3), but it has two limits an envelope scheme removes:

- **Crypto-shredding on delete (R5).** Today hard-delete (KC-1) removes the
  ciphertext files. With one master key, "delete" depends on the filesystem/backup
  layer actually dropping every byte. If each story had its own data key wrapped by
  the master, destroying that one wrapped key would render the story
  **unrecoverable even from a stale backup** — a stronger, verifiable delete for
  special-category child data.
- **Blast radius / rotation.** Rotating or compromising the single master key
  affects every story at once; per-story data keys localize exposure and make
  rotation incremental.

This is an enhancement, not a gap: KC-5 already satisfies the at-rest obligation.
It raises the assurance of R3/R5 rather than closing an unmet control.

## Acceptance criteria
- Each story is encrypted under a **per-story data key**; the data key is stored
  **wrapped** by the master key (envelope encryption). Artifact contents never use
  the master key directly.
- Hard-delete (KC-1) destroys the wrapped per-story key as part of the sweep, and a
  test asserts that after delete the artifacts are **undecryptable** even if the
  raw ciphertext bytes are recovered (crypto-shred).
- Backward compatible: existing single-key stores still read; a documented migration
  path re-wraps existing stories, or old and new layouts coexist behind the cipher
  seam. No plaintext window during migration.
- Master-key rotation re-wraps per-story keys **without** re-encrypting artifact
  bodies; documented rotation procedure.
- Decryption failures still fail closed with `DecryptionError` (never plaintext
  fallback); a missing/again-unwrappable per-story key is distinguishable in logs
  (safe identifiers only, no key material).

## Implementation notes
- Extend the existing `StorageCipher` seam in `storage/crypto.py` rather than
  replacing it; keep it provider-agnostic. A per-story key file (wrapped) lives in
  the story dir alongside the artifacts so hard-delete already sweeps its directory.
- Reuse AES-256-GCM for both the data-key wrapping and the artifact bodies; fresh
  random nonces throughout.
- OpenSpec docstrings; explicit errors, no bare `except`.
- Tests with mock stories: round-trip under per-story keys; delete → artifacts
  undecryptable; rotation re-wraps without touching bodies; tampered wrapped key
  raises `DecryptionError`.
- Update `docs/DPIA.md` R3/R5 residual notes once built (crypto-shred is realized).

## What was built
- `storage/crypto.py`: `generate_data_key`, `wrap_data_key`, `unwrap_data_key`
  (AES-256-GCM wrapping; `unwrap` fails closed with `DecryptionError`).
- `storage/store.py`: `create_story` generates a per-story data key and writes it
  wrapped to `_data_key.wrapped` in the story dir; all artifact bodies are sealed
  under the per-story cipher (`_story_cipher`), never the master directly. A story
  with no wrapped-key file (legacy KC-5) transparently falls back to the master —
  old and new layouts coexist with no plaintext window.
- Crypto-shred is automatic: hard-delete (KC-1) already sweeps the story dir, so
  the only wrapped copy of the data key is destroyed on delete.
- `StoryArtifactStore.rewrap_story(story_id, *, new_master)` re-wraps a story's data
  key under a new master **without** re-encrypting bodies (see procedure below).
- Tests: `tests/kathai_chithiram/storage/test_store_envelope.py` and the KC-10
  cases in `test_crypto.py`.

## Master-key rotation procedure
The master key (`KC_STORAGE_KEY`) can be rotated without touching artifact bodies:

1. Provision the new master key alongside the current one (both available to the
   rotation job — e.g. `KC_STORAGE_KEY` and a `KC_STORAGE_KEY_NEXT`).
2. Build a store bound to the **current** master; build an `AesGcmCipher` for the
   **new** master.
3. For every `story_id` in `store.iter_story_ids()`, call
   `store.rewrap_story(story_id, new_master=<new cipher>)`. Each call unwraps the
   per-story data key with the current master and re-wraps it under the new one;
   the artifact bodies are untouched. (Legacy stories with no wrapped key are
   skipped — migrate those by re-encrypting bodies if needed.)
4. Once every story is re-wrapped, promote the new key to `KC_STORAGE_KEY` and
   retire the old one. Reads now succeed only under the new master.

Rotation is incremental and interruptible: a story already re-wrapped reads under
the new master; one not yet re-wrapped still reads under the old master, so both
keys must remain available until the sweep completes.
