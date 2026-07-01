# KC-11 — Operator access control for stored child content

**Labels:** P1, privacy, security
**Status:** 🔨 In progress — DPIA risk **R10** (Medium residual). Design decided in **ADR-004** (Accepted): full technical enforcement at the store boundary, identity behind a swappable seam. **Model landed** (PR #29: `access/` — principal, policy, identity seam, audit) and **enforcement boundary landed** (`GuardedStore` + store grants, deny-by-default, audited, hard-delete sweeps `grants.json`). **Remaining:** migrate the callers (CLI/intake/review/progress) to hold a `GuardedStore` — until then the guard is built but not wired in, so R10's residual stays Medium.
**Refs:** `docs/ADR_004_operator_access_control.md`; `docs/DPIA.md` §4 (R10), §5 (launch precondition 4); PRIVACY.md §7

## Why
The store keeps a family's story content — `story.txt`, `scene_script.json`,
`intake.json`, `feedback.jsonl`, rendered `media/` — under `<store-root>/<story_id>/`.
Today, access is scoped to the owning session **by convention only**: anyone who can
reach the store root (an operator, an admin, a backup restorer) can read every
child's content. At-rest encryption (KC-5) protects a *stolen disk*, but a running
system decrypts for anyone holding `KC_STORAGE_KEY`, so it does not bound *operator
browsing*. The DPIA records R10 as **Medium residual** with "enforcement beyond
convention is an infra control, not yet built," and §5 lists deciding it as a launch
precondition. It is the only tracked risk with no ticket — this captures the intent.

## Acceptance criteria
- A written decision for the intended deployment: **technical enforcement** vs.
  **documented operational limit** (with compensating controls: access logging,
  least-privilege operator accounts, break-glass procedure). Recorded in `docs/`
  (DPIA §4/§5 updated) so R10's residual is justified, not just asserted.
- If technical enforcement is chosen: access to a story's artifacts is scoped to an
  authenticated principal (the owning family and their assigned reviewer/therapist),
  denied by default; a store read by an unauthorized principal fails closed with a
  domain-specific error, never returns content.
- Any access to child content is **audit-logged** — who, which `story_id`, when —
  with no raw story text, captions, or names in the log (PRIVACY.md §6 log-safety).
- The design states how it composes with KC-5 (encryption) and KC-1 (hard-delete):
  access records for a deleted story are swept or provably de-identified.

## Implementation notes
- Largely an **infra/deployment** control (identity, network boundary, object-store
  ACLs), so the shape depends on where this runs; the code-side seam is an
  authorization check at the `StoryArtifactStore` boundary plus an audit-log hook —
  keep it provider-agnostic like the other seams.
- Does **not** require a network boundary to start: even the local CLI can gain an
  operator-identity + audit-log seam and a documented least-privilege posture.
- OpenSpec docstrings; explicit domain errors (e.g. an `AccessDeniedError`), no bare
  `except`; fail closed.
- Tests with mock stories: an unauthorized principal is denied and gets no bytes; an
  authorized read is permitted and produces an audit record carrying no story text.
- Out of scope: the DPO/counsel sign-off itself and the operational provisioning
  (accounts, secret manager) — this ticket decides and builds the enforcement seam;
  the human/ops gate is separate (DPIA §6).
