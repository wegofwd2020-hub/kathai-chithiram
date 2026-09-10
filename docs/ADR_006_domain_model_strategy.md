# ADR-006 — Domain model strategy: capability layers before weights, on a permissively-licensed small base

**Date:** 2026-09-10
**Status:** Proposed
**Branch at decision:** main

---

## Context

Generation today runs one path: `intake/service.py` → `wegofwd_llm/gateway.run_generation`
→ `AnthropicProvider` (`DEFAULT_MODEL = "claude-opus-4-8"`) → `generate_scene_script`'s
validate-and-repair loop, bounded at three attempts. The full ~150-line
`SCENE_SCRIPT_SCHEMA_V1` plus a worked example is re-serialized into the system prompt on
**every attempt, including repairs**. Repair is text-feedback-only: `best_match` reports
the *first* failing rule, the detail string is appended to the prompt, and the model is
re-asked. There is no prompt caching, no structured-output/tool use, no few-shot bank, and
no evaluation of generation *quality* — only of contract validity.

Four independent pressures now point at owning the model rather than renting it:

1. **Unit economics.** Every story costs a frontier-model call, and a story that needs two
   repair rounds costs three. The cost per story is roughly flat in model price and rises
   with contract strictness — exactly the wrong gradient for a product whose whole thesis
   is that *every* family gets a story written for *their* child.
2. **Data sovereignty, and the honest state of DPIA R2.** `KC-6` established that
   Anthropic's no-training / zero-retention posture is an **org-level property of the
   credential**, not a per-request flag, so `build_zdr_provider` fails closed on a
   dedicated `ANTHROPIC_ZDR_API_KEY`. `docs/DPIA.md` R2 rates the residual **Low** — but
   explicitly "on the operational precondition that the key is provisioned against an org
   Anthropic has confirmed as ZDR," which "is not something the client can verify." That
   is a well-managed risk resting on an unverifiable assertion. An in-process model removes
   the processor entirely: there is no third party, no credential to misprovision, and the
   claim becomes verifiable by construction (no egress) rather than by attestation. **This
   is the strongest argument in this ADR and it is not the cost argument.**
3. **Domain capability.** The system prompt encodes `MUST`/`MUST_NOT` as prose and a test
   asserts each string appears in the built prompt. That keeps the prompt in step with
   `CONTENT_SAFETY.md`; it does not make the model *good* at social-narrative authoring for
   a child with a particular support profile. Nothing in the repository measures whether it
   is.
4. **IP.** The defensible asset in this product is not the renderer and not the CLI. It is
   the pairing of a clinician-authored rubric with a corpus and a model that embodies it.

The framing that prompted this ADR was "which base LLM should we start with." Taken
literally that question is premature, because it presumes the missing capability lives in
weights. It mostly does not.

### The capability decomposition

"Understands special-needs story authoring" is five separable capabilities. Only one of
them is learned:

| # | Capability | Where it actually lives |
|---|---|---|
| C1 | Emit structurally valid scene-script JSON | **Decoder constraint.** A grammar-constrained sampler cannot emit a token that leaves the schema. Scale does not help; constraint makes the failure unrepresentable. |
| C2 | Choose art the renderer can actually draw | **The contract.** `setting`, `props`, `characters[].pose`, `characters[].expression` and `audio.sfx` are unconstrained strings today; `scene_art_hints.py` keyword-matches them and silently degrades to `Background.CALM` / `Gesture.REST`. The model has no way to learn a vocabulary that is never stated and never enforced. ADR-007. |
| C3 | Social-narrative grammar — first person, present tense, literal, positively framed, correct balance of describing vs. coaching | **Mostly validators.** Person, tense, idiom, sentence function and ratio are checkable in code. What is left over is a small supervised signal. |
| C4 | Situational judgment — turning a parent's messy paragraph into the right arc, at the right granularity, for *this* child's support profile | **Weights.** This is the only genuinely learned capability, and it is the whole product. |
| C5 | Recognise risk of harm in an intake | **Not a model decision.** ADR-001 D5: "automation is never the sole safeguard." A recall-biased router to a human, never a classifier with authority. |

