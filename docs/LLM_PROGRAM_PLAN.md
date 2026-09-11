# Kathai Chithiram — Domain model programme plan

**As of:** 2026-09-10 · **Owner:** WeGoFwd2020 · **Shaping ADRs:** `ADR_006_domain_model_strategy.md`,
`ADR_007_scene_script_v2_authoring_grammar.md`, `ADR_008_training_corpus_provenance.md`

> A phased plan to move generation from a rented frontier model to an owned, clinically
> grounded one — sequenced so that the majority of the quality gain lands before any
> training run, and so the programme is worth doing even if it stops early.
>
> Envelope this plan is costed against: **one engineer (part-time) plus a retained clinical
> collaborator, cash out under ~$25k.**

---

## The honest headline

Four things motivate this programme: unit cost, data sovereignty, domain capability, and IP.
They do not carry equal weight, and the plan is better if that is said out loud.

**The cost argument does not pay back at prototype volume.** The programme's fixed cost is
roughly $16k–26k (below), almost all of it clinician time. Per-story API cost today is
cents. Break-even is therefore in the tens of thousands of stories, and until the platform
is multi-family and running, cost alone would not justify this work. There is also a much
cheaper cost lever available *this week*: `scene_script_prompt.py` re-serialises the entire
JSON Schema plus a worked example into **every** request including repairs, and there is no
prompt caching. Caching that prefix is a large, immediate reduction in spend for a day of
work, and it is in Phase 1 for that reason.

**The sovereignty argument is the strong one.** `docs/DPIA.md` R2 currently rests on an
operational precondition the client cannot verify — that `ANTHROPIC_ZDR_API_KEY` is
provisioned against a confirmed-ZDR org. In-process generation removes the processor
altogether: no third party, no credential to misprovision, a claim verifiable by
construction rather than by attestation. For a product processing special-category data
about children, that is a change in kind.

**The IP argument is the durable one**, and it lands earlier than expected — because
ADR-006's decomposition puts most of the clinical intelligence in a *rubric*, a *vocabulary*
and a *policy* rather than in weights. Those artefacts are the asset, they are readable, and
they exist after Phase 2.

So: run the programme for sovereignty and IP, treat cost as a downstream benefit, and take
the prompt-caching win immediately regardless.

---

## The one thing that determines whether this happens

**A retained clinical collaborator.** Not a reviewer at the end — a co-author, per ADR-001
D6. Without one, Phases 3–6 cannot start: the rubric, the persona grid, the rejection
taxonomy, the narrative-ratio policy and the acceptance judgement are all theirs.

The project **already owes this engagement** for M1 — ADR-002 D7.1 (policy authorship) and
D7.4 (clinical-language review) are open preconditions and
`docs/M1_PROFESSIONAL_COLLABORATOR_BRIEF.md` v0.2 already exists. **Make it one engagement
covering both tracks.** That saves a search, a briefing, a contract and roughly 15 hours of
onboarding, and it means the person who authors `ProgressPolicy` also authors
`NarrativePolicy` — two artefacts that ought to reflect one coherent clinical view.

Profile: a BCBA, SLP or specialist teacher with hands-on experience authoring visual
supports and social narratives for the target population, comfortable being named and
comfortable with a written scope. Volume needed: **~100–110 hours across ~9 months**, front-
loaded into design and then steady adjudication.

---

## Phases

Each phase has a deliverable and an exit gate. Phases 0–2 need no ML, no GPU and no
collaborator sign-off to *begin*, and improve the current Anthropic path as well as the
future local one. Timings assume ~15 engineering hours/week.

### Phase 0 — Contract v2: the art vocabulary registry *(4–6 weeks)* — `KC-13`

ADR-007 D1–D3. Build `scene_script/vocabulary.py` as the single registry for `Background`,
`Expression`, `Gesture`, `Prop`, `SfxCue`; derive both `SCENE_SCRIPT_SCHEMA_V2` and
`scene_art_hints.py` from it; extend the renderer conformance suite to a
renderer × vocabulary matrix; make an unrecognised value a rejection with its own rule id
instead of a silent fall-through to `Background.CALM`. Land it at exact parity with the art
that exists today so the registry goes green on day one.

