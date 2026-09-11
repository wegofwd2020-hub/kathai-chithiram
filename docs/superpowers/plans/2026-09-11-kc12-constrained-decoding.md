# KC-12 Constrained Decoding + v2 Emission — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Constrain generation output to the v2 scene-script schema via Anthropic structured outputs, and switch generation to emit v2 — collapsing the repair loop toward one attempt without removing it.

**Architecture:** Add an optional `output_schema` to the provider-agnostic `LLMRequest`; the gateway forwards it and the Anthropic provider maps it to `output_config.format` (`type: json_schema`). Structured outputs enforce *structure* (types, enums, `$ref`, `required`, `additionalProperties:false`); `validate_scene_script` keeps enforcing the numeric/length/pattern/cross-field rules the structured-output subset does not cover, and the validate-and-repair loop stays as the guarantee of last resort.

**Tech Stack:** Python, `anthropic` SDK (Messages API, streaming), `jsonschema` (Draft 2020-12), `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-11-kc12-constrained-decoding-design.md`

## Global Constraints

- **Language:** Python only. Match surrounding style.
- **Exceptions:** every function handles errors explicitly; raise domain-specific errors with context; no bare `except`; no swallowed exceptions.
- **Docstrings:** OpenSpec-compliant docstrings on every public function/class (and on changed ones — keep them accurate).
- **Tests:** every change ships with tests using **mock data only**. No real child data. **No live model / no network** — use the existing fakes (`FakeClient`, `CapturingProvider`, `ScriptedProvider`).
- **Privacy:** the gateway's privacy guards (posture check → pseudonymize → residual-identifier guard → audit record) must run exactly as today; `output_schema` changes none of them.
- **Model id:** `claude-opus-4-8` (already the provider default; do not change it).
- **Structured-output subset:** Anthropic structured outputs enforce only types/`enum`/`const`/`required`/`$ref`/`$defs`/`additionalProperties:false`. They do **not** enforce `minimum`/`maximum`/`exclusiveMinimum`/`minLength`/`maxLength`/`pattern` — those remain the job of `validate_scene_script`. Do not remove any validator rule.
- **Frozen dataclasses:** the seam types are `@dataclass(frozen=True)`; keep new fields defaulted so the change is backward compatible.
- **Run the whole suite** (`pytest`) at the end of each task, not just the new test — these files have many existing tests that must stay green.

---

### Task 1: Add `output_schema` to the seam contract

**Files:**
- Modify: `src/kathai_chithiram/wegofwd_llm/provider.py` (the `LLMRequest` dataclass)
- Test: `tests/kathai_chithiram/wegofwd_llm/test_provider.py` (create)

**Interfaces:**
- Produces: `LLMRequest(prompt, config, system_prompt="", system_prefix="", output_schema=None)` where `output_schema: dict[str, Any] | None`. Consumed by Tasks 2, 3, 5.

- [ ] **Step 1: Write the failing test**

Create `tests/kathai_chithiram/wegofwd_llm/test_provider.py`:

```python
"""Tests for the wegofwd-llm seam request type.

The seam is text-first but may carry an optional output schema so a
structured-output-capable provider can constrain its reply; providers that
cannot honour it ignore the field.
"""

from __future__ import annotations

from kathai_chithiram.wegofwd_llm.provider import LLMRequest, ProviderConfig

CONFIG = ProviderConfig(provider_id="fake:no-train-zdr", no_training=True, zero_retention=True)


def test_output_schema_defaults_to_none() -> None:
    req = LLMRequest(prompt="p", config=CONFIG)
    assert req.output_schema is None


def test_output_schema_round_trips() -> None:
    schema = {"type": "object", "additionalProperties": False}
    req = LLMRequest(prompt="p", config=CONFIG, output_schema=schema)
    assert req.output_schema == schema
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/kathai_chithiram/wegofwd_llm/test_provider.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'output_schema'`.

- [ ] **Step 3: Add the field**

In `src/kathai_chithiram/wegofwd_llm/provider.py`, add `from typing import Any` if not already imported, then add the field to `LLMRequest` (after `system_prefix`):

