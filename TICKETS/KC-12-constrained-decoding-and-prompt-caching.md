# KC-12 — Grammar-constrained decoding, and cache the schema prompt prefix

**Labels:** P1, quality, cost
**Status:** 📋 Proposed — prompt caching is independently shippable **now**; constrained decoding depends on KC-13
**Refs:** `docs/ADR_006_domain_model_strategy.md` D4 (L1), C1; `generation/scene_script_prompt.py`, `generation/generator.py`, `wegofwd_llm/anthropic_provider.py`

## Why
Two problems with one ticket, because they touch the same file.

**1. The prompt is rebuilt from scratch on every attempt.**
`build_scene_script_system_prompt` serialises the entire `SCENE_SCRIPT_SCHEMA_V1`
(`json.dumps(..., indent=2, sort_keys=True)`, ~150 lines) plus the full safety prompt, the
cross-field rules and a worked `EXAMPLE_SCENE_SCRIPT` into **every** request — including
each of up to three repair attempts, where the only thing that changes is a one-line
`repair_feedback` suffix. There is no prompt caching. This is a large, entirely avoidable
recurring cost on the path running in production today, and it is a day of work to fix.

**2. Contract validity is being solved by retrying.**
`generate_scene_script` loops up to three times: parse with a brace-slice heuristic
(`text[text.find("{") : text.rfind("}")+1]`), validate, and on failure feed `best_match`'s
*first* failing rule back as prose and re-ask. It works, but it spends a full generation to
discover a missing comma, reports one rule at a time, and leaves a residual failure mode
(`generation.exhausted`) that a parent experiences as "it didn't work."

Grammar-constrained sampling removes the class. If the decoder cannot emit a token that
leaves the schema, an invalid script is not rejected — it is unrepresentable. This is the
capability ADR-006 identifies as C1: a decoder constraint, not something model scale buys.
It matters most for the eventual local model, but it is worth having on any path, and it
must land before KC-14 so that contract validity stops being a variable in every
measurement.

## Acceptance criteria
- The static prefix (safety prompt + schema + cross-field rules + example) is separated
  from the volatile suffix (`child_token`, `repair_feedback`) and marked cacheable, so a
  repair attempt re-sends only what changed. Measured token cost per story falls; a test
  asserts the prefix is byte-identical across attempts.
- Where the provider supports it, the scene script is produced under a schema constraint
  (structured output / grammar-constrained sampling) rather than by free-text emission plus
  a brace-slice parse.
- The constraint is generated from `SCENE_SCRIPT_SCHEMA_V2` (KC-13) — never hand-written —
  so schema and grammar cannot drift.
- With the constraint active, contract validity is **100%** across the `mock_scripts.py`
  mutation battery and mean attempts per story is ≈ 1.0.
- The repair loop **stays** as the fallback for providers without constraint support, and
  `generation.exhausted` remains a real error path. Constraint support is a provider
  capability, not an assumption.
- The cross-field rules the schema cannot express (caption == narration, contiguous
  indices, `total_duration_s` sum, no `content_flags`) still go through
  `validate_scene_script` after generation. **The grammar narrows the space; it does not
  replace validation.**

## Implementation notes
- Prompt caching is a provider-level concern; the split into prefix/suffix belongs in
  `scene_script_prompt.py` and is useful regardless of which provider consumes it. Ship it
  first, alone.
- Add constraint support as an optional capability on the provider seam (e.g. an optional
  `response_schema` on `LLMRequest` plus a capability flag), so `LLMProvider` keeps its
  single-method shape for providers that do not support it.
- Do not weaken `_extract_scene_script`'s tolerance while a fallback path exists.
- `test_prompt_includes_every_must_and_must_not_rule` must keep passing — the prefix split
  must not drop a rule.
- OpenSpec docstrings; no bare `except`; never log raw story text or prompt content
  (`ProviderRequestRecord` still records lengths only).

## Tests (mock data only)
- Prefix byte-identical across attempts 1–3; suffix differs only in the feedback line.
- Token/character count per repair attempt strictly lower than the current implementation.
- Under the constraint, a `ScriptedProvider` cannot produce a script that fails structural
  validation across the full mutation battery.
- A provider **without** constraint support still takes the repair path and still reaches
  `generation.exhausted` on a persistently bad reply.
- Cross-field rules still fire under constrained generation (a grammar-valid script with
  `caption != narration` is still rejected).