**Why first:** this is the largest quality lever in the system and it needs no model. Today
a story can ask for a supermarket and the child watches a stick figure in a blank room, and
nothing anywhere reports it.

**Exit gate:** every enum member drawable by every registered renderer, asserted by test;
v1 fixtures still validate and render; unknown values rejected and logged without the value.

### Phase 1 — Constrained decoding and v2 emission *(3–4 weeks)* — `KC-12`

**Status (2026-09-11): done.** Generation emits v2 and constrains output to the
v2 schema via Anthropic structured outputs (`output_config.format`), which
enforces structure only; `validate_scene_script` continues to enforce the
numeric/length/pattern/cross-field rules and the repair loop remains the
fallback. The prompt-caching half shipped earlier (#101). The exit-gate numbers
(100% contract validity, mean attempts ≈ 1.0, token cost) are a live-model
measurement to be recorded by an eval run, not asserted in unit tests.

Grammar-constrained sampling against the v2 schema, so structural violations become
unrepresentable rather than repairable. Generation paths emit v2. **Also in this phase, and
independent of everything else: cache the schema prompt prefix** — the immediate cost win
described above.

**Why here:** with a closed vocabulary in place, constrained decoding collapses the
three-attempt repair loop toward one attempt and removes contract validity as a variable in
every later measurement.

**Exit gate:** contract-validity rate at 100% across the `mock_scripts.py` mutation battery;
mean attempts per story ≈ 1.0; measured per-story token cost down.

### Phase 2 — Rubric validators and `NarrativePolicy` *(3–4 weeks, + collaborator)* — `KC-16`

ADR-007 D4–D6. Add `author`/`perspective`/`intent` with the experiential gate; add
per-scene `sentence_function`; ship `NarrativePolicy` with **no defaults** and a
`TEMPLATE-replace-me` example, mirroring `progress_policy.template.json`. Write the
person/tense/idiom/positive-framing validators. The collaborator authors the real policy.

**Why here:** this is where the clinical intelligence first becomes a reviewable artefact.
If the programme stops after this phase, the product is materially better and the IP exists.

**Exit gate:** a collaborator-authored `NarrativePolicy` in place; ratio and reading-load
rules enforced; `intent: "experiential"` structurally rejected; ADR-007 ratified.

### Phase 3 — Corpus *(6–8 weeks elapsed, collaborator-paced)* — `KC-15`

ADR-008. Grid and personas authored; rejection taxonomy fixed; `kc corpus` tooling; split
assigned by grid cell **before** generation; teacher generates candidates; validators filter;
collaborator adjudicates in tranches of ~250 with a double-adjudicated slice. Dataset card
written as the corpus grows, not after.

**Exit gate:** ~800–1,000 adjudicated items with stated grid coverage, a reported agreement
figure, and `DATASET_CARD.md` complete. Held-out cells reserved and untouched.

### Phase 4 — `kc eval` *(3–4 weeks, overlaps Phase 3)* — `KC-14`

ADR-006 D6's four axes: contract validity, per-rule rubric conformance, blind paired
clinician preference against the Anthropic baseline, and an adversarial safety suite.
Establish the baseline number for the current path **before** any adapter exists — otherwise
there is nothing to be non-inferior to.

**Exit gate:** harness runs in CI on the dev split; a recorded baseline for the current
production path on all four axes.

### Phase 5 — Adapter and local provider *(5–7 weeks)* — `KC-17`

`LocalModelProvider` as a second `LLMProvider` concrete, asserting `no_training` and
`zero_retention` structurally (holds no client, opens no socket — asserted by test). QLoRA
SFT of Phi-4-mini-instruct on the gold set; retrain and re-score per tranche to get a
learning curve and apply ADR-008 D7's stopping rule. Optional preference tuning on
synthetic accept/reject pairs only.

**Exit gate:** the eval harness run on the held-out split, including the unseen-grid-cell
slice.

### Phase 6 — Gate, rollout, and documents *(3–4 weeks)*

Apply ADR-006 D6. If the gate passes, the local model becomes the default provider and
`docs/DPIA.md` R2, `PRIVACY.md` §6, `docs/PARENT_PRIVACY_NOTICE.md` and
`docs/CONTENT_SAFETY.md` §5 are revised. If it does not, ship the two-tier fallback (below).
Either way the KC-7 human review gate is unchanged.

**Elapsed total: roughly 7–9 months** at part-time engineering, collaborator-paced in the
middle.

---

## Cost model

Ranges, not estimates dressed as figures. The shape matters more than the total: **over 80%
of this budget is clinician time, and essentially none of it is compute.**

| Line | Basis | Low | High |
|---|---|---|---|
| Clinical collaborator — design (rubric, grid, personas, taxonomy, `NarrativePolicy`) | ~32 h | $4,000 | $5,600 |
| Clinical collaborator — adjudication | ~55 h at 2.5–4 min/item, tier-2 filtered | $6,900 | $9,600 |
| Clinical collaborator — eval preference judging + copy review | ~18 h | $2,250 | $3,150 |
| *(Collaborator subtotal — ~105 h at $125–175/h consulting)* | | *$13,150* | *$18,350* |
| Teacher API for corpus generation | ~2,500 candidates; cacheable prefix | $300 | $900 |
| Training compute | QLoRA on 3.8B ≈ 2–3 h/run at ~$0.92/h (5090-class); 30–60 runs, some on H100 PCIe at ~$2.01/h | $150 | $800 |
| Inference for eval and prototype serving | local workstation; marginal ≈ electricity | $0 | $200 |
| Legal — DPO addendum delta + trademark rename opinion | delta on work already owed for launch | $2,000 | $5,000 |
| Contingency | ~10% | $1,500 | $2,500 |
| **Total** | | **≈ $17,100** | **≈ $27,750** |

**Landing inside $25k** means holding collaborator hours near 100 and the rate near $150, or
finding a collaborator who will take part of the engagement as advisory equity. The three
levers that actually move this number:

1. **Merge the M1 and ADR-006 collaborator engagements.** Saves search, contracting and
   ~15 h of duplicated onboarding.
2. **Never spend a clinician hour on something a validator can check.** Every rejection
   reason that recurs should become a Phase 2 validator; that is what makes tranche 4 cheaper
   than tranche 1.
3. **Apply ADR-008's stopping rule honestly.** The temptation is to keep labelling. Retrain
   per tranche, watch the curve, and stop when it flattens — the difference between 1,000 and
   2,500 items is roughly $7k and, most likely, very little accuracy.

**Not in this budget, by design:** always-on hosted inference (an L4-class endpoint runs
roughly $250–400/month and is not needed until there is traffic), a second clinician for
independent inter-rater reliability (worth adding if funding appears — it is the single
best marginal spend), and any renderer art expansion, which is a product cost tracked
separately.

---

## Decision gates and kill criteria

| Gate | Condition to proceed | If it fails |
|---|---|---|
| **G0** — after Phase 0 | Vocabulary conformance matrix green at parity with today's art | Stop and fix; nothing downstream is valid without it |
| **G1** — before Phase 3 | A named collaborator retained under written scope | **Halt the programme.** Phases 0–2 stand alone and are worth having. Do not proceed with an engineer-authored rubric |
| **G2** — after Phase 3 tranche 1 | Adjudication agreement acceptable; rejection reasons cluster into a workable taxonomy | Revise the grid and rubric before spending more clinician hours |
| **G3** — after Phase 4 | Baseline recorded for the current path on all four axes | Do not train — there is nothing to compare against |
| **G4** — after Phase 5 | Tuned model non-inferior on blind clinician preference, 100% contract validity, no safety regression | **Two-tier fallback**, below |

### The two-tier fallback is a success outcome

If a 3.8B model loses the preference test, do not ship it as the default and do not keep
training in the hope it turns around. Ship the split instead: **the local model handles the
constrained emitter step (structure, vocabulary, lowering); the frontier model handles the
shaping step (turning a parent's paragraph into the right narrative arc).** That still moves
most tokens in-house, still cuts cost substantially, still produces the rubric and corpus
assets, and leaves the sovereignty win partial but real. It is a worse outcome than a clean
win and a much better one than a year spent chasing parity.

### Genuine kill criteria

- No collaborator retained within ~3 months of G1 → stop after Phase 2 and revisit.
- Phase 0 reveals the vocabulary cannot be closed without unacceptable rejection rates on
  realistic inputs → the premise is wrong; reconsider before Phase 3.
- Adjudication cost per item does not fall across tranches → the rubric is not converging;
  stop and rework rather than buying more labels.

---

## Risks

| Risk | Likelihood | Impact | Response |
|---|---|---|---|
| Collaborator not found, or leaves mid-programme | Medium | Blocking | Merge with the M1 engagement (already needed); written scope with deliverables; corpus and taxonomy are handover artefacts by design |
| Synthetic parent voices too clean → model degrades on real inputs | **High** | High | ADR-008's deliberate input roughening; a real-path qualitative review by the collaborator that informs the grid without any story entering the corpus; hold out whole grid cells |
| Closed vocabulary too small → rejection rate on real stories unacceptable | Medium | High | Land Phase 0 at parity first and *measure* the rejection rate before Phase 3; treat vocabulary growth as a funded product track, not a chore |
| Two supported schema majors create drift | Medium | Medium | Doubled conformance matrix in CI; a dated plan to retire v1 |
| Self-hosting availability and patching burden | Medium | Medium | Keep the Anthropic provider as a live fallback path, not a removed one; the seam makes this free |
| Scope creep into the risk-of-harm path | Medium | **Severe** | Explicitly out of scope in ADR-006. That path is a safeguarding design owned with a professional; do not let a modelling programme absorb it |
| Trademark exposure on "social stories" | Low now, rising with commercial launch | Medium | ADR-007 D8 rename in Phase 2; a short counsel opinion in the legal line |
| Tuned model's failure modes are subtler and harder to spot than the teacher's | Medium | High | The KC-7 human gate is unchanged; per-rule eval reporting; adversarial suite in CI |

---

## What this programme must not do

Restated from the ADRs because these are the temptations a training programme creates.

- Train on a real child's story. Ever, in any form (ADR-008 D1).
- Turn `feedback.jsonl` — a child's `mood_checkin`, `prompt_level`, `completed` — into a
  reward signal. It is ADR-002 D8's closed loop in its least inspectable form (ADR-006 D7,
  ADR-008 D4).
- Give a model authority over risk-of-harm triage (ADR-001 D5).
- Relax the KC-7 human review gate because the model is now tuned (`CONTENT_SAFETY.md` §6).
- Replace the deterministic renderer with a generative video model. Determinism is what
  makes `guard_render`'s flash and high-contrast limits a guarantee rather than a sample.
- Let an engineer pick a clinical constant. No `DEFAULT_K`, no default ratio, no default
  reading load (ADR-003 D2, ADR-007 D5/D6).
- Waive an eval axis because the person who trained the model finds the output convincing.

---

## Immediate next actions

1. **Cache the schema prompt prefix.** A day's work, immediate cost reduction on the path
   running today, independent of every decision in these ADRs.
2. **Measure what the vocabulary problem actually costs.** Instrument
   `scene_art_hints.art_hint_for` to count how often a scene falls through to
   `Background.CALM` / `Gesture.REST`. That number sizes Phase 0 and is currently unknown.
3. **Extend the M1 collaborator outreach to cover this track**
   (`docs/M1_COLLABORATOR_OUTREACH.md`) — one engagement, two deliverable sets.
4. **Start Phase 0.** It is ungated, needs nobody's sign-off, and everything else depends
   on it.