```python
    output_schema: dict[str, Any] | None = None
```

Extend the `LLMRequest` docstring's Args with:

```
        output_schema: Optional JSON Schema the reply must conform to. A provider
            that supports constrained/structured output MUST return a value
            satisfying it; a provider that does not ignores this field and the
            caller's validate-and-repair loop remains the guarantee. Carries no
            child identifier.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/kathai_chithiram/wegofwd_llm/test_provider.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/wegofwd_llm/provider.py tests/kathai_chithiram/wegofwd_llm/test_provider.py
git commit -m "feat(seam): optional output_schema on LLMRequest"
```

---

### Task 2: Gateway forwards `output_schema`

**Files:**
- Modify: `src/kathai_chithiram/wegofwd_llm/gateway.py` (`run_generation`)
- Test: `tests/kathai_chithiram/wegofwd_llm/test_gateway.py` (add tests)

**Interfaces:**
- Consumes: `LLMRequest.output_schema` (Task 1).
- Produces: `run_generation(..., output_schema: dict[str, Any] | None = None)` — forwards the schema into the `LLMRequest` it builds. Consumed by Task 5.

- [ ] **Step 1: Write the failing tests**

Append to `tests/kathai_chithiram/wegofwd_llm/test_gateway.py`:

```python
def test_output_schema_forwarded_to_provider() -> None:
    provider = CapturingProvider()
    schema = {"type": "object", "additionalProperties": False}
    run_generation(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
        output_schema=schema,
    )
    assert provider.requests[0].output_schema == schema


def test_output_schema_defaults_to_none_when_omitted() -> None:
    provider = CapturingProvider()
    run_generation(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
    )
    assert provider.requests[0].output_schema is None


def test_output_schema_not_forwarded_when_leak_guard_trips() -> None:
    # The privacy guards run before dispatch; a leak means the provider is never
    # called, schema or not.
    mapping = NameMapping(identifiers=("Milo", "MILO"), token="MILO")
    provider = ExplodingProvider()  # raises if reached
    with pytest.raises(IdentifierLeakError):
        run_generation(
            story_text=MOCK_STORY,
            mapping=mapping,
            provider=provider,
            config=COMPLIANT,
            request_id="req-leak",
            output_schema={"type": "object"},
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/kathai_chithiram/wegofwd_llm/test_gateway.py -k output_schema -v`
Expected: FAIL — `run_generation() got an unexpected keyword argument 'output_schema'`.

- [ ] **Step 3: Add the parameter and forward it**

In `src/kathai_chithiram/wegofwd_llm/gateway.py`:

Add `from typing import Any` (if not present). Add the parameter to `run_generation`'s signature (after `system_prefix`):

```python
    output_schema: dict[str, Any] | None = None,
```

Document it in the Args (after `system_prefix`):

```
        output_schema: Optional JSON Schema forwarded to the provider so a
            structured-output-capable provider can constrain its reply; providers
            without that capability ignore it. Carries no child identifier.
```

Pass it into the `LLMRequest` construction in the `provider.complete(...)` call:

```python
    response = provider.complete(
        LLMRequest(
            prompt=prompt,
            config=config,
            system_prompt=system_prompt,
            system_prefix=system_prefix,
            output_schema=output_schema,
        )
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/kathai_chithiram/wegofwd_llm/test_gateway.py -v`
Expected: PASS (new tests plus all existing gateway tests).

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/wegofwd_llm/gateway.py tests/kathai_chithiram/wegofwd_llm/test_gateway.py
git commit -m "feat(gateway): forward output_schema into the seam request"
```

---

### Task 3: AnthropicProvider maps `output_schema` to `output_config.format`

**Files:**
- Modify: `src/kathai_chithiram/wegofwd_llm/anthropic_provider.py` (`AnthropicProvider.complete`)
- Test: `tests/kathai_chithiram/wegofwd_llm/test_anthropic_provider.py` (add tests)

**Interfaces:**
- Consumes: `LLMRequest.output_schema` (Task 1).
- Produces: when `output_schema` is set, the Messages call's `output_config` gains a `format` block `{"type": "json_schema", "schema": <schema>}` alongside the existing `effort`; when it is `None`, the call is unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `tests/kathai_chithiram/wegofwd_llm/test_anthropic_provider.py`:

```python
def test_output_schema_sets_json_schema_format_with_effort() -> None:
    client = FakeClient(FakeMessage(content=[FakeBlock("text", "{}")]))
    schema = {"type": "object", "additionalProperties": False}
    req = LLMRequest(prompt="p", config=CONFIG, system_prompt="RULES", output_schema=schema)
    AnthropicProvider(client=client, effort="high").complete(req)
    assert client.messages.calls[0]["output_config"] == {
        "effort": "high",
        "format": {"type": "json_schema", "schema": schema},
    }


