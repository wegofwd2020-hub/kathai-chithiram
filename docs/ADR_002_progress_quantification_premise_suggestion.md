# ADR-002 — Per-child progress quantification: capture-first, suggestion-only, engine deferred behind preconditions

**Date:** 2026-06-30
**Status:** Accepted (2026-06-30)
**Branch at decision:** main

---

## Context

Kathai Chithiram turns a premise into a story a child watches; over repeated viewings a
parent observes how the child does. The product's actor model already names these artifacts
(`docs/BRAND.md` §7): a **premise** is *therapist-owned*, per-session **feedback** is
*parent-owned*, and a **goal** is *therapist-owned*. Milestone **M1** (`docs/BACKLOG.md`)
proposes closing the loop: quantify a child's feedback into a **progress measure** (e.g.
"% independent over the last K sessions", a mastery flag, a regulation trend) that may
**suggest** — never auto-author — an updated premise for future stories. The therapist
decides; the existing safety gate still runs.

This is attractive (the child's actual response shapes what comes next) and dangerous in
specific ways:

1. **Pseudo-clinical measurement.** A number called "progress" about a child with special
   needs invites being read as a clinical assessment or diagnosis. The product is not a
   clinician (`docs/CONTENT_SAFETY.md` §3 forbids medical claims/diagnoses/therapeutic
   promises). An arbitrary engineer-chosen threshold ("independent < 60% → regression")
   can mislead a therapist's judgment or pathologize ordinary day-to-day variance.
2. **Automation steering a child's content.** A closed loop where a dip in a measure
   automatically changes the premise or difficulty puts the pipeline — not a person — in
   charge of what a vulnerable child sees next. ADR-001 Decision 5 already rejects automation
   as a sole safeguard; the same principle applies to automated content steering.
3. **A new category of sensitive data.** Behavioral/regulation data about a named child with
   special needs, accrued over time, is special-category data and is *profiling*. It engages
   `PRIVACY.md` (§2 minimization, §5 retention/deletion, §6 no-training) and the DPIA
   anticipated in §8.

The backlog already states the safe near-term move — *"keep the door open now by preserving
quantifiable feedback primitives … keyed to a structured `goal` id — build no engine yet."*
This ADR records the stance and the decomposition before any of the progress logic is built,
so the risky part cannot ship casually. It follows the precedent and the safety philosophy of
ADR-001.

## Decision

**Decision 1 — The feedback primitive set is fixed, minimal, and structured.**
Per-session feedback is a small structured record keyed to a `goal` id, not free text:
`prompt_level ∈ {refused, prompted, independent}`, `completed` (bool), `mood_checkin` (a
short, calm ordinal scale), plus the session timestamp and the story/goal it pertains to.
There is **no free-text clinical-notes field** in the core primitive — that would invite
PII/disclosure capture and clinical-record creep, against minimization (`PRIVACY.md` §2/§3).
Feedback is parent-owned capture (`BRAND.md` §7).

**Decision 2 — Progress is a transparent, derived indicator — not a score, not a diagnosis.**
Any progress measure is computed **deterministically and explainably** from the primitives
over an explicit window (the last K sessions): e.g. % independent, a mastery flag when
independence holds across K, a simple trend from `mood_checkin`. It always exposes its inputs
(which sessions, which values). It is framed as an *engagement / independence indicator for a
therapist's judgment*, explicitly **not** a clinical assessment, diagnosis, mastery-of-a-
disorder, or therapeutic-outcome claim (`CONTENT_SAFETY.md` §3). No opaque or ML scoring in
M1.

**Decision 3 — The system suggests; the therapist decides; it never auto-authors.**
The engine may only surface a *suggestion* to update a premise (therapist-owned) to the
therapist, with its rationale and the underlying evidence. It never edits a premise, never
generates a story, and never schedules one on its own. This mirrors ADR-001 Decision 5
(automation is never the sole safeguard) and the `BRAND.md` §7 ownership model.

**Decision 4 — Every therapist-accepted change re-enters the full safety pipeline.**
A premise the therapist accepts is not a shortcut. The resulting story still passes through
generation (`wegofwd-llm` seam) → scene-script contract validation (KC-3) → content-safety →
human-in-the-loop review (`CONTENT_SAFETY.md` §6) before it reaches the child. Progress-driven
customization is never a bypass of any existing gate.

**Decision 5 — Feedback/progress data inherits the special-category privacy regime.**
Per-child feedback and any derived progress are High-sensitivity child data and constitute
profiling. They inherit `PRIVACY.md`: collect only the primitives (§2/§3); verifiable
hard-delete sweeps them with the child's other artifacts (§5); never used to train or improve
a model (§6); access scoped to the owning family and their therapist; never logged in
plaintext beyond safe aggregates. The parent-captures / therapist-reads split is a deliberate
confidentiality decision (echoing ADR-001 Decision 4.3, at lower risk because this is routine,
parent-authored progress — not a child's experiential disclosure).

**Decision 6 — Build the capture primitives now; gate the engine behind preconditions.**
Two phases, mirroring ADR-001's instructional/experiential split:
- **Now (low-risk):** define and persist the feedback-primitive schema (Decision 1) keyed to a
  structured `goal` id, so longitudinal data can accrue. **No** progress computation and **no**
  suggestions yet.
- **Gated:** the progress measure *and* the premise-suggestion logic may not be built or
  enabled until every precondition in Decision 7 is met.

**Decision 7 — Hard preconditions before the progress engine / suggestion feature.**
All must be satisfied and recorded:
1. A **trained therapist/professional collaborator** (ADR-001 Decision 6) defines what
   constitutes a meaningful signal — the window K, the thresholds, and the trend definitions —
   so the measure is clinically informed rather than an engineer's arbitrary cutoff.
2. **Explainability:** the therapist can see the exact inputs (which sessions, which primitive
   values) behind every number and every suggestion. No black box.
3. A **therapist-in-the-loop path** exists and is tested: a suggestion lands with the premise
   owner, who explicitly accepts / edits / dismisses it; nothing is applied silently.
4. **No clinical-language creep:** copy and UX are reviewed so indicators are never presented
   as clinical measurement, diagnosis, or therapeutic outcome (`CONTENT_SAFETY.md` §3).
5. **Privacy controls for the new data** (Decision 5) are implemented and the verifiable
   hard-delete sweep provably covers progress/feedback records (a test asserts it) before any
   accrued data is used.
6. **DPIA touchpoint:** confirm this progress-*profiling* use is covered by the `PRIVACY.md`
   §8 DPIA; profiling a child can raise additional GDPR/GDPR-K considerations — engage counsel
   if it extends beyond the existing assessment.

**Decision 8 — Reject any closed auto-adjustment loop.**
A loop where the measure automatically changes the premise, difficulty, or schedule is
rejected. There is always a therapist decision *and* the full safety pipeline between a measure
and a child-facing story.

## Consequences

### Positive
- The genuinely useful part — letting a child's real response inform what comes next — is
  preserved, but only through a human therapist and the existing safety gates.
- Longitudinal feedback can begin accruing immediately (low-risk schema) without committing to
  any progress logic, so the eventual engine has real data to be designed against.
- The product avoids the trap of an unexplainable "progress score" that reads as a clinical
  verdict; the measure is transparent and advisory by construction.
- Privacy/profiling obligations gain a concrete sequencing and an owner outside engineering.

### Negative
- The headline M1 capability (the suggestion engine) is deferred behind professional and legal
  engagement, possibly for a while.
- Adds a feedback-primitive schema and its storage/retention plumbing now, ahead of the engine
  that pays it off.

### Neutral
- The exact window K, thresholds, and trend definitions are deliberately **left to the
  professional collaborator** (Decision 7.1); this ADR forces that choice to be informed but
  does not make it.
- The confidentiality specifics of the parent-captures / therapist-reads split (Decision 5)
  must still be decided concretely when the engine is designed.

## Alternatives considered

- **Build the engine now from the primitives** — rejected (Decision 7): thresholds without
  professional input can mislead a therapist or pathologize normal variance, and the profiling
  use isn't yet confirmed against the DPIA.
- **Auto-author or auto-adjust the premise from progress (closed loop)** — rejected (Decisions
  3/8, ADR-001 Decision 5): automation as the sole driver of a vulnerable child's content.
- **An opaque / ML progress score** — rejected (Decision 2): unexplainable to the therapist
  who must own the decision, and it implies clinical measurement.
- **Capture nothing until the engine is designed** — rejected: forgoes longitudinal data; the
  primitive capture is low-risk and the backlog explicitly wants the door kept open.
- **Free-text clinical notes as the feedback unit** — rejected (Decisions 1/5): minimization,
  disclosure/PII risk, and clinical-record creep.

## Migration / rollout

- **Capture track (now):** add a small feedback-primitive contract — a `goal` id plus a
  per-session record `{prompt_level, completed, mood_checkin, timestamp, story_id}` — persisted
  under the child/story in storage, with the verifiable hard-delete sweep extended to cover it
  (a test asserts removal). No engine. Add the new data category to `PRIVACY.md` §3 and a
  non-clinical-framing note to `CONTENT_SAFETY.md`.
- **Engine track (gated):** the progress measure + premise-suggestion path is tracked
  separately and cannot begin until the Decision 7 preconditions are satisfied. Revisit this
  ADR to record each precondition as it is met before any status change.
- **Partner engagement:** engage the trained professional/therapist collaborator (ADR-001
  Decision 6 / Decision 7.1) before the engine is designed — they define the signal, not
  engineering.

**Accepted 2026-06-30:** the capture-track primitive schema has landed
(`src/kathai_chithiram/feedback/` — `SessionFeedback` keyed to `goal_id` + `story_id`, the
store's `feedback.jsonl` log swept by the verifiable hard-delete), and `PRIVACY.md` §3 /
`CONTENT_SAFETY.md` §7 now record the new data category and its non-clinical framing — the
conditions this ADR set for acceptance. **The engine track remains gated**: the progress
measure and premise-suggestion logic may not be built until the Decision 7 preconditions are
satisfied. Revisit this ADR to record each precondition as it is met before the engine begins.