C1–C3 are engineering with a clinician in the loop and need no training run. They also
raise the floor for *any* model, including the current Anthropic one, which is why they
come first. C4 is what a tuned model buys. C5 is deliberately excluded from the model's
job.

## Decision

**Decision 1 — Do not pretrain. Adapt a permissively-licensed open-weight base with
parameter-efficient fine-tuning, behind the existing seam.**
Pretraining a base model is a seven-to-eight-figure exercise producing something worse
than a free 4B checkpoint at everything except the narrow thing we care about, which we
can reach with a LoRA adapter for the price of a laptop. Continued pretraining on
domain text is also rejected: we have no domain corpus and, per ADR-008, will never have a
real one. The program is: **contract → constraint → validators → corpus → adapter.**

**Decision 2 — Default base: `Phi-4-mini-instruct` (≈3.8B, MIT), with `Phi-4` /
`Phi-4-reasoning` (≈14B, MIT) as the optional larger rung of the same ladder.**
Selection criteria, in priority order: (a) a licence with no field-of-use restriction and
no acceptable-use policy a third party can revoke; (b) small enough that inference is a
fixed local cost, not a variable one; (c) strong instruction-following on structured
output, which is the job; (d) a family, so the small and large rungs share a tokenizer and
a tuning recipe and are one dependency rather than two.

Phi-4-mini is the smallest checkpoint that can plausibly do the job and it satisfies the
stated MIT constraint literally. Sizing the emitter at ~4B is deliberate: under
constrained decoding (Decision 4, layer L1) the structural burden is carried by the
grammar, so parameters buy phrasing and judgment, not syntax.

**Decision 3 — Record that MIT is the *stated* constraint but probably not the *right*
one; treat "MIT **or** Apache-2.0" as the real bar.**
Three things worth having written down before this choice hardens:

- **MIT grants copyright permissions and is silent on patents. Apache-2.0 grants an
  express patent licence plus defensive termination.** For a commercial product, Apache-2.0
  is *strictly more protective*, not a step down. Asking for "MIT specifically" optimises
  for the wrong axis. Qwen3.8-27B, SmolLM3, OLMo and Granite sit in the Apache-2.0 class
  and should not be excluded by a literal reading of the constraint.
- **The licence covers the weights, not the training data.** No open-weight checkpoint
  ships a warranted provenance for its pretraining corpus. This is a fact for
  `docs/DPIA.md` to record honestly, not one a licence can fix — and it is a reason to
  keep the model's job narrow (C4) and keep safety in validators and humans.
- **Excluded on licence grounds regardless of quality:** Llama 4 (community licence,
  EU-specific restrictions, and an acceptable-use policy whose terms a third party can
  change) and the Kimi/GLM model-specific licences. A product that promises continuity of
  care to a family cannot rest on a licence another party may revise. **DeepSeek V4 is
  genuinely MIT** but at 304B–1.7T is not self-hostable at this budget; it is a *teacher*
  candidate (ADR-008), not a base.

**Decision 4 — Sequence capability layers before weights; each layer ships and reverts
independently.**

| Layer | What lands | Needs ML? | Benefits the current Anthropic path too |
|---|---|---|---|
| **L0** | Scene-script v2: enumerated art vocabulary, `author`/`perspective`/`intent`, `sentence_function` (ADR-007) | No | Yes |
| **L1** | Grammar-constrained decoding against the v2 schema | No | Partially (structured output) |
| **L2** | Rubric validators — person, tense, idiom, sentence-function ratio — with the clinical *values* policy-supplied | No | Yes |
| **L3** | Synthetic, clinician-adjudicated corpus + dataset card (ADR-008) | No | Yes (evaluation) |
| **L4** | LoRA SFT of Phi-4-mini on the gold set; second `LLMProvider` concrete | Yes | — |
| **L5** | Preference tuning from adjudicated accept/reject pairs on the **synthetic** corpus only | Yes | — |

L0–L2 are the majority of the quality gain and none of them is a training run. If the
program stops after L2 it has still made the product materially better and cheaper to
operate. That is the intended property.