def test_no_output_schema_sends_no_format_key() -> None:
    client = FakeClient(FakeMessage(content=[FakeBlock("text", "ok")]))
    AnthropicProvider(client=client).complete(_request())
    assert client.messages.calls[0]["output_config"] == {"effort": "high"}
    assert "format" not in client.messages.calls[0]["output_config"]


def test_refusal_still_raises_on_structured_path() -> None:
    client = FakeClient(FakeMessage(content=[], stop_reason="refusal"))
    schema = {"type": "object", "additionalProperties": False}
    req = LLMRequest(prompt="p", config=CONFIG, output_schema=schema)
    with pytest.raises(ProviderResponseError, match="refusal"):
        AnthropicProvider(client=client).complete(req)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/kathai_chithiram/wegofwd_llm/test_anthropic_provider.py -k "output_schema or structured_path" -v`
Expected: FAIL — `test_output_schema_sets_json_schema_format_with_effort` fails because `output_config` has no `format` key. (`test_no_output_schema_sends_no_format_key` and the refusal test may already pass — that is fine; they lock the no-schema behavior.)

- [ ] **Step 3: Implement the structured-output branch**

In `src/kathai_chithiram/wegofwd_llm/anthropic_provider.py`, in `complete`, after the `kwargs` dict is built and the `system` param is set, and before the `self._client.messages.stream(**kwargs)` call, add:

```python
        # KC-12: when the caller supplies a schema, constrain the reply to it via
        # Anthropic structured outputs. This enforces structure only (types,
        # enums, $ref, required, additionalProperties); the caller still validates
        # the numeric/length/pattern/cross-field rules the subset cannot express.
        if request.output_schema is not None:
            kwargs["output_config"] = {
                **kwargs["output_config"],
                "format": {"type": "json_schema", "schema": request.output_schema},
            }
```

Update the `complete` docstring's Args note for `request` to mention `request.output_schema` constrains the reply when set. Update the module docstring's "thin text-in/text-out adapter" sentence to note it also constrains output to a supplied schema via structured outputs (KC-12).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/kathai_chithiram/wegofwd_llm/test_anthropic_provider.py -v`
Expected: PASS (new tests plus all existing provider tests — especially `test_returns_assembled_text_and_builds_streaming_call`, which asserts `output_config == {"effort": "high"}` for the no-schema path).

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/wegofwd_llm/anthropic_provider.py tests/kathai_chithiram/wegofwd_llm/test_anthropic_provider.py
git commit -m "feat(anthropic): constrain reply to output_schema via structured outputs"
```

---

### Task 4: Emit v2 from the generation prompt

**Files:**
- Modify: `src/kathai_chithiram/generation/scene_script_prompt.py` (schema import, `EXAMPLE_SCENE_SCRIPT`, `_cross_field_rules`)
- Test: `tests/kathai_chithiram/generation/test_scene_script_prompt.py` (add tests)

**Interfaces:**
- Consumes: `SCENE_SCRIPT_SCHEMA_V2` from `kathai_chithiram.scene_script.schema`; the vocabulary enums (indirectly, via valid values).
- Produces: an updated `EXAMPLE_SCENE_SCRIPT` that is a valid **v2** script, and a prefix that embeds the v2 schema and instructs `intent: "instructional"` / `perspective: "first_person"`. `EXAMPLE_SCENE_SCRIPT` is re-exported through `kathai_chithiram.generation` and reused by Task 5's tests.

Note: `validate_scene_script` requires an instructional story to be `perspective: "first_person"` (`story.instructional.requires_first_person`), and rejects `intent: "experiential"` (`story.intent.gated`). The v2 example below uses `parent` / `first_person` / `instructional` and closed-vocabulary art values (`setting` ∈ Background, `props` ∈ Prop, `pose` ∈ Gesture, `expression` ∈ Expression).

- [ ] **Step 1: Write the failing tests**

Append to `tests/kathai_chithiram/generation/test_scene_script_prompt.py`:

```python
# --- KC-12: v2 emission ----------------------------------------------------


