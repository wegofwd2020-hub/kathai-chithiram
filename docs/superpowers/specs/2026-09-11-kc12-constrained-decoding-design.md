# KC-12 — Constrained decoding and v2 emission — design

Status: proposed (awaiting review)
Date: 2026-09-11
Ticket: KC-12 (LLM Program Plan, Phase 1). Depends on KC-13 (v2 contract, landed).
Shaping ADRs: ADR-006 (Decision 4, layer L1 — "grammar-constrained decoding
against the v2 schema … partially, via structured output"), ADR-007 (the closed
art vocabulary this constrains against).

## Problem

Generation today is a text-in / text-out call through the `wegofwd-llm` seam
followed by a validate-and-repair loop (`generation/generator.py`). Two gaps
remain from Phase 1 of the M3 program:

1. **No decoder constraint.** The model is asked, in the system prompt, to emit a
   single JSON object conforming to the contract, and the pipeline parses and
   validates whatever comes back. Structural violations (a missing field, a wrong
   type, an out-of-vocabulary `setting`) are caught only after the fact and cost a
   repair round trip. The three-attempt repair loop exists precisely because a
   free-form completion cannot be trusted to be structurally valid on the first
   try.

2. **Generation still emits v1.** `generation/scene_script_prompt.py` embeds
   `SCENE_SCRIPT_SCHEMA_V1` and a `schema_version: "1.0"` worked example. KC-13
   landed the v2 schema (closed art vocabulary + `author`/`perspective`/`intent`)
   and the validator understands both majors, but nothing emits v2 yet. Phase 1's
   exit gate requires v2 emission.

The prompt-caching half of KC-12 (marking the static system-prompt prefix
cacheable) already shipped in #101 and is out of scope here.

## Goal and non-goals

**Goal.** Make structural contract violations *unrepresentable at generation
time* on the Anthropic path by constraining the model's output to the v2 JSON
schema, and switch generation to emit v2. Collapse the repair loop toward a
single attempt without removing it as the guarantee of last resort.

**Non-goals.**

- True token-level grammar-constrained sampling. That is L1 in weights (KC-17,
  the local model path) and is not what today's Anthropic path can do. ADR-006
  records this explicitly: the current path realises L1 *partially, via
  structured output*.
- Growing or changing the art vocabulary (that was KC-13; ADR-007 puts vocabulary
  growth out of scope for the mechanism work).
- Removing `validate_scene_script` or the repair loop. Structured output is a
  partial constraint; validation remains the enforcement point and the loop
  remains the fallback.

## Mechanism: Anthropic structured outputs, not forced tool use

The Anthropic Messages API exposes structured outputs through
`output_config.format` with `{"type": "json_schema", "schema": <schema>}`. This
is the current, recommended way to constrain response shape — preferable to a
forced `tool_choice` tool call for this use case, and it guarantees the first
content block is text containing schema-valid JSON, so the existing
`_extract_scene_script` path is unchanged.

Structured outputs enforce **structure only**. The supported JSON-Schema subset
covers exactly what we need for structural conformance and deliberately excludes
the rest:

| Schema feature | In v2 schema | Structured outputs |
| --- | --- | --- |
| object/array/string/number/... types | yes | **enforced** |
| `enum` (the closed art vocabulary) | yes | **enforced** |
| `required` | yes | **enforced** |
| `additionalProperties: false` | yes (every object) | **enforced** (and required) |
| `$ref` / `$defs` (scene, character, audio) | yes | **enforced** |
| `minimum` / `maximum` / `exclusiveMinimum` | yes (fps, durations, flash) | not enforced — stripped |
| `minLength` / `maxLength` | yes (title, caption, narration) | not enforced — stripped |
| `pattern` (schema_version, child_token, locale) | yes | not enforced — stripped |

The Anthropic Python SDK strips the unsupported keywords before dispatch and
would validate them client-side for its own `parse()` helper; we do not rely on
that client-side validation, because **`validate_scene_script` already enforces
every one of those numeric, length, and pattern rules**, plus the cross-field
rules a JSON Schema cannot express at all (caption equals narration, sequential
scene indices, `total_duration_s` equals the sum of scene durations, no
`content_flags`, `intent: "experiential"` gated).

