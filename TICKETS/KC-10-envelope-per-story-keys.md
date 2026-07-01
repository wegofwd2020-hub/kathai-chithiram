# KC-10 — Envelope encryption with per-story keys (crypto-shredding on delete)

**Labels:** P2, privacy, security, enhancement
**Status:** ⏳ Open — enhancement to KC-5 (noted there as a future item).
**Refs:** `docs/DPIA.md` §4 (R3, R5); `storage/crypto.py`; TICKETS/KC-5; PRIVACY.md §5, §7

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