def test_example_is_v2() -> None:
    assert EXAMPLE_SCENE_SCRIPT["schema_version"] == "2.0"
    assert EXAMPLE_SCENE_SCRIPT["author"] in ("parent", "therapist")
    assert EXAMPLE_SCENE_SCRIPT["perspective"] == "first_person"
    assert EXAMPLE_SCENE_SCRIPT["intent"] == "instructional"


def test_example_uses_closed_vocabulary() -> None:
    from kathai_chithiram.scene_script.vocabulary import (
        Background,
        Expression,
        Gesture,
        Prop,
    )

    settings = {b.value for b in Background}
    props = {p.value for p in Prop}
    poses = {g.value for g in Gesture}
    expressions = {e.value for e in Expression}
    for scene in EXAMPLE_SCENE_SCRIPT["scenes"]:
        assert scene["setting"] in settings
        assert set(scene["props"]) <= props
        for character in scene["characters"]:
            assert character["pose"] in poses
            assert character["expression"] in expressions


def test_prefix_embeds_v2_schema_and_grammar() -> None:
    prefix = build_scene_script_system_prefix(child_token="CHILD")
    # v2 schema id and the story-grammar fields are present.
    assert "scene-script/v2.json" in prefix
    assert "author" in prefix and "perspective" in prefix and "intent" in prefix
    # It steers the model to the instructional, first-person track.
    assert "instructional" in prefix
    assert "first_person" in prefix
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/kathai_chithiram/generation/test_scene_script_prompt.py -k "v2 or closed_vocabulary or grammar" -v`
Expected: FAIL — the example is still v1 (`schema_version == "1.0"`, no `author`), and the prefix embeds the v1 schema.

- [ ] **Step 3: Swap the schema, the example, and the rules**

In `src/kathai_chithiram/generation/scene_script_prompt.py`:

3a. Change the schema import:

```python
from kathai_chithiram.scene_script.schema import SCENE_SCRIPT_SCHEMA_V2
```

3b. Replace `EXAMPLE_SCENE_SCRIPT` with a v2 example (keep the module comment above it about it being synthetic and test-validated):

```python
EXAMPLE_SCENE_SCRIPT: dict[str, Any] = {
    "schema_version": "2.0",
    "story_id": "00000000-0000-0000-0000-000000000001",
    "title": "Brushing Teeth With CHILD",
    "child_token": "CHILD",
    "locale": "en-US",
    "author": "parent",
    "perspective": "first_person",
    "intent": "instructional",
    "total_duration_s": 8,
    "fps": 24,
    "safety": {
        "max_flash_hz": 3,
        "max_scene_cuts_per_min": 12,
        "reviewed_by_human": False,
    },
    "scenes": [
        {
            "index": 1,
            "duration_s": 4,
            "narration": "I pick up my toothbrush.",
            "caption": "I pick up my toothbrush.",
            "setting": "bathroom",
            "characters": [{"id": "child", "pose": "rest", "expression": "calm"}],
            "props": ["toothbrush", "toothpaste"],
            "transition_in": "fade",
            "transition_out": "dissolve",
            "audio": {"narration_volume": 0.7, "sfx": []},
        },
        {
            "index": 2,
            "duration_s": 4,
            "narration": "I brush and I smile.",
            "caption": "I brush and I smile.",
            "setting": "bathroom",
            "characters": [{"id": "child", "pose": "wave", "expression": "smile"}],
            "props": ["toothbrush"],
            "transition_in": "dissolve",
            "transition_out": "fade",
            "audio": {"narration_volume": 0.7, "sfx": []},
        },
    ],
}
```

3c. In `build_scene_script_system_prefix`, change the schema serialization line to the v2 schema:

```python
    schema = json.dumps(SCENE_SCRIPT_SCHEMA_V2, indent=2, sort_keys=True)
