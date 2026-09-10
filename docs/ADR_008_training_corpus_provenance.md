# ADR-008 — Training corpus: wholly synthetic, clinician-adjudicated, and provenance-carrying

**Date:** 2026-09-10
**Status:** Proposed
**Branch at decision:** main

---

## Context

ADR-006 Decision 4 puts a corpus at layer L3: the gold set that a LoRA adapter learns from
and, more importantly, the held-out slice that ADR-006 Decision 6's acceptance gate scores
against. Without it there is no adapter and no way to know whether anything improved.

The obvious corpus is the one we already hold. It is also the one we may never touch. Every
delivered story is a `story.txt` a parent wrote about their own child, a `scene_script.json`
derived from it, a `review.json` with an operator's free-text reason, and a `feedback.jsonl`
of that child's sessions. `CLAUDE.md` states it plainly — "no real child data in tests or
fixtures" — and `PRIVACY.md` §8, the `docs/DPIA.md` lawful basis (Art. 6(1)(a) + Art.
9(2)(a) explicit consent, for a stated purpose), the 30-day retention default and KC-1/KC-10
verifiable hard-delete all point the same way. Training is a *different purpose* from
generating this family's story, and it is a purpose that outlives deletion: a model does not
forget when `delete_story` runs. A crypto-shredded corpus and a model trained on it are not
the same object, and only one of them can be destroyed.

There is a subtler version of the same temptation. The system already produces something
that looks exactly like preference data: the KC-7 review gate emits approve/reject decisions
with reasons, and `feedback.jsonl` emits per-session `prompt_level`, `completed` and
`mood_checkin` keyed to a goal. A preference-tuning pipeline could consume both tomorrow.
ADR-002 D8 rejects "any closed auto-adjustment loop," and a model whose objective is
partly *this child's recorded mood* is the strongest form of that loop and the least
inspectable. This ADR makes both prohibitions explicit rather than leaving them implied.

What is left is to build a corpus from nothing — which turns out to be an advantage, because
a wholly synthetic corpus is the only kind whose provenance can be stated completely.

## Decision

**Decision 1 — The corpus contains no real submission, ever, in any form.**
Not raw, not pseudonymised, not paraphrased, not "inspired by," and not as a held-out
evaluation item. `NameMapping` and `pseudonymize` bound what reaches a *provider*; they are
not an anonymisation good enough to relicense a family's story into training data, and the
question is purpose, not identifiability. This is a permanent constraint of the product, not
a constraint of the current phase.

**Decision 2 — The corpus is instantiated from an explicit scenario × persona grid,
authored with the clinical collaborator.**
Two axes, both collaborator-owned:

- **Scenario** — the situation the story addresses. An indicative first cut, to be replaced
  by the collaborator's: hygiene routines, transitions between activities, mealtime, arrival
  and departure, waiting, an unexpected change to a plan, a medical or dental visit, sensory
  overwhelm and regulation, sibling or peer conflict, asking for help, using a new place.
- **Persona** — the child the story is for, described only in terms that change the
  authoring: expressive-language level, receptive-language level, sensory profile,
  tolerance for change, and attention span. Personas are *composites defined by the
  collaborator from professional experience*, never derived from a real child known to the
  project, and are recorded as such.

Each grid cell is instantiated N times with varied parent-voice inputs, so the corpus
contains the messy, hedged, run-on paragraph a real parent writes — not a clean prompt.
Grid coverage is the sampling plan and is stated up front, so a gap in the corpus is a
visible gap rather than an unknown one.

**Decision 3 — Three-tier labelling: teacher generates, validators filter, clinician
adjudicates.**
1. **Generate** — the current Anthropic path (ADR-006 keeps it as teacher) produces a
   candidate v2 scene script per input.
2. **Filter** — ADR-007's contract and rubric validators reject anything structurally or
   grammatically wrong before a human sees it. Clinician attention is scarce and must never
   be spent on a caption that exceeds 140 characters.
