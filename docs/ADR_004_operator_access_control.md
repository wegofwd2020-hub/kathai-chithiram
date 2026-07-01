# ADR-004 — Operator access control: full technical enforcement at the store boundary, identity behind a swappable seam

**Date:** 2026-07-01
**Status:** Accepted (2026-07-01)
**Branch at decision:** main

---

## Context

The store persists a family's story content — `story.txt`, `scene_script.json`,
`intake.json`, `feedback.jsonl`, rendered `media/` — under `<store-root>/<story_id>/`.
Today access is scoped to the owning session **by convention only**: the
`StoryArtifactStore` API is keyed by `story_id` and carries **no notion of a caller,
principal, or authorization** (a scan of `storage/` finds none). Anyone who can
construct the store object — an operator, an admin, a backup restorer — can read every
child's content.

`docs/DPIA.md` records this as **R10** (operator browses story content): **Medium
inherent, Medium residual**, "enforcement beyond convention is an infra control, not
yet built," and §5 lists deciding it as a launch precondition. `KC-11` captures it —
the only tracked DPIA risk without a ticket until now. At-rest encryption (KC-5)
protects a *stolen disk*, but a running system decrypts for anyone holding
`KC_STORAGE_KEY`, so it does not bound a *live operator*. R10 is a distinct control.

`KC-11` poses a fork: **technical enforcement** vs. a **documented operational limit**.
The product is presently a local-CLI prototype with no identity layer, accounts, or
network boundary, so the conservative, precedent-matching move (ADR-001/002/003:
"build the seam, gate the deployment-dependent part") would be a fail-closed seam with
a single local principal and enforcement deferred. **This ADR instead records the
decision to build full technical enforcement now** — the complete authorization model,
enforced at the store boundary, with real deny-by-default — because R10 concerns a
*vulnerable child's* content and the team has chosen to close it with code rather than
a documented limit. The honest cost (below) is that we introduce an identity/authz
model ahead of the deployment that will ultimately define authentication; we contain
that cost by making **identity a provider-agnostic seam** while the **authorization
model is real and complete**.

## Decision

**Decision 1 — Every store access to child content requires a `Principal`; denied by
default.**
Enforcement lives in a thin **`GuardedStore`** that binds one authenticated
`Principal` to the underlying `StoryArtifactStore` and exposes the content-bearing
operations (`read_scene_script`, `read_session_feedback`, `read_progress_suggestions`,
`read_intake_record`, `read_review_record`, `read_media`, `media_paths`, the
corresponding writes/appends, `create_story`, and `mark_delivered`) — each
**authorizes before it delegates**. (This is a refinement of the original phrasing
"the store methods take a `Principal`": putting the guard in a wrapper keeps the
persistence layer a pure data store and avoids rewriting it and its whole test suite,
for the same boundary guarantee.) No principal with an authorized relationship to the
story — or a story with no recorded owner — yields **nothing**: the call fails closed
with a domain-specific `AccessDeniedError` (log-safe: principal id + `story_id` +
action, never content), before any read, decrypt, or write. Deny-by-default: access is
granted only by an explicit rule, never by omission. Cross-story enumeration
(`iter_story_ids`, `artifact_paths`) stays a system/operational primitive on the raw
store, outside the per-story model — an operator-level control, not a per-principal one.

**Decision 2 — A small, explicit role model bound to a story, aligned to the actor
model.**
A story has one **owner** (the family/parent who submitted it) and zero or more
**assignments** granting a role to another principal. Roles are
`family_owner`, `reviewer`, and `therapist`, mirroring `BRAND.md` §7 (premise/goal
therapist-owned, feedback parent-owned) and the existing review (KC-7) and progress
(ADR-002) reviewers. An `AccessPolicy` maps `(principal, story, action) → allow/deny`
from the story's owner + assignments. The initial action grants (refined with the
professional collaborator and in review, Decision 7 below):
- `family_owner` — full access to their own story's artifacts and media.
- `reviewer` — read scene script + media + intake consent; write the review decision
  (the KC-7 gate). No feedback/progress access.
- `therapist` — read the evidence view + feedback; record suggestion decisions
  (ADR-002). Read scene script/media as needed for judgement.
- no relationship — denied.

