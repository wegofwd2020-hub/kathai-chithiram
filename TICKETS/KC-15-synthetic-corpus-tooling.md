# KC-15 — `kc corpus`: synthetic scenario grid, clinician adjudication, dataset card

**Labels:** P1, quality, privacy, clinical
**Status:** 📋 Proposed — **GATED** on a retained clinical collaborator (the grid, personas and taxonomy are theirs to author)
**Refs:** `docs/ADR_008_training_corpus_provenance.md`; `CLAUDE.md` ("no real child data"); `PRIVACY.md` §8; `docs/DPIA.md`

## Why
KC-14 needs a held-out set to score against and KC-17 needs a gold set to learn from.
Neither may come from the data we hold. Every delivered story is a parent's account of their
own child under Art. 6(1)(a)/9(2)(a) consent for a stated purpose; training is a different
purpose, and one that outlives deletion — a model does not forget when `delete_story` runs.
A crypto-shredded corpus and a model trained on it are not the same object, and only one of
them can be destroyed.

Building from nothing turns out to be the advantage: a wholly synthetic corpus is the only
kind whose provenance can be stated completely, and "what is this model trained on?" is a
question a DPO, a school district and a parent will each ask.

## Acceptance criteria
- `kc corpus generate | adjudicate | export | card`, operating on a directory **outside
  `<store-root>`**; the tooling refuses a path inside it.
- Corpus items are instantiated from a collaborator-authored **scenario × persona grid**,
  with coverage stated up front so a gap is visible rather than unknown. Personas are
  professional composites, recorded as such, never derived from a real child known to the
  project.
- Inputs are deliberately roughened to resemble real parent writing — typos, run-ons,
  hedging, missing context, two children mentioned at once. This is the corpus's central
  validity threat and the mitigation belongs in the generator, not in a note.
- Three-tier labelling: teacher generates → KC-13/KC-16 validators filter → collaborator
  adjudicates **accept / edit / reject**, rejections drawn from a **closed reason taxonomy**.
  Only accepted and edited items enter the gold set; rejected items are retained as the
  negative half of preference pairs.
- Train/dev/test assigned **by grid cell and input seed before generation**, so no
  paraphrase of a training input can reach the test set. Whole grid cells reserved unseen,
  to measure generalisation to situations the grid does not contain.
- Every record carries complete provenance: grid cell, input generator version, teacher
  model and version, prompt version, rubric version, opaque adjudicator id, decision,
  reason, timestamps, and the edit diff where one exists. `export` refuses a record with
  incomplete provenance.
- `DATASET_CARD.md` generated and kept current: composition, grid coverage, who adjudicated,
  agreement on the double-adjudicated slice, known gaps, and the explicit statement that no
  real child data is present.
- **Hard prohibitions, asserted by test:** no real submission enters the corpus in any form,
  including pseudonymised or paraphrased; `review.json` decisions on real families' stories
  are never a training source; `feedback.jsonl` (`prompt_level`, `completed`,
  `mood_checkin`) is excluded from every objective, loss and filter.
- Build in tranches of ~250 with ADR-008 D7's stopping rule applied — retrain, re-score,
  stop when the eval curve flattens. Clinician hours are the binding budget constraint.

## Implementation notes
- Thin tooling over a directory of JSON records; reuse the existing validators rather than
  reimplementing them.
- Corpus and adapter are **project assets, not story artefacts**: KC-1 hard-delete and the
  retention sweep must **not** be extended over them. A versioned training asset a sweep can
  silently mutate is worse than useless. Version, checksum and access-control them instead.
- The rejection taxonomy is the highest-leverage artefact here: a reason that recurs is a
  KC-16 validator waiting to be written, and each one written makes the next tranche cheaper.
- OpenSpec docstrings; no bare `except`.
- Docs on completion: `docs/DPIA.md` (corpus/adapter custody; non-personal by construction),
  `PRIVACY.md` §8 and `docs/PARENT_PRIVACY_NOTICE.md` (a plain-language commitment, with a
  version bump, that a child's story is never used to train — worth stating to a parent at
  consent time).

## Tests (mock data only)
- The tooling refuses a corpus path inside `<store-root>`.
- A synthetic "real submission" fixture is rejected by the ingest guard.
- `export` refuses a record lacking any provenance field.
- The split assigner never places two records sharing an input seed on both sides.
- A grep-level assertion that no training or export path reads `feedback.jsonl` or
  `review.json`.
