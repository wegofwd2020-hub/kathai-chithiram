# M1 — Progress engine + premise-suggestion (GATED behind ADR-002 Decision 7)

**Labels:** P1, safety, privacy, gated
**Refs:** `docs/ADR_002_progress_quantification_premise_suggestion.md`; `docs/BACKLOG.md` (M1); CONTENT_SAFETY.md §3/§7; PRIVACY.md §3/§8

## Status
**Engine GATED — do not build the progress measure or the suggestion-generation
logic** until every Decision 7 precondition below is met and recorded in ADR-002.
The capture track (feedback primitives) is done. This ticket tracks the gate and
the ships-inert scaffolding that engineering may own *before* the gate opens.

## The gate — ADR-002 Decision 7 preconditions (all required)
- [ ] **7.1 Professional collaborator defines the signal.** A trained
  therapist/professional sets the window **K**, the thresholds, and the trend
  definitions. *Engineering must not choose these.* → see
  `docs/M1_PROFESSIONAL_COLLABORATOR_BRIEF.md`.
- [x] **7.2 Explainability substrate.** The exact inputs behind any number are
  visible (which sessions, which primitive values). → `progress/evidence.py`
  builds a read-only evidence bundle of the raw captured primitives (no measure).
- [x] **7.3 Therapist-in-the-loop path exists and is tested.** A suggestion lands
  with the premise owner, who explicitly accepts / edits / dismisses it; nothing
  is applied silently. → `progress/suggestion.py` + `progress/review.py` (the
  decision plumbing; it records the therapist's call and triggers nothing).
- [ ] **7.4 No clinical-language creep.** Copy/UX reviewed so indicators are never
  presented as clinical measurement, diagnosis, or therapeutic outcome (§3).
- [x] **7.5 Privacy controls for the new data + deletion test.** Suggestion/review
  records inherit the special-category regime and the verifiable hard-delete
  sweeps them (a test asserts it). → stored under the story (`suggestions.jsonl`,
  encrypted at rest by KC-5, swept by KC-1); `tests/.../progress/` asserts removal.
- [ ] **7.6 DPIA touchpoint.** Confirm the progress-*profiling* use is covered by
  the PRIVACY.md §8 DPIA (`docs/DPIA.md` R8); engage counsel if it extends beyond
  the current assessment.

## What is built now (ships inert — no measure, no auto-suggestion)
- `progress/evidence.py` — `build_evidence()` surfaces the raw captured
  primitives for a goal over a window. It computes **no** progress measure: no %,
  no ratio, no trend, no mastery flag, no threshold verdict (those are Decision 2
  / Decision 6 gated). It only exposes the inputs (Decision 7.2).
- `progress/suggestion.py` + `progress/review.py` — the therapist accept / edit /
  dismiss review plumbing (Decision 7.3). **Nothing generates suggestions** (the
  engine that would is gated); this only records a therapist decision and never
  edits a premise, generates a story, or schedules one (Decisions 3/4/8).

## Enabling wire-up — BUILT, gated by config (2026-07-02)
The measure/suggest interpreter (ADR-003) and now the **wire-up** are landed, but the
engine still ships **no policy** and does nothing until a collaborator-authored one is
loaded — so an engineer's cutoff structurally cannot reach a child (ADR-003 D2):
- `progress/config.py` — `load_policy(path)` / `policy_from_mapping(data)`: the *only*
  way a real `ProgressPolicy` enters the engine. Ships no policy; every value is the
  collaborator's, and each clinical invariant is still enforced by the schema types.
- `progress/run.py` — `run_progress(store, evidence, policy, …)`: `measure → suggest →
  record_suggestion` (the one permitted effect, **inert** — a therapist decides;
  Decisions 3/4/8).
- `kc progress <goal> --policy <file> --story <id>` — runs it. `--policy` is **required**
  (no default). Recording a suggestion requires the acting principal to hold the
  **therapist** role on the story (`Action.DECIDE_SUGGESTION`), so it fails closed
  otherwise (ADR-002 actor model / ADR-004).
- **Still gated:** *using* this in production remains blocked on 7.1 (collaborator authors
  the policy), 7.4 (clinical-copy review), 7.6 (DPIA progress-profiling touchpoint). The
  plumbing exists; a reviewed policy does not.

## What stays gated (Decision 6/7 — do NOT build here)
- Authoring a real `ProgressPolicy` (window K, thresholds, copy) — the collaborator's,
  not engineering's (7.1).
- Enabling the engine in production before 7.1/7.4/7.6 are met.
- Any closed auto-adjustment loop (Decision 8) — permanently rejected.

## Acceptance criteria (for opening the gate later)
- Every Decision 7 checkbox above is ticked and recorded in ADR-002, with 7.1
  authored by the professional collaborator (not engineering).
- The measure, once built, is deterministic and explainable over the
  collaborator-defined K/thresholds, framed as a non-clinical engagement /
  independence indicator (§3/§7).
- Every therapist-accepted premise still re-enters the full safety pipeline
  (generate → KC-3 validate → content-safety → KC-7 human review) — never a
  bypass (Decision 4).
