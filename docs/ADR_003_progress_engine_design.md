# ADR-003 — Progress-engine design: a deterministic, policy-driven measure + suggestion seam, clinical parameters owned by the collaborator

**Date:** 2026-07-01
**Status:** Proposed
**Branch at decision:** main

---

## Context

ADR-002 (Accepted) settled the **stance** for Milestone M1: capture the feedback
primitives now, but keep the *progress measure* and the *premise-suggestion* logic
gated behind the six preconditions in its Decision 7 — chief among them, a trained
professional collaborator must define what counts as a meaningful signal (the window
K, the thresholds, the trend definitions), because those are clinical judgment and
not an engineer's to pick.

That stance is now backed by real scaffolding, all deliberately inert:

- `progress/evidence.py` — a read-only **evidence view** that lists the exact
  sessions and their raw primitive values for a goal over a window, and computes
  *nothing* derived (the explainability substrate, ADR-002 D7.2).
- `progress/suggestion.py` + `progress/review.py` — the **accept / edit / dismiss**
  therapist-in-the-loop path (ADR-002 D7.3). A suggestion can be recorded and
  decided; recording a decision triggers nothing.
- `docs/M1_PROFESSIONAL_COLLABORATOR_BRIEF.md` — the ask to the collaborator, and
  `docs/DPIA.md` — the profiling assessment. Both are Draft v0.1; **no collaborator
  is engaged yet**.

What ADR-002 does *not* do is say **how the engine is built** — the shape of the
measure, where the clinical parameters live, how a suggestion is generated from a
measure, and what code may be written before the collaborator responds. Left
unanswered, the natural failure mode is an engineer quietly hardcoding a threshold
("independent ≥ 60% over the last 5 → suggest advance") to make the feature work —
exactly the arbitrary cutoff ADR-002 D7.1 forbids and ADR-002 §Context calls out as
pseudo-clinical measurement.

This ADR records the **engine design** before it is built, so the risky part — the
clinical judgment — is structurally impossible to smuggle into code, and so the
mechanics that carry no clinical judgment can be built safely now, de-risking the
collaborator handoff. It follows the precedent and safety philosophy of ADR-001 and
ADR-002.

## Decision

**Decision 1 — The engine is two pure, deterministic stages over the evidence
substrate; it never recomputes raw inputs.**
The engine is composed of two side-effect-free functions layered on the existing
`EvidenceBundle` (it consumes that bundle, it does not re-read or re-tally feedback):

1. **measure:** `(EvidenceBundle, ProgressPolicy) → ProgressIndicator` — applies the
   policy's rules to the raw evidence and returns a transparent indicator.
2. **suggest:** `(ProgressIndicator, ProgressPolicy) → PremiseSuggestion | None` —
   turns a *present, actionable* signal into a suggestion, or returns `None`.

Both are deterministic and explainable by construction (no clock, no randomness, no
network, no model). The same evidence + policy always yields the same indicator and
the same suggestion. This is the "no black box" requirement (ADR-002 D2) made
structural.

**Decision 2 — Every clinical parameter lives in a `ProgressPolicy` supplied as
configuration; engineering ships the interpreter, never the values.**
The window K, the thresholds, the trend definitions, the uncertainty band, and the
per-goal on/off switch are fields of a `ProgressPolicy` object authored by the
collaborator (ADR-002 D7.1) and loaded as configuration — the same seam discipline as
`wegofwd-llm` for the LLM and `StorageCipher` for at-rest crypto. Engineering builds
and tests the **schema, its validation, and the deterministic interpreter that
applies it**. Engineering ships **no default policy values**. There is no
`DEFAULT_K`, no fallback threshold, no "reasonable" constant. If no signed-off policy
is loaded, the engine stays off (Decision 7) and `measure`/`suggest` are never called.
Any example policy committed for tests is synthetic, explicitly labelled non-clinical,
and never importable as a production default.

**Decision 3 — The indicator carries its own evidence and the rule that fired;
explainability is a payload, not a report generated later.**
A `ProgressIndicator` embeds the `EvidenceBundle` it was computed from and an
identifier of which policy rule produced its verdict (e.g. which threshold matched, or
that the uncertainty band was hit). A generated `PremiseSuggestion`'s `rationale`
states, in policy-supplied non-clinical wording, the signal and points at that
evidence. A therapist reading a suggestion can always trace it back to the exact
sessions and values behind it (ADR-002 D7.2), because it never had to be reconstructed.