This is the clean division ADR-006 anticipated: the closed enums and the object
shape become a decoder constraint; everything else stays a validator. The
constraint removes the structural failures that dominated the repair loop, so
mean attempts collapse toward 1 — but a scene whose caption drifts from its
narration still fails validation and still triggers one repair, which is correct.

The v2 schema uses `$defs`/`$ref`, which structured outputs support natively, so
no schema inlining or flattening is required.

## Seam contract change

The `wegofwd-llm` seam stays provider-agnostic. `LLMRequest` gains one optional
field:

```python
@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    config: ProviderConfig
    system_prompt: str = ""
    system_prefix: str = ""
    output_schema: dict[str, Any] | None = None   # new
```

Contract wording: `output_schema`, when set, is a JSON Schema the reply must
conform to. A provider that supports constrained/structured output MUST return a
value satisfying it; a provider that does not (the offline provider, a future
local provider before it grows the capability) ignores the field and the caller's
validate-and-repair loop remains the guarantee. `LLMResponse` is unchanged — a
structured provider serialises the structured object back to JSON text, so the
rest of the pipeline does not change.

The field is defaulted and the dataclass is frozen, so this is backward
compatible: every existing caller and provider keeps working untouched.

## Components and data flow

Unchanged: `run_generation`'s privacy guarantees (posture check, pseudonymise,
residual-identifier guard, audit record) all run exactly as today. Constrained
decoding does not relax pseudonymisation — defence in depth does not get cheaper
because the output is constrained.

1. **`generation/generator.py`** — `generate_scene_script` passes
   `output_schema=SCENE_SCRIPT_SCHEMA_V2` into `run_generation`. The repair loop
   is unchanged in shape; it simply converges faster.
2. **`wegofwd_llm/gateway.py`** — `run_generation` gains an `output_schema`
   parameter and forwards it into the `LLMRequest` it constructs. No other change.
3. **`wegofwd_llm/anthropic_provider.py`** — when `request.output_schema` is set,
   merge `"format": {"type": "json_schema", "schema": request.output_schema}` into
   the `output_config` dict that already carries `effort`. `stop_reason` handling
   is unchanged: a refusal is still a domain error; structured output does not
   change the refusal contract on Opus 4.8. When `output_schema` is `None`, the
   call is byte-for-byte what it is today.
4. **`generation/scene_script_prompt.py`** — swap `SCENE_SCRIPT_SCHEMA_V1` for
   `SCENE_SCRIPT_SCHEMA_V2`; replace `EXAMPLE_SCENE_SCRIPT` with a v2 example
   (`schema_version: "2.0"`, `author`/`perspective`/`intent`, closed-vocabulary
   `setting`/`props`/`pose`/`expression`) that passes `validate_scene_script`
   under v2; add the new grammar rules to `_cross_field_rules` (require
   `author`/`perspective`/`intent`; instruct `intent: "instructional"` because
   `experiential` is gated). The in-prompt schema stays (it carries the
   cross-field rules and communicates the vocabulary to the model), and it stays
   inside the cacheable prefix.

```
generate_scene_script
  builds v2 system prefix (cached) + passes SCENE_SCRIPT_SCHEMA_V2
    → run_generation  (privacy guards unchanged) forwards output_schema
      → AnthropicProvider.complete  sets output_config.format = json_schema(schema)
        → model returns schema-valid JSON as text
      → _extract_scene_script (unchanged) → validate_scene_script (unchanged)
    → repair only on cross-field misses the schema cannot express
```

## Why the in-prompt schema and `output_config.format` both carry the schema

They are complementary. The in-prompt v2 schema is what the model *reads* to
choose renderable art and to satisfy the cross-field rules; it sits in the cached
prefix, so it is cheap on repeat attempts. `output_config.format` is what the
decoder is *constrained* by. Sending both costs some tokens; a later
optimisation could trim the in-prompt copy once we have data on whether the model
needs it to choose good vocabulary. Not doing that now — correctness first,
measured trimming later. (Structured-output schemas are compiled and cached
server-side for 24 hours, so the constraint itself is not re-compiled per
request.)

## Error handling

