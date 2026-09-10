# KC-14 — `kc eval`: a generation-quality harness that gates the default provider

**Labels:** P1, quality, safety
**Status:** 📋 Proposed — depends on KC-12, KC-13, KC-16; **must record a baseline before any adapter exists**
**Refs:** `docs/ADR_006_domain_model_strategy.md` D6; `docs/ADR_008_training_corpus_provenance.md` D6; `review/`, `generation/`

## Why
Nothing in this repository measures whether a generated story is *good*. 641 tests measure
whether it is *valid*: schema conformance, cross-field rules, render safety, no identifier
leak. Those are necessary and they are not the same thing. A contract-valid, guard-passing,
seizure-safe story can still be paced wrong for the child, directive-heavy, abstract where
it should be concrete, or set in the wrong room.

The only human quality signal the system captures today is the free-text `reason` on a
`review.json` **rejection** — and a rejected story is then left undelivered and swept by
retention, so even that is not retained. There is no way to answer "did that prompt change
help?" and, more urgently, no way to answer ADR-006's question: is a tuned local model as
good as the frontier model it would replace? Without this harness the default provider
could only be swapped on impression, which is not an acceptable basis for a change that
reaches children.

The baseline must be recorded **before** an adapter exists. A baseline measured after
training, by the person who trained, is not a baseline.

## Acceptance criteria
- `kc eval --split dev|test --provider <id>` scores a corpus split (KC-15) on four axes and
  writes a versioned report:
  1. **Contract validity** — pass rate through `validate_scene_script`. Under KC-12 this
     must be **100%**; anything less is a grammar defect, reported as such, not as a model
     result.
  2. **Rubric conformance** — the KC-16 validators, **reported per rule id** so a regression
     is attributable to a specific rule rather than to a single blended score.
  3. **Blind clinician preference** — paired against the recorded baseline, presentation
     order shuffled, provider identity hidden from the judge. Reported as a win/tie/loss
     rate with a stated sample size.
  4. **Safety** — pass rate on an adversarial intake suite (distressing situations that must
     be transformed rather than reproduced; out-of-purpose requests that must be refused;
     inputs that must route to the risk-of-harm path once one exists).
- A recorded baseline for the current production Anthropic path on all four axes, dated and
  committed, before any local model is trained.
- **The gate:** a provider becomes the default only on non-inferiority to the baseline on
  axis 3, with axis 1 at 100% and no regression on axis 4. Encoded as a check, not a
  convention.
- **No axis may be waived by the person who trained the model.** The report states which
  axes passed; a failing report cannot produce a default-provider change.
- Runs in CI on the dev split. Axis 3 is necessarily out-of-band (a human judges) and the
  harness records the judgement rather than producing it.
- Evaluation inputs are corpus items only — synthetic, per ADR-008. **No real submission is
  ever an eval item**, including as a held-out example.

## Implementation notes
- Axis 3 needs a small blind-comparison workflow: export paired outputs with identities
  stripped, collect a judgement file back, join on an opaque pair id. Keep it a file-based
  CLI flow; it does not need a UI.
- Report per-rule, not just aggregate — this is what makes axis 2 useful for improving the
  rubric rather than merely scoring it, and it is what turns a recurring rejection reason
  into a validator.
- Version the report against the rubric version, prompt version, provider id and corpus
  version, so two reports are only comparable when those match. A comparison across
  different rubric versions must be refused, not silently produced.
- The adversarial suite is authored **with the collaborator**, not by an engineer. It is a
  clinical artefact.
- OpenSpec docstrings; no bare `except`; the report contains no story text from any real
  submission because no real submission is ever an input.

## Tests (mock data only)
- A deliberately invalid provider scores 0 on axis 1 and the report labels it a grammar
  defect.
- Per-rule reporting: a fixture violating exactly one rubric rule is attributed to that rule
  and no other.
- The pair export strips provider identity and the join is order-independent.
- A report generated against rubric version A refuses comparison with one against version B.
- The gate check fails when axis 3 is absent, rather than passing by omission.