**Decision 4 — "Not enough data" and "no actionable signal" are first-class states
that suppress any suggestion.**
The indicator distinguishes *insufficient data* (fewer than the policy's minimum, or
inside the uncertainty band) and *no actionable signal* from *signal present*. Only
the last may produce a suggestion; the first two return `None` from `suggest`. This
answers the collaborator brief's open question ("should 'not enough data' suppress a
suggestion?") in the architecture, while the actual band boundaries stay policy-owned
(Decision 2). Suppressing on uncertainty is the guard against pathologising ordinary
day-to-day variance (ADR-002 §Context, D2).

**Decision 5 — The engine's only output effect is `record_suggestion`; it re-uses the
existing inert path and adds no new authority.**
When `suggest` returns a suggestion, the engine records it via the existing
`progress/review.py::record_suggestion` seam — the same PENDING record a human could
file today. The engine never edits a premise, never generates a story, never
schedules one, and never auto-decides its own suggestion (ADR-002 D3/D8, ADR-001 D5).
Everything downstream is the already-built, human-driven accept / edit / dismiss path,
and any accepted premise re-enters the full safety pipeline (ADR-002 D4). The engine
adds a *producer* for the pending queue; it gains no new power over a child's content.

**Decision 6 — Suggestion copy and framing are policy-supplied and
collaborator-reviewed; the engine authors no clinical language.**
The wording of a suggestion (its tone, its framing as a prompt-for-your-decision, its
avoidance of clinical/diagnostic/outcome language) comes from the policy, reviewed by
the collaborator (ADR-002 D7.4, CONTENT_SAFETY.md §3/§7). The engine composes a
suggestion from policy-supplied templates and the traced evidence; it does not
generate free-form clinical prose. Code review keeps clinical phrasing out of the
source (it belongs in the reviewed policy, not in a string literal).

**Decision 7 — This ADR designs the engine; it does not lift ADR-002's gate.**
Designing the mechanics does not permit enabling them. Loading any non-inert
`ProgressPolicy` — and therefore running `measure`/`suggest` against real data —
remains blocked until every ADR-002 Decision 7 precondition is satisfied and recorded,
the collaborator-authored policy (D7.1) foremost. The mechanics, schema, validation,
and interpreter may be **built and unit-tested against synthetic policies now**,
because none of that embodies a clinical judgment; the engine simply has no production
policy to run until the gate opens. See §Precondition status.

**Decision 8 — The indicator and any suggestion are derived special-category data and
inherit the existing regime; the engine introduces no new store and no new plaintext.**
A computed indicator is transient (recomputed from evidence on demand) and is not
persisted as a separate record; a generated suggestion persists only through the
existing `suggestions.jsonl` under the story directory, which the verifiable
hard-delete sweep already covers (a store test asserts `suggestions.jsonl` ∈
`artifact_paths`). The engine logs no raw primitives, no child identifiers, and no
indicator values in plaintext — safe aggregates only (ADR-002 D5, PRIVACY.md §5/§6/§7).

## Consequences

### Positive

- The clinical judgment cannot leak into code: with no default policy values and the
  gate on loading a real policy, there is no path by which an engineer's threshold
  reaches a child. The design enforces ADR-002 D7.1 structurally, not by discipline.
- Real, valuable work can proceed now — the policy schema, validation, interpreter,
  and the measure/suggest mechanics — all unit-testable against synthetic policies,
  so when the collaborator responds the remaining step is "load their policy," not
  "now build the engine."
- The engine reuses the evidence substrate and the accept/edit/dismiss path already
  shipped; it adds a producer, not a parallel pipeline, keeping one human-in-the-loop
  seam.
- Explainability and suppression-on-uncertainty are built into the types, so a
  suggestion can never appear without traceable evidence or on thin data.

### Negative

- Introduces a `ProgressPolicy` schema and interpreter that produce nothing until a
  collaborator authors a policy — scaffolding ahead of payoff, as with the capture
  track before it.
- Modelling policy as configuration pushes real expressiveness into a config format;
  the schema must be rich enough for the collaborator's thresholds/trends without
  becoming a general rules engine. Getting that boundary right is non-trivial.

### Neutral

- The exact policy shape (which trend operators, whether K is a count or a time
  window or both, per-behaviour vs per-goal signals) is informed by the collaborator's
  answers to the brief's open questions and is settled when the schema is written, not
  here.
