# KC-5 — Encryption at rest for story text, scene scripts, and media

**Labels:** P0, privacy, security
**Refs:** PRIVACY.md §7, §9; `storage/store.py` (NOTE at lines 18–21)

## Why
The reference store writes every artifact as plaintext on the filesystem —
`story.txt`, `scene_script.json`, `intake.json`, `feedback.jsonl`, and rendered
`media/*.mp4` all sit unencrypted under `<store-root>/<story_id>/`. PRIVACY.md §7
requires story text and animations to be encrypted at rest. `store.py` already
flags this as a control that "must be added before any production use." This is
the highest-risk unshipped security obligation.

## Acceptance criteria
- All at-rest artifacts containing personal data are encrypted: `story.txt`,
  `scene_script.json`, `intake.json`, `feedback.jsonl`, and `media/` output.
  `_meta.json` may stay cleartext (no story content) but must not leak the child
  token or story text.
- Encryption is transparent to callers: `StoryStore` read/write APIs return/accept
  plaintext; ciphertext never crosses the store boundary.
- Key management is explicit and documented: keys are loaded from configuration
  (env/secret store), never committed, and are distinct from the LLM provider key.
- Hard-delete (KC-1) still fully removes ciphertext + any key material scoped to
  the deleted story; no recoverable plaintext or key remains.
- Decryption failure raises a domain-specific error (e.g. `DecryptionError`) with
  context — never silently returns partial/garbled data or falls back to plaintext.

## Implementation notes
- Add an encryption seam in `storage/` (e.g. `storage/crypto.py`) wrapping the
  filesystem read/write in `store.py`; keep it provider-agnostic like `wegofwd-llm`.
- Prefer authenticated encryption (AES-GCM / libsodium secretbox). Consider a
  per-story data key wrapped by a master key (envelope encryption) so per-story
  hard-delete can drop the wrapped key.
- OpenSpec docstrings; explicit errors, no bare `except`.
- Tests with mock stories: assert on-disk bytes are not plaintext (story text /
  child token absent from raw files), round-trip decrypt matches input, and
  tampered ciphertext raises `DecryptionError`.
- Document the "in transit" half of §7 separately if/when a network boundary
  exists — this ticket covers at-rest only.
