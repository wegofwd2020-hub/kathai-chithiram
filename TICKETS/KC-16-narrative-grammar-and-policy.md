# KC-16 — `sentence_function` and a collaborator-authored `NarrativePolicy`

**Labels:** P1, quality, clinical
**Status:** 📋 Proposed — design is ungated; **enabling** requires a collaborator-authored policy
**Refs:** `docs/ADR_007_scene_script_v2_authoring_grammar.md` D5, D6, D8; `progress/policy.py` (the pattern to mirror); `docs/PROGRESS_POLICY.md`

## Why
The clinical grammar of a social narrative is absent from the contract. `system_prompt.py`
asks in prose for plain, concrete, positively framed language and for showing the desired
behaviour rather than listing prohibitions — and nothing checks any of it. A story that is
90% instructions to the child is contract-valid today.

The generic literature holds that such a story should *describe* far more than it *directs*,
and expresses this as a ratio. That ratio is a clinical judgement about how much a
particular child should be told what to do. **Engineering must not choose it.**
`progress/policy.py` already establishes the right pattern and says why in its own docstring:
"There is no `DEFAULT_K` and no fallback threshold anywhere in this package, so an
engineer's cutoff cannot reach a child by omission." The same applies here, and for the same
reason.

Making the ratio checkable requires the contract to carry what each scene is *doing* — hence
`sentence_function`. This is also the point at which the clinical intelligence in the system
becomes a reviewable, versioned artefact rather than something diffused into a prompt or,
later, into weights. That is what makes the model programme defensible.

## Acceptance criteria
- Each v2 scene carries `sentence_function ∈ {descriptive, perspective, coaching,
  affirmative}` (required in v2).
- A `NarrativePolicy` type carrying `policy_id`, minimum non-coaching:coaching ratio,
  optional `caption_chars` (which may **only lower** the contract's hard 140 ceiling, never
  raise it), optional maximum scene count, and `enabled`. Constructed and validated the way
  `ProgressPolicy` is — types enforce their own invariants, the loader only constructs them.
- **No `DEFAULT_RATIO`, no fallback, nowhere in the package.** With no policy supplied,
  `sentence_function` is recorded and the ratio is not enforced.
- A `docs/examples/narrative_policy.template.json` shipping `"enabled": false` and
  `"policy_id": "TEMPLATE-replace-me"` with placeholder copy, mirroring
  `progress_policy.template.json`, plus a `docs/NARRATIVE_POLICY.md` authoring guide aimed
  at the collaborator, not at an engineer.
- Rubric validators for the checkable parts of the generation prompt: first person, present
  tense, one idea per scene, absence of idiom/figurative constructions, positive framing
  (desired behaviour rather than prohibition). Each with its own rule id so KC-14 can report
  per rule.
- **Naming (ADR-007 D8):** replace "social stories" with "social narrative" in `README.md`,
  `generation/system_prompt.py`, `docs/BRAND.md` and all parent-facing copy. Social
  Stories™ is a registered trademark denoting a specific methodology with its own training;
  our rubric is *informed by* the published literature and authored by our collaborator, and
  must not be presented as an implementation of someone else's named method.

## Implementation notes
- Mirror `progress/policy.py` closely — the same shape means one thing for a collaborator to
  learn, and the same review discipline applies to both artefacts.
- Whether `sentence_function` is emitted by the model or derived by a classifier over the
  narration is an implementation choice; the contract only requires it be present and
  correct, and a validator may disagree with a claimed label.
- Keep the two policies as separate files for now: `ProgressPolicy` is gated behind ADR-002
  D7 and `NarrativePolicy` is not, so merging them would drag an ungated capability behind a
  gate. Revisit if the collaborator finds two files a genuine burden.
- The trademark rename carries a short legal note; budget a counsel opinion if commercial
  launch is near.
- OpenSpec docstrings; no bare `except`; validator failures logged as rule ids only.

## Tests (mock data only)
- A coaching-heavy fixture rejected under a supplied policy and **accepted with none
  supplied** — the no-defaults guarantee, asserted.
- A policy attempting to raise `caption_chars` above 140 rejected at construction.
- A policy with a duplicate `policy_id` or an out-of-range ratio rejected, not best-guessed.
- Each rubric validator fires on a fixture violating exactly its rule and on no other.
- Parity test: every `MUST`/`MUST_NOT` string that is mechanically checkable has a
  corresponding validator, so the prose and the code cannot drift.