- Where the loaded policy lives operationally (who signs it, how it is versioned and
  audited) is an operational decision for when the gate opens.

## Alternatives considered

- **Hardcode sensible thresholds and let the collaborator tune later** — rejected
  (Decision 2, ADR-002 D7.1): the first shipped constant *is* the clinical judgment;
  "tune later" rarely happens and the arbitrary cutoff is exactly the harm ADR-002
  names.
- **An ML / learned progress score** — rejected (ADR-002 D2, D7.2): unexplainable to
  the therapist who must own the decision, and it implies clinical measurement.
- **Build the whole engine now, policy and all** — rejected (Decision 7, ADR-002
  D6/D7): enabling the measure before the collaborator defines the signal and before
  the DPIA confirms the profiling use is the precise thing the gate exists to prevent.
- **Design and build nothing until the collaborator responds** — rejected: the
  mechanics, schema, and interpreter embody no clinical judgment and are safe to
  build; deferring them wastes the window and leaves a bigger, riskier lift for the
  moment the collaborator is finally engaged.
- **Persist the computed indicator as its own record** — rejected (Decision 8):
  recomputing from evidence keeps a single source of truth, avoids a new
  special-category artifact to secure and sweep, and cannot drift from the evidence it
  claims to explain.
- **Let the engine auto-decide high-confidence suggestions** — rejected (Decision 5,
  ADR-002 D3/D8): a closed loop, however confident, puts the pipeline in charge of a
  vulnerable child's content.

## Precondition status (ADR-002 Decision 7)

Tracked honestly; the engine cannot be enabled until every row is **Met**.

| # | Precondition | Status | Note |
|---|--------------|--------|------|
| 7.1 | Collaborator defines K / thresholds / trends | **Open** | Brief is Draft v0.1; no collaborator engaged. The `ProgressPolicy` is the artifact they author. |
| 7.2 | Explainability — therapist sees exact inputs | **Substrate met** | `progress/evidence.py` ships; Decision 3 keeps the indicator/suggestion tied to it. |
| 7.3 | Tested therapist-in-the-loop accept/edit/dismiss | **Met** | `progress/review.py` + tests; the engine only feeds this path (Decision 5). |
| 7.4 | No clinical-language creep; copy reviewed | **Open** | Framing is policy-supplied and collaborator-reviewed (Decision 6); nothing to review until 7.1. |
| 7.5 | Privacy controls; hard-delete provably covers the data | **Largely met** | `suggestions.jsonl` is under the story dir and swept by hard-delete (store test asserts). At-rest encryption seam (`storage/crypto.py`, KC-5) exists but is opt-in and must be enabled for any real deployment. |
| 7.6 | DPIA touchpoint confirms the profiling use | **Open** | `docs/DPIA.md` is Draft v0.1; needs DPO/counsel review before enablement. |

## Migration / rollout

- **Mechanics track (buildable now, still gated off):** add a `ProgressPolicy` schema
  with validation, the deterministic `measure` and `suggest` interpreter over
  `EvidenceBundle`, and the `ProgressIndicator` type carrying its evidence and fired
  rule (Decisions 1–4). Unit-test against **synthetic** policies only. Ship no default
  policy values; the engine has no production policy to run. The producer wires to the
  existing `record_suggestion` (Decision 5) but is not invoked in any real flow.
- **Enablement track (gated):** loading a collaborator-authored policy and running the
  engine against real data is blocked until every §Precondition-status row is Met.
  Revisit this ADR and ADR-002 to record each precondition as it is met before any
  enablement.
- **Collaborator engagement:** the `ProgressPolicy` is the concrete deliverable behind
  `docs/M1_PROFESSIONAL_COLLABORATOR_BRIEF.md` — the collaborator's answers become the
  policy schema's fields and the first signed policy (ADR-002 D7.1/D7.4).
- **Doc updates:** point `docs/BACKLOG.md` M1 at this ADR; note in the brief that the
  policy is the artifact we need from the collaborator.

Status flips `Proposed → Accepted` only once the engine-mechanics design here is
reflected in code (the policy schema + interpreter land, inert and default-free) and
this ADR is referenced from the backlog. Enabling the engine is a *separate* event
gated on the §Precondition status, not on this ADR's acceptance. Do not pre-flip, and
do not read acceptance of this design as permission to load a policy.