```

3d. In `_cross_field_rules`, add the v2 story-grammar rules to the tuple of rules (after the existing rules), so the model is steered to the gated-safe, validator-passing track:

```python
            "Set 'author' to 'parent', 'perspective' to 'first_person', and "
            "'intent' to 'instructional'.",
            "Write narration in the first person ('I ...'); instructional stories "
            "must be first person.",
            "Choose 'setting', 'props', each character's 'pose', and each "
            "character's 'expression' only from the enumerated values in the "
            "schema above; do not invent new ones.",
```

Update the module docstring so its reference to the contract mentions v2 (the closed art vocabulary and the author/perspective/intent grammar).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/kathai_chithiram/generation/test_scene_script_prompt.py -v`
Expected: PASS — including the existing `test_example_is_contract_valid` (now validating the example under **v2**) and `test_prompt_carries_safety_rules_and_contract`.

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/generation/scene_script_prompt.py tests/kathai_chithiram/generation/test_scene_script_prompt.py
git commit -m "feat(generation): emit scene-script v2 (closed vocab + story grammar)"
```

---

### Task 5: Generator constrains generation to the v2 schema

**Files:**
- Modify: `src/kathai_chithiram/generation/generator.py` (`generate_scene_script`)
- Test: `tests/kathai_chithiram/generation/test_generator.py` (add a test)

**Interfaces:**
- Consumes: `run_generation(..., output_schema=...)` (Task 2); `SCENE_SCRIPT_SCHEMA_V2` (from `kathai_chithiram.scene_script.schema`); `EXAMPLE_SCENE_SCRIPT` (now v2, Task 4).
- Produces: production generation passes `SCENE_SCRIPT_SCHEMA_V2` as the output constraint on every attempt.

- [ ] **Step 1: Write the failing test**

Append to `tests/kathai_chithiram/generation/test_generator.py`:

```python
def test_generation_constrains_output_to_v2_schema() -> None:
    from kathai_chithiram.scene_script.schema import SCENE_SCRIPT_SCHEMA_V2

    provider = ScriptedProvider(replies=[json.dumps(_valid_script())])
    generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
    )
    assert provider.requests[0].output_schema == SCENE_SCRIPT_SCHEMA_V2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/kathai_chithiram/generation/test_generator.py::test_generation_constrains_output_to_v2_schema -v`
Expected: FAIL — `output_schema` is `None` (generator does not pass one yet).

- [ ] **Step 3: Pass the v2 schema into the seam**

In `src/kathai_chithiram/generation/generator.py`:

Add the import:

```python
from kathai_chithiram.scene_script.schema import SCENE_SCRIPT_SCHEMA_V2
```

In `generate_scene_script`, add `output_schema=SCENE_SCRIPT_SCHEMA_V2` to the `run_generation(...)` call inside the attempt loop:

```python
        result = run_generation(
            story_text=story_text,
            mapping=mapping,
            provider=provider,
            config=config,
            request_id=f"{request_id}#{attempt}",
            system_prompt=system_prompt,
            system_prefix=system_prefix,
            output_schema=SCENE_SCRIPT_SCHEMA_V2,
            clock=clock,
        )
