# KC-2 — Identifier minimization before LLM calls + provider no-training config

**Labels:** P0, privacy, security
**Refs:** PRIVACY.md §6

## Acceptance criteria
- Child's real name is replaced with a token (`CHILD`) before any `wegofwd-llm` call and reinserted only at render time.
- No raw story text or real name written to plaintext logs.
- The provider config used (no-training / zero-retention) is recorded per request.

## Implementation notes
- Pseudonymization util + test with a mock story containing a name; assert the outbound payload contains no name.
