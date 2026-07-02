# Kathai Chithiram — State of Play

**As of:** 2026-07-02 · **Owner:** WeGoFwd2020 · **Purpose:** one place to see what is
built, what is left, and **who each remaining item is blocked on** — so the next move is
never ambiguous.

> This is a status snapshot, not a spec. The authoritative detail lives in the ADRs,
> `docs/DPIA.md`, `PRIVACY.md`, and the `TICKETS/`. Update it when a track changes state.

**Final status (2026-07-02):** the next-session queue is fully closed (4/4), all merged to
`main` (PRs #37–#40); the tree is green — **345 tests pass, ruff + mypy clean**. **No
engineering-ownable work remains open.** Everything left to reach launch is
external/operational (DPO/counsel, professional collaborator, ops provisioning), each with
a decision-ready artifact and a named owner below.

## TL;DR

The **product pipeline is built and green** (345 tests): a parent's story becomes a
validated, safety-checked, human-review-gated draft animation, behind a provider-agnostic
LLM seam, with encryption at rest and verifiable deletion. **There is essentially no
engineering-ownable work left**: the two open tracks (M1 progress engine, KC-11 access
control) are built to the line where the next step is a *person* or *deployment*, and the
one remaining pick-up-able item (KC-10 envelope keys) is now built too. What blocks launch
is external: a professional collaborator, a DPO sign-off, and operational provisioning.

## What is built (done)

- **Core pipeline** — scene-script contract + validation, generation behind the
  `wegofwd-llm` seam (Anthropic provider), both reference renderers consume the contract,
  parent intake with consent capture. `kc intake` / `kc generate` / `kc review` /
  `kc assign` CLI.
- **Production hardening (KC-1…KC-9)** — verifiable hard-delete (KC-1), identifier
  minimization before the LLM (KC-2), scene-script validation (KC-3), render-time seizure/
  flash safety (KC-4), **encryption at rest** (KC-5), **dedicated ZDR/no-training
  credential** (KC-6), **review→approve→deliver** gate (KC-7), **parent privacy notice** +
  versioned consent (KC-8), **DPIA drafted** (KC-9).
- **Access control (KC-11, ADR-004)** — code-complete: deny-by-default enforcement wired
  through every app flow (CLI/intake/review/progress), a durable log-safe audit trail,
  `kc assign` for reviewer/therapist grants, all role-scoped to the actor model.
- **Envelope encryption (KC-10)** — each story is encrypted under its own data key,
  stored wrapped by the master; hard-delete crypto-shreds the wrapped key (undecryptable
  even from a stale backup), and `rewrap_story` rotates the master without re-encrypting
  bodies. Backward-compatible with legacy KC-5 stores.
- **Decision-ready artifacts for the external blockers** — `docs/R10_DEPLOYMENT_BOUNDARY.md`
  (the boundary + acceptance checklist that drops R10 → Low), `docs/M1_OUTREACH_SEND_READY.md`
  (send-ready collaborator email, three fill-ins, *not sent*), and `docs/DPO_REVIEW_PACKAGE.md`
  (one entry point for DPO/counsel sign-off, with the open gaps named). These don't unblock
  the work themselves — they make each external step actionable.

## Open tracks — status and who they are blocked on

### 1. M1 — per-child progress → therapist-suggested premises

- **Built:** ADR-002 (stance, Accepted) + ADR-003 (engine design, Accepted). The
  `ProgressPolicy` schema and the deterministic `measure`/`suggest` interpreter are landed,
  **default-free and gated off** — the engine has no thresholds and cannot run until a
  policy is supplied. Collaborator brief is at v0.2.
- **Blocked on — a professional collaborator (therapist/OT):** authoring the real
  `ProgressPolicy` — the window K, thresholds, and trend definitions (ADR-002 D7.1), and
  the framing/copy sign-off (D7.4). *Engineering cannot pick these — they are clinical
  judgment.*
- **Also blocked on — DPO/counsel:** the progress-profiling DPIA touchpoint (D7.6).
- **Then (small, engineering-ownable):** wire the signed policy into the interpreter and to
  `record_suggestion`. Cannot start until the gate opens.

### 2. KC-11 — operator access control (DPIA R10)

- **Built:** everything in code (ADR-004, PRs #28–#34).
- **Blocked on — a deployment boundary (operational):** R10's residual drops from Medium to
  Low only where an operator cannot bypass the app via direct filesystem access to the store
  (a network boundary / no shared filesystem). In-app enforcement is done; the boundary is
  infrastructure, not code. The required boundary — properties, threat-model delta, and the
  §5 acceptance checklist for reassessing R10 → Low — is now specified in
  `docs/R10_DEPLOYMENT_BOUNDARY.md`.

### 3. KC-10 — envelope / per-story keys (crypto-shredding)

- **Built (2026-07-02).** Per-story data keys wrapped by the master; hard-delete
  crypto-shreds the wrapped key (R5), and `rewrap_story` rotates the master without
  re-encrypting bodies (R3). Backward-compatible with legacy KC-5 stores; documented
  rotation procedure in `TICKETS/KC-10-envelope-per-story-keys.md`.
- **Blocked on — nobody:** done. The only operational follow-on is provisioning the
  secret manager that holds `KC_STORAGE_KEY` (already tracked as a launch precondition).

## Launch preconditions (from `docs/DPIA.md` §5) — the critical path

The DPIA is **Draft v0.1, not signed off**. Before any EU/UK launch, all of:

| # | Precondition | Blocked on | Kind |
|---|--------------|-----------|------|
| 1 | DPO / counsel review + sign-off of the DPIA and parent notice | **DPO / counsel** | external |
| 2 | Confirm the Anthropic org is genuinely no-training / ZDR (R2) | **Owner (ops)** | operational |
| 3 | `KC_STORAGE_KEY` in a secret manager, separate from data/backups, with rotation (R3) | **Owner (ops)** | operational |
| 4 | Deployment boundary that removes the local filesystem bypass (R10) — spec + checklist in `docs/R10_DEPLOYMENT_BOUNDARY.md` | **Owner (ops)** | operational |
| 5 | Progress-engine DPIA touchpoint, if the engine is enabled (R8) | **Collaborator + DPO** | external |

Code side of the two highest-inherent risks (R2 ZDR, R3 at-rest) is already done; what
remains on the critical path is human and operational.

## Who owns the next move

- **WeGoFwd2020 (owner):** engage the professional collaborator; commission the DPO/counsel
  review; provision the secret manager, confirm the ZDR org, and stand up a deployment
  boundary.
- **Professional collaborator (therapist/OT):** author the `ProgressPolicy` and sign off the
  framing (unblocks M1).
- **DPO / counsel:** sign off the DPIA (unblocks launch) and the progress-profiling touchpoint.
- **Engineering:** KC-10 is now built; nothing else is pick-up-able — everything waits on
  the above. When the M1 gate opens, a small policy-wiring task remains.

## Next-session task queue (pinned 2026-07-01, all cleared 2026-07-02)

**All four queued items are done.** What now remains is entirely external/operational
(a DPO/counsel sign-off, a professional collaborator, and ops provisioning) plus, when
the M1 gate opens, a small policy-wiring task. The four completed items are kept below
for the audit trail.

1. ~~**Build KC-10 — envelope / per-story keys (crypto-shredding).**~~ **Done 2026-07-02.**
   Per-story data keys wrapped by the master; crypto-shred on delete; incremental
   master-key rotation. Spec + rotation procedure: `TICKETS/KC-10-envelope-per-story-keys.md`.
2. ~~**Write the R10 deployment-boundary design note.**~~ **Done 2026-07-02.**
   `docs/R10_DEPLOYMENT_BOUNDARY.md`: the gap, the target properties, the threat-model
   delta (before/after), and a §5 acceptance checklist for reassessing R10 Medium → Low.
   Linked from DPIA R10 + §5 precondition 4. Unblocks the ops conversation.
3. ~~**Prepare the M1 collaborator outreach.**~~ **Drafted + copy approved 2026-07-02.**
   `docs/M1_OUTREACH_SEND_READY.md` — finalized pediatric-OT / advisory / cold-email
   message; **owner approved the copy 2026-07-02**. **Still not sent** — sending is an
   operational step the owner takes from `wegofwd2020@gmail.com` once a recipient
   (name + email) and signature are supplied. Outward-facing; no auto-send.
4. ~~**Assemble the DPO/counsel DPIA review package.**~~ **Done 2026-07-02.**
   `docs/DPO_REVIEW_PACKAGE.md` — one entry point: enclosed-docs inventory, processing
   at-a-glance, the five sign-off asks, honestly-surfaced open gaps (international
   transfer, controller/processor DPA, Art. 22, DSAR process, retention justification),
   and a sign-off record. Prepares for, does not substitute, legal review.

## Human-in-the-loop stays on

Per CLAUDE.md, the human review gate (`kc review`) remains mandatory before any output
reaches a child until automated safety enforcement is independently tested — regardless of
the tracks above.