```

Add one sentence to the `generate_scene_script` docstring noting it constrains the reply to the v2 schema via the seam's `output_schema`, while validation and the repair loop remain the guarantee (structured output is a partial constraint).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/kathai_chithiram/generation/test_generator.py -v`
Expected: PASS — the new test plus every existing generator test (they use `EXAMPLE_SCENE_SCRIPT`, now v2, which still validates).

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/generation/generator.py tests/kathai_chithiram/generation/test_generator.py
git commit -m "feat(generation): constrain generation to the v2 schema (KC-12)"
```

---

### Task 6: Update docs to reflect KC-12 done

**Files:**
- Modify: `docs/LLM_PROGRAM_PLAN.md` (Phase 1 heading)
- Modify: `docs/SCENE_SCRIPT_CONTRACT.md` (note structured v2 emission)
- Modify: `docs/CONTENT_SAFETY.md` (enforcement point note)

No code, no test. This task documents the shipped change.

- [ ] **Step 1: Mark KC-12 done in the program plan**

In `docs/LLM_PROGRAM_PLAN.md`, under the heading `### Phase 1 — Constrained decoding and v2 emission *(3–4 weeks)* — `KC-12``, add a status line immediately after the heading:

```markdown
**Status (2026-09-11): done.** Generation emits v2 and constrains output to the
v2 schema via Anthropic structured outputs (`output_config.format`), which
enforces structure only; `validate_scene_script` continues to enforce the
numeric/length/pattern/cross-field rules and the repair loop remains the
fallback. The prompt-caching half shipped earlier (#101). The exit-gate numbers
(100% contract validity, mean attempts ≈ 1.0, token cost) are a live-model
measurement to be recorded by an eval run, not asserted in unit tests.
```

- [ ] **Step 2: Note structured emission in the contract**

In `docs/SCENE_SCRIPT_CONTRACT.md`, in the section describing generation/validation (near where v1/v2 majors are discussed), add a short paragraph:

```markdown
Generation constrains its output to the v2 JSON schema at decode time using the
provider's structured-output mechanism (on the Anthropic path,
`output_config.format` with `type: json_schema`). This makes structural
violations (wrong types, out-of-vocabulary art, missing fields) unrepresentable
on a compliant provider. It is a *partial* constraint — structure only — so the
validator in `scene_script/validation.py` remains the enforcement point for every
numeric, length, pattern, and cross-field rule, and an invalid script is still
rejected, not rendered.
```

- [ ] **Step 3: Note the enforcement point in content safety**

In `docs/CONTENT_SAFETY.md` §5 (the enforcement-points section), append to the generation enforcement point a sentence:

```markdown
As of KC-12, generation additionally constrains its output to the v2 schema at
decode time (structured outputs) — a first line of structural defence that does
not replace the validator gate below it.
```

- [ ] **Step 4: Commit**

```bash
git add docs/LLM_PROGRAM_PLAN.md docs/SCENE_SCRIPT_CONTRACT.md docs/CONTENT_SAFETY.md
git commit -m "docs: mark KC-12 done; note structured v2 emission"
```

---

## Final verification

- [ ] **Run the full suite:** `pytest`
  Expected: all tests pass (the pre-existing 677+ plus the new ones).
- [ ] **Lint / typecheck:** `ruff check .` and `mypy .`
  Expected: clean. If `mypy` flags the new `output_schema: dict[str, Any] | None`, ensure `from typing import Any` is imported in each file that references `Any`.

---

## Self-review notes (author)

- **Spec coverage:** seam change → Task 1; gateway forward → Task 2; Anthropic `output_config.format` → Task 3; v2 emission (schema + example + grammar rules) → Task 4; generator passes the schema, loop retained → Task 5; docs → Task 6. The spec's "honest exit gate" is reflected in Task 6's status note (not fabricated as a unit test).
- **Type consistency:** `output_schema: dict[str, Any] | None` is used identically in `LLMRequest` (Task 1), `run_generation` (Task 2), and the provider read (Task 3). The `format` block shape `{"type": "json_schema", "schema": <schema>}` is identical in the Task 3 impl and its test.
- **No live-model dependency:** every test uses an existing fake (`FakeClient`, `CapturingProvider`, `ScriptedProvider`); no network.
- **Backward compatibility:** `output_schema` defaults to `None` everywhere; existing provider/gateway/generator tests remain valid (the no-schema provider test still asserts `output_config == {"effort": "high"}`).