3. **Adjudicate** — the collaborator marks each surviving candidate **accept**, **edit**
   (with the corrected script) or **reject** (with a reason drawn from a closed
   taxonomy — wrong granularity, directive-heavy, abstract language, wrong emotional
   register, unsafe framing, mismatched art). Only accepted and edited items enter the gold
   set. Rejected items are retained as the negative half of preference pairs.

The closed reason taxonomy matters more than it looks: it is what turns adjudication into a
measurable signal (ADR-006 Decision 6 axis ii reports per-rule) and what lets the rubric
improve, since a reason that recurs is a validator waiting to be written.

**Decision 4 — Preference pairs come only from the synthetic corpus. The production review
gate is never a training source.**
`review.json` decisions and reasons on real families' stories stay operational telemetry:
they inform the rubric *through the collaborator's judgement*, never through a pipeline.
`feedback.jsonl` — `prompt_level`, `completed`, `mood_checkin` — is excluded from every
objective, loss and filter. Restating ADR-006 Decision 7 because this is the ADR where the
data actually sits: a model optimised against a child's recorded mood is ADR-002 D8's closed
loop wearing an opaque coat, and no gate would catch it.

**Decision 5 — Every example carries provenance, and the corpus ships a dataset card.**
Per example: grid cell, input generator and its version, teacher model and version, prompt
version, rubric/validator version, adjudicator id (opaque), decision, decision reason,
timestamps, and the edit diff where one exists. Per corpus: a `DATASET_CARD.md` stating
composition, grid coverage, who adjudicated, inter-rater agreement on the double-adjudicated
slice, known gaps, and the explicit statement that no real child data is present.

This is not paperwork. "What is this model trained on?" is a question a DPO, a school
district, a clinician and a parent will each ask, and a complete answer is a competitive
asset in this category, where the honest answer for most tools is "we don't know."

**Decision 6 — Split before generating, not after.**
Train / dev / test are assigned **by grid cell and by input seed**, before generation, so
no paraphrase of a training input can appear in the test set. A held-out set of whole grid
cells is also reserved to measure generalisation to scenarios never trained on — the case
that actually matters, since a real family will bring a situation the grid does not contain.

**Decision 7 — Size targets are estimates with a stopping rule, not a plan.**
Indicatively: ~300 adjudicated items is the floor below which a LoRA on a narrow structured
task is unlikely to beat prompting; ~800–2,000 is where the return is expected; beyond
~5,000 the marginal clinician hour is better spent on the rubric than on more labels, since
rubric improvements raise the floor for every example at once and labels do not. **Treat
these as priors to be overwritten by a learning curve** — build in tranches of ~250, retrain
and re-score each tranche, and stop when the eval curve flattens. Clinician hours are the
budget's binding constraint (see `docs/LLM_PROGRAM_PLAN.md`), so the stopping rule is the
most valuable line in this ADR.

**Decision 8 — Do not ingest third-party social stories.**
Published social-narrative collections are copyrighted, frequently trademark-bound (ADR-007
D8), and often sold to the very families we serve. Scraping them would be an infringement
risk, a provenance hole in the dataset card, and a poor fit besides — their value is in
being *general*, and this product's premise is that a story should be *specific*. The corpus
is original work commissioned from a professional.

**Decision 9 — Corpus and adapter are project assets with their own custody, not story
artefacts.**
They contain no personal data, so KC-1 hard-delete and the retention sweep do not apply and
must not be extended over them — a versioned, auditable training asset that a sweep can
silently mutate is worse than useless. They are versioned, checksummed, access-controlled
and stored outside `<store-root>`. `docs/DPIA.md` gains a line noting the corpus is
non-personal by construction and stating who holds the adapter weights.

## Consequences

### Positive

- The strongest privacy answer available in this category: not "we anonymise your child's
  story before training," but "your child's story is never training data, and here is the
  card for what is."
- A synthetic grid gives deliberate coverage of situations that are rare in real intake but
  matter clinically — a first dental visit, a fire drill — which an organic corpus would
  under-represent exactly where support is scarcest.
- The reason taxonomy makes the rubric self-improving: recurring rejections become
  validators, which raise the floor for the whole system and reduce future adjudication load.
- Provenance is complete because the corpus is synthetic. This is the rare case where the
  constraint produces the better artefact.