- **Provider without structured output** (offline provider today): ignores
  `output_schema`, returns free-form text, and the repair loop does its existing
  job. No new failure mode.
- **Refusal**: unchanged — `ProviderResponseError` as today.
- **Constrained-but-invalid**: the model can still emit JSON that satisfies the
  structure yet violates a cross-field rule. `validate_scene_script` rejects it
  and the loop repairs it, exactly as now.
- **Malformed JSON despite the constraint**: `_extract_scene_script` raises
  `SceneScriptGenerationError` as today; the loop retries. In practice structured
  output makes this path cold, but it is not removed.

Every function keeps raising domain-specific errors with context; no bare
excepts; no new swallowed exceptions.

## Testing (mock data only; no real child data; no live model calls)

Mirroring source layout under `tests/`:

- **Seam contract** — `LLMRequest` defaults `output_schema` to `None`
  (backward-compat); a request carrying a schema round-trips it.
- **Gateway** — `run_generation` forwards `output_schema` into the `LLMRequest`
  handed to the provider (assert via a spy/fake provider), and does so *after*
  the privacy guards (a residual-identifier case still raises before dispatch).
- **Generator** — with a fake structured provider that returns a valid v2 script,
  `generate_scene_script` succeeds on attempt 1 and passes
  `SCENE_SCRIPT_SCHEMA_V2` through; with a fake that returns a cross-field-invalid
  script once then a valid one, it repairs and succeeds on attempt 2.
- **AnthropicProvider** — with an injected fake client, a request carrying
  `output_schema` sets `output_config.format` to a `json_schema` block wrapping
  that schema (and preserves `effort`); a request without one sends no `format`
  key (byte-for-byte-today assertion); refusal and empty-text handling still
  raise `ProviderResponseError` on the structured path.
- **v2 emission** — the new `EXAMPLE_SCENE_SCRIPT` validates under v2; the built
  prefix embeds the v2 schema and instructs `intent: "instructional"`; a v1
  fixture from `mock_scripts.py` still validates and renders (no regression).

### The exit gate is a live-model measurement — stated honestly

ADR-006/LLM_PROGRAM_PLAN set the Phase-1 exit gate at **100% contract validity
across the `mock_scripts.py` mutation battery, mean attempts per story ≈ 1.0, and
measured per-story token cost down**. That "100% / ≈1.0" number is a property of a
*real* model under the constraint; it cannot be asserted in unit tests without a
live call, and this design does not fabricate it. The test-side proxy is: with a
structured fake that honours the schema, validity is 100% and mean attempts is
1.0 across the mock stories. The real figure belongs in a `kc eval`-style
harness or a manual run against Opus 4.8, recorded separately — not invented here.

## Files touched

- `src/kathai_chithiram/wegofwd_llm/provider.py` — add `output_schema` field.
- `src/kathai_chithiram/wegofwd_llm/gateway.py` — forward `output_schema`.
- `src/kathai_chithiram/wegofwd_llm/anthropic_provider.py` — structured-output branch.
- `src/kathai_chithiram/generation/generator.py` — pass `SCENE_SCRIPT_SCHEMA_V2`.
- `src/kathai_chithiram/generation/scene_script_prompt.py` — v2 schema, v2 example, v2 grammar rules.
- `tests/` — mirrored test files for each of the above.
- `docs/LLM_PROGRAM_PLAN.md` — mark KC-12 done (both halves).
- `docs/SCENE_SCRIPT_CONTRACT.md` / `docs/CONTENT_SAFETY.md` — note structured v2 emission at enforcement point.

## Risks and open items

- **Structured output + adaptive thinking on Opus 4.8.** `output_config.format`
  is documented to work with streaming and extended/adaptive thinking; the
  provider already streams with `thinking: {type: "adaptive"}`. Confirm on a live
  call during implementation; if any incompatibility surfaces, the offline path
  and the repair loop mean generation still functions while we adjust.
- **In-prompt schema duplication.** Accepted for now (see above); flagged as a
  future token-cost optimisation once we can measure whether the model needs it.
- **`additionalProperties: false` everywhere.** Structured outputs require it on
  every object; the v2 schema already satisfies this (root, scene, character,
  audio, safety). A test asserts the schema is accepted, so a future object added
  without it fails loudly.
