# Kathai Chithiram — State of Play

**As of:** 2026-07-02 · **Owner:** WeGoFwd2020 · **Purpose:** one place to see what is
built, what is left, and **who each remaining item is blocked on** — so the next move is
never ambiguous.

> This is a status snapshot, not a spec. The authoritative detail lives in the ADRs,
> `docs/DPIA.md`, `PRIVACY.md`, and the `TICKETS/`. Update it when a track changes state.

**Compliance status (2026-07-02):** the next-session queue is fully closed (4/4), all merged
to `main` (PRs #37–#40). **No engineering-ownable *launch-blocker* work remains open** —
everything left to reach launch is external/operational (DPO/counsel, professional
collaborator, ops provisioning), each with a decision-ready artifact and a named owner below.

**Rendering/offline status (2026-07-02):** a follow-on session hardened the **render and
authoring** side (PRs #47–#59, all merged): in-process narration with **per-character
voices** + sound-effects (mixed into the mp4), rendered scene transitions, an accessibility
caption sidecar (`.srt`/`.vtt`), **offline generation** (`kc generate`/`kc intake --offline`
— story→video with no LLM/API key), and content-aware scene art (per-scene inferred setting,
backdrop, props, character pose/expression, reading-paced duration). Tree is green — **565
tests pass, ruff + mypy clean** (incl. the M1 policy wire-up and the `kc author` story
template below). The matplotlib reference renderer (`generate_animation.py`)
carries these; the Blender v2 renderer is intentionally left on the older hard-cut/generic
path (a heavier bpy lift, lower value than the default matplotlib flow).

## TL;DR

The **product pipeline is built and green** (565 tests): a parent's story becomes a
validated, safety-checked, human-review-gated draft animation, behind a provider-agnostic
LLM seam, with encryption at rest and verifiable deletion — and now renders with narration,
sound, transitions, captions, and content-aware art, drivable end-to-end offline (no key)
for manual verification. **There is essentially no engineering-ownable launch-blocker work
left**: the two open tracks (M1 progress engine, KC-11 access control) are built to the line
where the next step is a *person* or *deployment*, and KC-10 envelope keys is built too. What
blocks launch is external: a professional collaborator, a DPO sign-off, and operational
provisioning.

## What is built (done)

- **Core pipeline** — scene-script contract + validation, generation behind the
  `wegofwd-llm` seam (Anthropic provider), both reference renderers consume the contract,
  parent intake with consent capture. `kc intake` / `kc generate` / `kc review` /
  `kc assign` / `kc progress` / `kc author` / **`kc delete`** / **`kc retention-sweep`** CLI.
- **Erasure + retention are CLI-invokable** — `kc delete <story>` (owner-only, guarded +
  audited, verifiable KC-1 hard-delete + KC-10 crypto-shred, confirms unless `--yes`) and
  `kc retention-sweep` (purge undelivered older than the window; `--dry-run` reports only).
  The right-to-erasure the DPIA/PRIVACY reference is now user-invokable, not just a function.
- **Three ways to make a story** — `kc intake` (interactive, consented), `kc generate`
  (free text; `--offline` = no LLM/key), and **`kc author`** (a structured story template
  **from a file or via guided interactive prompts**, with `--dry-run` preview and shipped
  examples in `docs/examples/` → scene script, deterministic, no key — ADR-005 part a;
  `docs/STORY_TEMPLATE.md`). All three strip the child's name to the token (KC-2) and produce
  a review-gated draft.
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
- **Rendering & offline authoring (PRs #47–#57)** — the render/authoring side, all
  in-process and behind the scene-script contract:
  - *Audio* — an in-process narration voice (`--voice`, a local CLI-TTS seam) with optional
    **per-character voices** (`--character-voice ID=CMD` → a `VoiceCast`, each scene narrated
    in its foreground character's voice) and a local sound-effects bank (`--sfx`), each
    safety-guarded and mixed into the sealed mp4; the child's name/audio never leaves the
    machine (ADR-026 D1).
  - *Motion & accessibility* — scene transitions (fade/dissolve) actually rendered, and a
    caption sidecar (`kc … --captions srt|vtt`) written beside the `--out` video.
  - *Offline generation* — `kc generate --offline` / `kc intake --offline` turn a story into
    a video with **no LLM/API key** (deterministic local segmentation): sentences grouped
    into readable scenes, name still stripped (KC-2), contract-validated, review-gated.
  - *Content-aware art* — each scene infers its setting (bathroom / bedroom / kitchen /
    classroom / outdoors / calm), backdrop, props (brushing / mealtime / play / school /
    dressing), character pose/expression, and reading-paced duration from its content; the
    hand-authored demo keeps its bespoke frames. (Reference renderer: `generate_animation.py`.)
- **Decision-ready artifacts for the external blockers** — `docs/R10_DEPLOYMENT_BOUNDARY.md`
  (the boundary + acceptance checklist that drops R10 → Low), `docs/M1_OUTREACH_SEND_READY.md`
  (send-ready collaborator email, three fill-ins, *not sent*), and `docs/DPO_REVIEW_PACKAGE.md`
  (one entry point for DPO/counsel sign-off, with the open gaps named). These don't unblock
  the work themselves — they make each external step actionable.

## Open tracks — status and who they are blocked on

### 1. M1 — per-child progress → therapist-suggested premises

- **Built:** ADR-002 (stance, Accepted) + ADR-003 (engine design, Accepted). The
  `ProgressPolicy` schema, the deterministic `measure`/`suggest` interpreter, **and the
  enabling wire-up** are all landed (PR #61) — a policy *loader* (`load_policy`), the runner
  (`run_progress` = measure→suggest→record), and `kc progress <goal> --policy <file>
  --story <id>`. It stays **default-free and gated off**: no policy ships, `--policy` is
  required, recording a suggestion needs the therapist role (fails closed), and the
  suggestion is inert (a therapist decides). Collaborator brief is at v0.2.
- **The engineering track is now COMPLETE** — there is no code left to write; the engine
  runs the moment a reviewed policy file exists. What remains is the policy itself and its
  clearances:
- **Blocked on — a professional collaborator (therapist/OT):** authoring the real
  `ProgressPolicy` file — the window K, thresholds, and trend definitions (ADR-002 D7.1),
  and the framing/copy sign-off (D7.4). *Engineering cannot pick these — they are clinical
  judgment.*
- **Also blocked on — DPO/counsel:** the progress-profiling DPIA touchpoint (D7.6).

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

### 4. M2 — multi-user program platform (`docs/ADR_005_multi_user_program_platform.md`, Proposed)

- **Part (a) story template — BUILT (2026-07-02, `kc author`).** Adds no new personal
  data, so it was not gated.
- **Parts (b) family/child/therapist identity + accounts and (c) therapist programs +
  parent reporting — GATED, not started.** They add accounts + child DOB, which
  **materially expand special-category processing and contradict the current
  data-minimization stance** (`PRIVACY §3` / `DPIA §3` list DOB + accounts out of scope).
- **Blocked on — DPO/counsel + a DPIA revision (ADR-005 D7):** new data categories,
  lawful basis for accounts, notice/consent update, retention+erasure for account/DOB,
  DPO note — before any identity/DOB/account code. Engineering decisions already taken:
  the model slots behind the ADR-004 `IdentityProvider` seam with grants lifted per-story
  → child-scoped; capture the *child's* DOB only (parent/therapist DOB dropped). Not
  engineering-blocked; blocked on the privacy clearance.

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
- **Engineering:** nothing is pick-up-able — everything waits on the above. The M1 policy
  wire-up (`load_policy` → `run_progress` → `kc progress`) is now built too (PR #61), so
  even that last "when the gate opens" task is done; the engine runs the moment a reviewed
  policy file exists.

## Next-session task queue (pinned 2026-07-01, all cleared 2026-07-02)

**All four queued items are done.** What now remains is entirely external/operational
(a DPO/counsel sign-off, a professional collaborator, and ops provisioning) — the M1
policy wire-up that used to be the one "when the gate opens" code task is now built too
(PR #61), so no engineering task is left. The four completed items are kept below for the
audit trail.

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