**Decision 5 — A local model is a second `LLMProvider` concrete, and it changes the
provider posture from asserted to structural.**
`LLMProvider` is a single method (`complete(LLMRequest) -> LLMResponse`), so a local
provider is a small module. What does *not* transfer is `build_zdr_provider`: ZDR-by-
credential has no local analogue. A `LocalModelProvider` instead stamps
`ProviderConfig(provider_id="local:phi-4-mini-…", no_training=True, zero_retention=True)`
where both flags are true **because the process makes no network call**, asserted by a test
that the provider holds no client and opens no socket. `docs/DPIA.md` R2 is then rewritten
from "Low, on an operational precondition the client cannot verify" to **not applicable —
no third-party processor** for stories generated on this path. The two gateway guards
(`is_privacy_compliant`, then `count_identifiers` immediately before dispatch) stay exactly
as they are; pseudonymisation is not relaxed because the model is local. Defence in depth
does not get cheaper when one layer improves.

**Decision 6 — Evaluation gates the default, not judgement.**
A `kc eval` harness scores four axes against a held-out slice of the ADR-008 corpus:
(i) **contract validity** — must be 100% under L1, and anything less is a grammar bug, not
a model result; (ii) **rubric conformance** — the L2 validators, reported per rule so a
regression is attributable; (iii) **blind clinician preference** against the Anthropic
baseline, paired and shuffled; (iv) **safety red-team pass rate** on an adversarial intake
suite. The tuned local model becomes the *default* provider only on **non-inferiority to
the current path on (iii)** with (i) at 100% and no regression on (iv). Until then it ships
opt-in behind a flag. No axis may be waived by the person who trained the model.

**Decision 7 — Hard prohibitions, restated for the ML context.**
These are inherited from ADR-001/ADR-002 and `CONTENT_SAFETY.md`; they are repeated here
because a training programme is exactly the context in which each is tempting.

- **No real child story is ever a training example.** Corpus is synthetic and
  clinician-adjudicated (ADR-008). This is not a retention question; the artefacts are
  encrypted, swept and crypto-shredded, and none of that would make training on them
  acceptable.
- **No child feedback becomes a reward signal.** `feedback.jsonl`'s `prompt_level`,
  `completed` and `mood_checkin` must never enter a preference objective. A model optimised
  to raise a child's recorded mood is precisely the closed auto-adjustment loop ADR-002 D8
  rejects, and it is worse than the loop ADR-002 was written about, because it is opaque.
- **No model-mediated harm triage** (ADR-001 D5). The `CONTENT_SAFETY.md` §4 risk-of-harm
  path remains the largest unbuilt safety item; when built it is a recall-biased router to
  a person with a defined protocol, and a tuned model does not earn it authority.
- **The human review gate (KC-7 / `CONTENT_SAFETY.md` §6) does not relax.** Nothing in this
  ADR is an argument for automating approval.
- **No generative video.** The renderer's determinism is what makes `guard_render`'s flash
  and high-contrast-oscillation limits a *guarantee* rather than a sample statistic, and it
  is why `video/adapter.py` correctly stamps no C2PA/SynthID signature. A diffusion model
  in that position would forfeit both properties. Better animation comes from a larger
  drawable vocabulary (ADR-007), not from a video model.

## Consequences

### Positive

- The single largest quality lever (L0/L1/L2) needs no GPU, no corpus and no clinician
  sign-off to *begin*, and improves the Anthropic path while the local path is built.
- DPIA R2 changes character rather than degree: from a managed risk resting on an
  unverifiable attestation to no processor at all.
- Marginal cost per story on the local path approaches zero, which is what makes the
  "a story for *this* child" promise economically real at family scale.
- The clinical intelligence lands as reviewable artefacts — a rubric, a grid, a ratio
  policy — mirroring `ProgressPolicy`'s discipline, so a regulator, a clinician or a parent
  can be shown *what* the system believes, which is not true of a system whose judgement
  lives only in weights.
- The `LLMProvider` seam is already the right shape; this ADR spends its option value
  rather than requiring new abstraction.

### Negative

- The repair loop, prompt assembly and offline path all assume free-string art values;
  ADR-007's v2 contract touches `scene_builder.py`, `scene_art_hints.py`, both reference
  renderers and the conformance suite. That is real, unglamorous migration work ahead of
  any model benefit.