**Decision 3 — Identity is a provider-agnostic seam; only the identity *source* is
deployment-dependent.**
An `IdentityProvider` protocol (like `LLMProvider` for the LLM and `StorageCipher` for
crypto) authenticates a credential and returns a `Principal` (an opaque id + role
context), or fails closed. A concrete **local** provider ships now for the prototype
(principals from configuration, not names); a networked identity provider (e.g. OIDC)
is a future concrete behind the *same* seam. This is the containment for the trade-off
in Context: the authorization model (Decisions 1/2) is complete and enforced today; the
part that genuinely needs a deployment — real cross-machine authentication — is the
*provider*, swappable without touching the policy.

**Decision 4 — Ownership and assignments live in store metadata, minimized and swept.**
`create_story` records the owning principal id; an explicit assignment operation grants
a `reviewer`/`therapist` role for a story. These are **opaque principal ids**, never
names (a name is a render-time substitution only — CLAUDE.md), kept in the story's
metadata so the existing verifiable hard-delete (KC-1) sweeps them with everything
else. A test asserts the ownership/assignment records are removed on delete.

**Decision 5 — Every content access is audit-logged, and the log is log-safe by
construction.**
Each authorized content access appends an audit record — principal id, `story_id`,
action, timestamp — with **no** story text, captions, or names (PRIVACY.md §6). Because
records carry only opaque ids, an audit log is safe to retain centrally for
"detect-operator-browsing" value even after a story is hard-deleted (it names no
content). Denied attempts are logged too (the security signal). The concrete sink
(local file now; a tamper-evident central log later) sits behind a small audit seam.

**Decision 6 — Authorization composes with encryption and hard-delete; it replaces
neither.**
KC-5 (encryption) bounds a *stolen disk*; this ADR bounds a *live operator*; both are
required and orthogonal. Authorization runs **before** decryption, so an unauthorized
principal never causes plaintext to be produced. Hard-delete (KC-1) removes a story's
ownership/assignment metadata; audit records carry only ids and may be retained or
swept per the retention policy without exposing content.

**Decision 7 — Fail closed, explicit errors, and the grants are reviewed, not
engineer-final.**
No bare `except`; a denied or unauthenticated access raises `AccessDeniedError` and
returns no bytes (WeGoFwd standards). The *mechanism* (principal, deny-by-default,
enforcement point, audit) is engineering's; the exact **action grants per role**
(Decision 2) are reviewed — the reviewer/therapist boundaries touch the same
confidentiality questions ADR-001 D4.3 and ADR-002 D5 flag, so they are confirmed in
review (and, for the therapist/feedback boundary, with the ADR-002 collaborator) rather
than frozen here.

## Consequences

### Positive

- R10 gains **real code enforcement**, not a documented limit: the store denies by
  default and cannot hand a child's content to an unauthorized principal, closing the
  gap KC-5 leaves for a live operator.
- The authorization model is complete and testable now (mock principals, mock stories),
  independent of any deployment; the audit trail exists from day one.
- The role model reuses the actor model (BRAND §7) and the existing reviewer/therapist
  concepts, so it slots into KC-7 review and ADR-002 progress rather than duplicating.
- The `IdentityProvider` seam keeps the deployment-dependent part swappable, so a real
  IdP later does not disturb the policy or the store boundary.

### Negative

- This is the seam-gated alternative's cost, taken on deliberately: we build an
  identity/authz model **ahead of** the deployment that will define authentication, so
  some abstractions (credential shape, session lifetime, multi-user concurrency) may
  need revision when a real IdP lands. The `IdentityProvider` seam bounds — but does not
  eliminate — that risk.
- Enforcement is now on in the app's flows (CLI + intake/review) with a durable audit
  trail, but a **local** operator can still bypass it via direct filesystem access to
  the store, so R10's residual stays Medium until a deployment boundary removes that
  bypass. All app paths (CLI, intake, review, progress/feedback) now route through the
  guard; a deployment boundary is the only remaining item for R10.
- A local concrete identity provider is genuine enforcement for a *single-machine*
  deployment only; it is not a substitute for real authentication across a network,
  which remains a deployment precondition.

### Neutral

- The concrete audit sink and credential store are deployment choices; this ADR fixes
  the seams and the log-safety invariant, not the backend.
- The per-role action grants (Decision 2) are an initial cut, expected to be refined in
  review and with the collaborator (Decision 7).

## Alternatives considered

- **Fail-closed seam with a single local principal, enforcement gated (the ADR-001/002/
  003 pattern)** — considered and **not** chosen for this decision: it would leave R10
  as a Medium residual with only a stub principal, and the team chose to close R10 with
  a complete, enforced authorization model now. (Recorded because it remains the
  fallback if the churn proves premature.)
