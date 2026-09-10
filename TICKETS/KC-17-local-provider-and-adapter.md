# KC-17 — `LocalModelProvider` + LoRA adapter on a permissively-licensed base

**Labels:** P1, cost, privacy
**Status:** 📋 Proposed — **GATED**: opens only when KC-14 is green with a recorded baseline
**Refs:** `docs/ADR_006_domain_model_strategy.md` D2, D5, D6, D7; `wegofwd_llm/provider.py`, `wegofwd_llm/gateway.py`, `wegofwd_llm/anthropic_provider.py`; `docs/DPIA.md` R2; KC-6

## Why
`docs/DPIA.md` R2 rates provider retention/training **Low residual** — but explicitly on the
operational precondition that `ANTHROPIC_ZDR_API_KEY` is provisioned against an org
Anthropic has confirmed as ZDR, which KC-6 records "is not something the client can verify."
That is a well-managed risk resting on an unverifiable assertion.

An in-process model removes the processor entirely. There is no third party, no credential
to misprovision, and the no-training / zero-retention claim becomes verifiable **by
construction** — the process makes no network call — rather than by attestation. R2 changes
from a managed risk to *not applicable*. That, not cost, is why this ticket exists.

Cost follows: marginal cost per story approaches zero, which is what makes "a story written
for *this* child" economically real at family scale.

## Acceptance criteria
- A `LocalModelProvider` implementing `LLMProvider.complete` — one method, per the seam.
- It stamps `ProviderConfig(provider_id="local:<model>-<adapter-version>", no_training=True,
  zero_retention=True)` where both flags are true **structurally**, asserted by a test that
  the provider holds no HTTP client and opens no socket. There is no local analogue of
  `build_zdr_provider`, and none is invented.
- **The gateway guards are unchanged.** `is_privacy_compliant` still gates dispatch and
  `count_identifiers` still hard-stops immediately before it. Pseudonymisation is **not**
  relaxed because the model is local — defence in depth does not get cheaper when one layer
  improves.
- Base model per ADR-006 D2: `Phi-4-mini-instruct` (≈3.8B, MIT) as the default emitter,
  `Phi-4` / `Phi-4-reasoning` (≈14B, MIT) as the optional larger rung. Licence bar is MIT
  **or** Apache-2.0 with no field-of-use restriction and no acceptable-use policy a third
  party can revoke. Llama-family and the Kimi/GLM model-specific licences are excluded on
  licence grounds regardless of quality.
- QLoRA SFT on the KC-15 gold set, retrained and re-scored per tranche to produce a learning
  curve, with ADR-008 D7's stopping rule applied. Optional preference tuning on **synthetic**
  accept/reject pairs only.
- Every training run records base model + revision, adapter version, corpus version, rubric
  version, hyperparameters and the resulting KC-14 report. An adapter without a linked
  report cannot be promoted.
- **The gate (ADR-006 D6):** the local model becomes the *default* provider only on
  non-inferiority to the recorded baseline on blind clinician preference, with contract
  validity at 100% and no safety regression. Until then it ships opt-in behind a flag. No
  axis may be waived by the person who trained the model.
- The Anthropic provider stays a live, tested fallback path — not a removed one.
- `MUST`/`MUST_NOT` parity extends to the local path rather than being duplicated:
  `test_prompt_includes_every_must_and_must_not_rule`'s guarantee must hold for whatever
  conditioning the local path uses.

## The acceptable failure outcome
If the tuned 3.8B loses the preference test, **do not ship it as default and do not keep
training**. Ship the two-tier split: local model for the constrained emitter step
(structure, vocabulary, lowering), frontier model for the shaping step (parent paragraph →
narrative arc). That still moves most tokens in-house, still cuts cost substantially, and
leaves the sovereignty win partial but real. It is a worse outcome than a clean win and a
much better one than a year spent chasing parity.

## Implementation notes
- Serving runtime (vLLM / llama.cpp / in-process) is an implementation choice behind the
  provider; the seam, the licence bar and the acceptance gate are what is fixed.
- Constrained decoding (KC-12) is where the local model earns its keep — a small model under
  a grammar is structurally equivalent to a large one, so parameters buy phrasing and
  judgment, not syntax.
- The open-weight licence covers **weights, not training data**; no checkpoint warrants its
  pretraining corpus. Record this honestly in `docs/DPIA.md` and keep the model's job narrow.
- Adapter weights are a project asset with their own custody (KC-15), outside `<store-root>`,
  not swept by retention.
- **Do not** fine-tune for safety refusal (it would put a stochastic function on a path
  ADR-001 D5 requires to be deterministic), **do not** give the model harm-triage authority,
  and **do not** relax the KC-7 human review gate.

## Tests (mock data only)
- The provider holds no client and opens no socket; a socket-blocking test passes.
- `is_privacy_compliant` and the residual-identifier hard stop still fire on the local path.
- A non-compliant local config is refused before any story text is touched.
- An adapter with no linked KC-14 report cannot be promoted to default.
- Both providers satisfy the same `MUST`/`MUST_NOT` parity assertion.