- Self-hosting moves an availability and patching burden in-house that Anthropic currently
  carries. For a single-machine prototype this is small; it does not stay small.
- A 3.8B model may simply lose the Decision 6 preference test. The plan must be willing to
  ship the two-tier outcome (local emitter, remote shaper) and call it success.
- Two generation paths means two things to keep in step with `CONTENT_SAFETY.md`. The
  existing `test_prompt_includes_every_must_and_must_not_rule` pattern must be extended to
  the local path rather than duplicated.
- Owning a model means owning its failures. "The provider's model changed" stops being an
  available explanation.

### Neutral

- Serving stack (vLLM / llama.cpp / an in-process runtime) and the constrained-decoding
  backend are implementation choices behind the provider; this ADR fixes the seam, the
  licence bar and the acceptance gate, not the runtime.
- The choice of teacher for corpus generation (ADR-008) is independent of the choice of
  base, and a frontier teacher remains appropriate even for a small student.

## Alternatives considered

- **Pretrain a base model from scratch.** Rejected. Cost is three to five orders of
  magnitude above the budget, and the result would be worse at general language than a free
  checkpoint while being no better at C4, which comes from the corpus and the rubric.
- **Continued pretraining on domain text.** Rejected. There is no lawful, ethical corpus of
  personalised children's social narratives: published ones are copyrighted and often
  trademark-bound, and real submissions are permanently off-limits (Decision 7). Continued
  pretraining also spends far more compute than SFT for a narrow structured task.
- **Prompt engineering only, on a small open model.** Not rejected — it is the **baseline
  arm of the Decision 6 evaluation**, and it may win. L0–L2 must land before it can be
  fairly measured; running the comparison before then would measure the missing contract,
  not the missing weights.
- **Stay on the frontier API indefinitely.** The honest status quo, and it stays the
  fallback and the teacher. It does not answer the sovereignty argument (Driver 2) and does
  not become an owned asset (Driver 4).
- **A larger MIT base (DeepSeek V4).** Rejected as a *base*: not self-hostable at this
  budget, so it would reintroduce a third-party processor and defeat Driver 2. Retained as
  a teacher option.
- **Fine-tune for safety refusal.** Rejected explicitly. Making refusal a learned behaviour
  would place a stochastic function on the safety path where ADR-001 D5 requires a
  deterministic one, and would make the refusal boundary untestable.

## Migration / rollout

- **Not yet started.** This ADR is Proposed; nothing in it has landed.
- **Ratification condition (Proposed → Accepted):** ADR-007 accepted and L0 merged, plus a
  named clinical collaborator engaged for the rubric — the same "the collaborator is a
  precondition, not a review afterthought" bar ADR-001 D6 sets. A model may not be selected
  by an engineer alone, because the acceptance test (Decision 6 axis iii) is a clinical
  judgement.
- **Tickets, in dependency order:** `KC-13` (v2 art-vocabulary registry — do this first),
  `KC-12` (grammar-constrained decoding; the prompt-caching half is shippable immediately),
  `KC-16` (narrative grammar + `NarrativePolicy`), `KC-15` (synthetic corpus tooling —
  gated on a collaborator), `KC-14` (`kc eval` harness). `KC-17` (local provider + LoRA
  adapter) opens only when `KC-14` is green with a recorded baseline.
- **Docs to revise on acceptance:** `docs/DPIA.md` R2 and §5 (a local path removes a
  processor and adds a model-artefact custody question); `PRIVACY.md` §6 (LLM provider
  handling gains a "processed on our own hardware" case); `docs/CONTENT_SAFETY.md` §5
  (enforcement point 1 becomes prompt **plus** grammar **plus** rubric validators);
  `docs/BACKLOG.md` (new milestone).
- **Tests, mock data only:** a local provider that opens no socket; a grammar that admits
  no invalid script across the existing `mock_scripts.py` mutation battery; parity between
  `MUST`/`MUST_NOT` and whatever the local path's conditioning is; and an eval harness whose
  fixtures are synthetic personas, never a real submission.
- **Explicitly out of scope for this ADR:** the risk-of-harm handling path
  (`CONTENT_SAFETY.md` §8), which is a safeguarding design owned with a professional, not a
  modelling problem, and must not be folded into this programme.