- Splitting by grid cell measures the thing that matters — generalisation to an unseen
  situation — rather than the thing that is easy to measure.

### Negative

- Synthetic parent voices will be cleaner, more coherent and more grammatical than real
  ones. This is the corpus's central validity threat: a model tuned on tidy inputs may
  degrade on a real 3 a.m. paragraph. Mitigation is deliberate input roughening (typos,
  run-ons, hedging, contradiction, missing context, two children mentioned at once) and,
  crucially, a **qualitative** review of real-path failures by the collaborator that informs
  the grid without any story entering the corpus.
- Adjudication is the programme's cost centre and its critical path. A single collaborator
  is also a single point of clinical view; the double-adjudicated slice measures that but
  does not remove it.
- The corpus encodes one professional's judgement. It should be described that way in the
  dataset card — as an authored position, not a ground truth.
- Building a corpus from nothing is slower than harvesting one, and the delay is real.

### Neutral

- Which teacher generates candidates is independent of ADR-006's choice of base and may
  change between tranches, provided the change is recorded per example.
- Storage and format are small: a few thousand JSON records with diffs. Tooling can be a
  CLI subcommand and a directory.

## Alternatives considered

- **Train on real submissions under a broadened consent.** Rejected. It could probably be
  made lawful with a separate opt-in, and it would still be wrong here: consent from a
  parent under stress, for a purpose that survives their own deletion request, for a
  population defined by vulnerability. It would also forfeit the positive above, which is
  worth more than the data.
- **Train on real submissions after pseudonymisation.** Rejected on the same grounds, plus
  a technical one: `pseudonymize` removes a name, not a situation, and a story about a
  specific incident at a specific school remains a story about a specific child.
- **Use `feedback.jsonl` as a reward signal.** Rejected as the sharpest form of ADR-002 D8's
  closed loop; see Decision 4.
- **Mine published social-narrative collections.** Rejected — Decision 8.
- **Skip the corpus; evaluate by clinician spot-check only.** Rejected: with no held-out
  set there is no non-inferiority test, so ADR-006 Decision 6's gate could not be run and
  the default provider could only be swapped on impression.
- **Crowdsource adjudication to non-specialists.** Rejected. Structural conformance is
  already automated (tier 2), so what remains for a human is precisely the part requiring
  professional judgement. Crowd labels would add volume to the axis that does not need it.
- **Fully synthetic labels — teacher generates, teacher judges, no clinician.** Rejected.
  It would produce a model that reproduces the teacher's blind spots with high confidence
  and no way to detect them, and the whole premise of ADR-006 Driver 3 is that the teacher's
  domain judgement is the thing in question.

## Migration / rollout

- **Not yet started.** Proposed; blocked on ADR-006 and ADR-007 acceptance and on a named
  clinical collaborator, since Decisions 2 and 3 are theirs to author.
- **Ratification condition (Proposed → Accepted):** the grid authored and reviewed, the
  rejection-reason taxonomy fixed, the split policy implemented, and a first tranche of ~250
  items adjudicated with a double-adjudicated slice sized for a meaningful agreement figure.
- **Tooling (`KC-15`):** `kc corpus generate|adjudicate|export|card` — deliberately thin, over a
  directory of JSON records outside `<store-root>`, reusing the existing validators rather
  than reimplementing them.
- **Docs to revise on acceptance:** `docs/DPIA.md` (a corpus/adapter custody line and the
  non-personal-by-construction statement), `PRIVACY.md` §8 (a parent-facing sentence that
  their child's story is never used to train), `docs/PARENT_PRIVACY_NOTICE.md` (same, in
  plain language, with a version bump — this is a commitment worth making explicit to a
  parent at consent time), `docs/BACKLOG.md`.
- **Tests, mock data only:** the corpus tooling refuses a path inside `<store-root>`; export
  refuses a record lacking complete provenance; the split assigner never places two records
  sharing an input seed on both sides; a synthetic "real submission" fixture is rejected by
  the ingest guard.
- **Explicitly out of scope:** how the adapter is trained. This ADR governs what may be
  learned from and what must be recorded; the recipe is `KC-17`.