- **Documented operational limit only** — rejected: no code enforcement and no audit
  hook; the store would still hand content to anyone who holds it, leaving R10's
  residual resting entirely on operator discipline.
- **Reuse `KC_STORAGE_KEY` as the access boundary** — rejected: encryption bounds a
  stolen disk, not a live operator (Decision 6); one key for "can decrypt" and "is
  authorized" conflates two controls and defeats per-principal scoping and audit.
- **A general RBAC/policy engine** — rejected as over-built: three roles bound to a
  story owner + assignments cover the actor model; a general engine adds surface
  without a requirement.

## Migration / rollout

- **Access-control model (landed):** `access/` holds `Principal`, `Role`, `Action`,
  `StoryGrants`, `AccessPolicy`, the `IdentityProvider` protocol + a concrete local
  provider, and the audit seam; `errors.AccessDeniedError` is added. *(PR #29.)*
- **Enforcement boundary (landed):** a `GuardedStore` binds a principal to the store
  and enforces deny-by-default before any read/decrypt/write, auditing each
  allow/deny; ownership is recorded on `create_story`, an `assign_role` operation adds
  reviewer/therapist grants, and the grants live in a `grants.json` under the story dir
  that the verifiable hard-delete sweeps (test asserts). The persistence
  `StoryArtifactStore` is unchanged except for the grants read/write.
- **Callers (landed):** the intake and review services type against a `StoryStore`
  protocol that both the raw store and `GuardedStore` satisfy, and the CLI now binds a
  principal (from `KC_PRINCIPAL`, defaulting to a single local operator) and passes a
  `GuardedStore` — so `kc generate`/`kc intake` establish ownership and `kc review`
  runs authorized. Deny-by-default is now enforced in the app's own flows (a test shows
  an unrelated principal is refused). *(PR for this change.)*
- **Audit trail (landed):** the CLI wires a durable `JsonlAuditSink`
  (`<store-root>/access_audit.jsonl`, log-safe opaque ids), so every allowed and denied
  access is persisted across invocations (a test shows both an ownership-bootstrap
  ALLOW and a cross-principal DENY on disk).
- **Role assignment (landed):** `kc assign <story> --principal <id> --role
  reviewer|therapist` lets an owner grant a scoped role; a granted reviewer can then
  read the draft a stranger cannot (end-to-end test).
- **Progress/feedback path (landed):** the per-story feedback and suggestion functions
  accept the `StoryStore` protocol, so passing a `GuardedStore` makes them
  deny-by-default and role-scoped (owner captures feedback; therapist reads it and
  decides on suggestions). Cross-story aggregation (`build_goal_evidence` /
  `iter_story_ids`) stays on the raw store as a privileged system operation, outside
  the per-story model.
- **Remaining (not code):** **R10's residual stays Medium** until a *deployment*
  boundary removes the local bypass — an operator on the single machine still has direct
  filesystem access to the store (bounded only by KC-5 encryption + OS permissions), so
  in-app enforcement fully pays off only where operators cannot reach the files directly.
- **Tests (mock stories, no real child data):** an unauthorized principal is denied and
  receives no bytes; each role gets exactly its granted actions and nothing more;
  authorized access emits a log-safe audit record; hard-delete removes
  ownership/assignment records; a denied decrypt never produces plaintext.
- **Docs:** update `docs/DPIA.md` R10 (residual reassessed once enforced) and §5
  precondition 4; note in PRIVACY.md §7 that access is technically enforced, not
  conventional; `KC-11` tracks implementation status.
- **Deferred (deployment):** a networked `IdentityProvider`, real credential/session
  management, and a tamper-evident central audit sink land behind the seams when a
  network boundary exists.

**Accepted 2026-07-01:** the access-control model (PR #29) and the `GuardedStore`
enforcement boundary — principal + deny-by-default at the store boundary + audit +
hard-delete coverage of the grants — have landed, the condition this ADR set for
acceptance. **Acceptance records that the design is realized and the boundary exists;
it is not "enforcement is on."** The app's own flows still reach the raw store until the
caller migration (Migration §"Callers, remaining rollout") lands, so `docs/DPIA.md`
R10's residual **stays Medium** until then. A **local** identity provider is genuine
enforcement for a single-machine deployment; it is **not** a substitute for network
authentication, which stays a launch precondition. Do not read acceptance as clearance
for a multi-user or networked launch.
