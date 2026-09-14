# Multi-provider generation — Gemini + Qwen behind the wegofwd-llm seam — design

Status: proposed (awaiting review)
Date: 2026-09-14
Repo: `kathai-chithiram`
Shaping ADRs: ADR-006 (domain-model / provider-agnostic generation), PRIVACY.md §6
(no-training / zero-retention before any story text leaves the machine), KC-12
(constrained decoding / structured output), KC-21 (grounding — provider-neutral).

## Problem

Generation currently has one concrete provider behind the `wegofwd-llm` seam:
`AnthropicProvider` (`claude-opus-4-8`). The owner is moving generation to **Google
Gemini (via AI Studio, free tier)** and **Qwen (via a hosted, OpenAI-compatible API)**
— for now against **synthetic / development data only**. The seam was built
provider-agnostic precisely for this, so the change is additive: new adapters, not a
rewrite. Nothing in the corpus, grounding, entitlement, contract, validation, or
rendering layers is touched.

One real tension: the gateway (`run_generation`) **refuses any provider whose
`ProviderConfig` is not `no_training AND zero_retention`** (`ProviderConfigError`,
before the story is touched — PRIVACY.md §6). The free AI Studio tier and a hosted
Qwen API do **not** guarantee no-training/zero-retention, so their honest posture is
non-compliant and the gateway would refuse them — for real *and* synthetic text alike
(it cannot tell them apart). We need to run them on synthetic data **without weakening
the real-data law.**

## Goal and non-goals

**Goal.** Add `GeminiProvider` and `QwenProvider` behind the existing `LLMProvider`
seam, selectable at the CLI, and a single explicit, default-off, loudly-logged
**synthetic-data escape** that lets a non-compliant provider run **only** when the
caller attests the input is synthetic/non-personal. The real-parent (`intake`) path
never exposes it; real story data through a non-ZDR provider stays refused by default.

**Non-goals.**
- **No weakening of the privacy law.** The `no_training AND zero_retention` gate stays.
  The escape is an explicit, auditable, dev-only opt-in — not a relaxation of the
  default. Providers report their **true** posture; nobody sets `no_training=True` for
  a provider that doesn't guarantee it.
- **No real child/story data through Gemini-free / hosted-Qwen** until their data-use
  terms are verified as no-training/zero-retention (or the provider is swapped to a
  compliant endpoint, e.g. Gemini via Vertex, or self-hosted Qwen). Recorded as the
  gate; not in this ticket.
- **No strict per-backend schema enforcement in v1** (see Structured output).
- **No change** to the corpus/grounding/entitlement/contract/validation/render layers.
- **No removal** of `AnthropicProvider` — it remains a selectable, compliant provider.

## Decisions from brainstorming

- **Providers:** Gemini via the `google-genai` SDK (API-key / AI Studio); Qwen via the
  `openai` SDK pointed at an OpenAI-compatible base URL (e.g. DashScope). Owner's choice.
- **Data posture:** synthetic/dev only for now; both providers' `ProviderConfig` report
  `no_training=False, zero_retention=False` (truthful).
- **Guard:** keep the gateway's compliance refusal; add one explicit
  `allow_untrusted_provider` escape (default `False`), CLI `--synthetic-data`, only on
  `generate`.
- **Structured output:** JSON mode + the existing validate-and-repair loop (strict
  schema deferred).
- **Config:** model id and Qwen base URL are env/config-driven (model names churn).

## Components and data flow

### 1. Gateway escape hatch — `wegofwd_llm/gateway.py`
`run_generation(..., allow_untrusted_provider: bool = False)`. New logic at the top,
replacing the unconditional compliance refusal:

```
if not config.is_privacy_compliant:
    if not allow_untrusted_provider:
        raise ProviderConfigError(config.provider_id, "... no-training and zero-retention ...")
    logger.warning(
        "wegofwd-llm: DISPATCHING TO NON-COMPLIANT PROVIDER under synthetic-data "
        "override — provider=%s no_training=%s zero_retention=%s request=%s. "
        "SYNTHETIC / DEV DATA ONLY; never real story data.",
        config.provider_id, config.no_training, config.zero_retention, request_id,
    )
```

- The identifier-leak hard-stop (`count_identifiers` → `IdentifierLeakError`) **still
  runs unconditionally** afterwards — defense in depth, even for synthetic data.
- `GenerationResult.record` (`ProviderRequestRecord`) already captures the true
  `no_training`/`zero_retention` posture, so the audit trail shows a non-compliant run.
- Default `False` → every existing caller behaves exactly as today.

### 2. `GeminiProvider` — `wegofwd_llm/gemini_provider.py` (new)
Mirrors `AnthropicProvider`'s shape.
- `DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"` (env-overridable; verified at build).
- `GEMINI_API_KEY_ENV = "GEMINI_API_KEY"`.
- Lazy import: `importlib.import_module("google.genai")` (package `google-genai`);
  `ImportError` → `ProviderUnavailableError` with the install hint.
- `complete(request)`: build a `generate_content` call — `contents=request.prompt`,
  `system_instruction=request.system_prompt` (when non-empty), and when
  `request.output_schema is not None`, set `response_mime_type="application/json"`
  (**JSON mode**, not the raw Draft-2020-12 schema — see Structured output). Assemble
  the text parts; empty/blocked reply → `ProviderResponseError`; a safety block →
  `ProviderResponseError`.
- Ignores `system_prefix` caching (Anthropic-specific; correctness unaffected).
- Factory `build_gemini_provider(*, model=…, env=…)`: reads `GEMINI_API_KEY`,
  constructs the client. It does **not** imply ZDR — the compliant/non-compliant
  decision lives in the `ProviderConfig` the caller builds.

### 3. `QwenProvider` — `wegofwd_llm/qwen_provider.py` (new)
- `DEFAULT_QWEN_MODEL = "qwen-plus"`; `QWEN_API_KEY_ENV = "QWEN_API_KEY"`;
  `QWEN_BASE_URL_ENV = "QWEN_BASE_URL"` (OpenAI-compatible endpoint, e.g. DashScope).
- Lazy import: `importlib.import_module("openai")`; `ImportError` →
  `ProviderUnavailableError`.
- `complete(request)`: `client.chat.completions.create(model=…, messages=[{system},
  {user: prompt}], response_format={"type": "json_object"} when output_schema)`.
  Map choice-0 message content → `LLMResponse`; empty → `ProviderResponseError`.
- Factory `build_qwen_provider(*, model=…, base_url=…, env=…)`: reads key + base URL
  (fails closed if the key is absent), constructs `openai.OpenAI(base_url=…, api_key=…)`.

### 4. Provider selection — `cli.py`
- New `--provider {anthropic,gemini,qwen}` (default `anthropic`) and `--synthetic-data`
  (default off) on the **`generate`** subcommand only. `intake` gains neither.
- A small factory `_build_provider(name, *, model, effort)` dispatches to the existing
  `_build_anthropic_provider` or the two new builders. Each prints a friendly error and
  returns `None` on missing key/SDK (existing pattern).
- `ProviderConfig` is built per provider with the **true** posture:
  - anthropic (ZDR key): `no_training=args.provider_no_train_zdr, zero_retention=…`.
  - gemini/qwen: `no_training=False, zero_retention=False`,
    `provider_id="gemini:<model>"` / `"qwen:<model>"`.
- `_cmd_generate` passes `allow_untrusted_provider=args.synthetic_data` into
  `generate_scene_script` → `run_generation`. Using `--provider gemini|qwen` **without**
  `--synthetic-data` fails closed with a clear message pointing to the flag and the
  synthetic-only meaning.

### 5. `generate_scene_script` — `generation/generator.py`
Add `allow_untrusted_provider: bool = False`, threaded into every `run_generation`
call. No other change (grounding, repair loop, schema pass-through untouched).

### 6. Optional-extra deps — `pyproject.toml`
```toml
gemini = ["google-genai>=1.0"]
qwen   = ["openai>=1.40"]
```
Lazy-imported, mirroring `[generation]`/`anthropic`. `dev` gains both so tests can
import the SDKs (tests still use fakes; no live keys).

### 7. Housekeeping
- **ADR-006**: record the move to multi-provider generation (Anthropic/Gemini/Qwen
  behind one seam), the synthetic-data escape, and the ZDR gate for real data.
- **`DEFAULT_MODEL`**: the generator/CLI default provider stays `anthropic` (compliant)
  so real-data behaviour is unchanged; the per-provider default model constants live in
  each adapter. (We do **not** silently make a non-ZDR provider the default.)
- **CLAUDE.md**: change the "default to the latest Claude models" line to a
  provider-agnostic statement (Anthropic/Gemini/Qwen behind the seam; real story data
  only through a no-training/zero-retention provider).

```
kc generate --provider gemini --synthetic-data --story mock.txt
  → _build_provider("gemini") → GeminiProvider
  → ProviderConfig(gemini, no_training=False, zero_retention=False)
  → generate_scene_script(..., allow_untrusted_provider=True)
    → run_generation(..., allow_untrusted_provider=True)
        not compliant → allowed (loud WARNING) → pseudonymize → identifier hard-stop
        → provider.complete(JSON mode) → validate + repair loop → scene script
kc generate --provider gemini            # no --synthetic-data
  → run_generation refuses (ProviderConfigError): non-ZDR provider needs --synthetic-data
kc intake ...                            # real-parent path: no --provider/--synthetic-data; ZDR only
```

## Structured output

The seam passes `output_schema=SCENE_SCRIPT_SCHEMA_V2` (JSON Schema Draft 2020-12).
Anthropic enforces it natively. Gemini's `response_schema` is a narrower OpenAPI-derived
dialect and would reject several Draft-2020-12 keywords; hosted Qwen's OpenAI-compatible
`json_schema` support varies. So in v1 both new providers use **JSON mode**
(`response_mime_type="application/json"` / `response_format={"type":"json_object"}`) —
"produce JSON", not "produce JSON matching this exact schema". The scene-script schema
still reaches the model through the prompt (unchanged), and the **validate-and-repair
loop remains the correctness guarantee** — exactly the contract the seam already
documents ("providers without structured output ignore the field; the repair loop is the
guarantee"). Strict per-backend schema translation is a future enhancement, per provider.

## Privacy & safety

- **The law is intact.** Default behaviour: a non-compliant provider is refused. Only an
  explicit `allow_untrusted_provider` / `--synthetic-data` opt-in permits it, and it is
  logged as a loud warning naming the provider and its posture.
- **Truthful posture.** Gemini/Qwen configs report `no_training=False`; we never fake
  compliance. The `ProviderRequestRecord` audit shows the real posture per request.
- **Real-parent path unchanged.** `intake` never exposes `--provider`/`--synthetic-data`;
  it continues to require a compliant (ZDR) provider.
- **Defense in depth.** Pseudonymisation and the `IdentifierLeakError` hard-stop run for
  synthetic runs too.
- **Logs.** Only ids/lengths/posture (existing discipline); never prompt text.
- **The gate for later:** real story data through Gemini/Qwen requires verifying
  no-training/zero-retention terms (Gemini via Vertex, or self-hosted Qwen) and building
  a compliant `ProviderConfig`. Out of scope here; recorded in ADR-006.

## Error handling

- Missing SDK → `ProviderUnavailableError` (in `__init__`, via lazy import), with the
  `pip install 'kathai-chithiram[gemini]'` / `[qwen]` hint.
- Missing API key (or Qwen base URL) → fail closed in the builder (`ProviderConfigError`
  / friendly CLI error), no fallback to ambient credentials.
- Empty / safety-blocked model reply → `ProviderResponseError`.
- No bare/blind except; specific SDK exceptions are caught and re-raised as domain errors.

## Testing (mock data only; no network; no live keys)

- **Gateway escape hatch:** non-compliant config + `allow_untrusted_provider=False` →
  `ProviderConfigError`; `=True` → dispatches (assert with `CapturingProvider`) and the
  identifier hard-stop still fires on a planted residual identifier.
- **GeminiProvider / QwenProvider:** inject a fake SDK client (duck-typed), assert the
  request is built correctly (system instruction, JSON-mode flag set when
  `output_schema` present, prompt carried), response text assembled, and empty/blocked →
  `ProviderResponseError`; missing SDK (simulated `ImportError`) → `ProviderUnavailableError`.
- **CLI:** `--provider gemini` without `--synthetic-data` fails closed with the pointed
  message; with it, the injected provider is used and config posture is non-compliant;
  `intake` exposes neither flag.
- **Privacy:** a synthetic run still pseudonymises (child token, not name, in the
  outbound prompt) — reuse the existing gateway payload test.
- All new providers unit-tested without importing a live SDK where possible (fakes);
  SDK import paths guarded so the suite passes with the extras absent.

## Files touched

- `src/kathai_chithiram/wegofwd_llm/gemini_provider.py`, `qwen_provider.py` (create).
- `src/kathai_chithiram/wegofwd_llm/gateway.py` — `allow_untrusted_provider` param.
- `src/kathai_chithiram/generation/generator.py` — thread the flag through.
- `src/kathai_chithiram/cli.py` — `--provider`, `--synthetic-data`, `_build_provider`.
- `src/kathai_chithiram/wegofwd_llm/__init__.py` — export the new providers/builders.
- `pyproject.toml` — `[gemini]`, `[qwen]` extras (+ into `dev`).
- `docs/ADR_006_domain_model_strategy.md`, `CLAUDE.md` — multi-provider note.
- `tests/kathai_chithiram/wegofwd_llm/…` — gateway escape, both adapters (fake clients),
  CLI selection/guard.

## Decisions / risks

- **Model-id / SDK churn.** Gemini and Qwen model names and SDK surfaces move fast; model
  ids and Qwen base URL are env/config-driven, and exact SDK calls are verified against
  the installed SDK at implementation time (the plan verifies, not this spec).
- **Gemini schema dialect.** Full Draft-2020-12 enforcement isn't portable; JSON mode +
  repair loop is the honest v1. Documented as a future per-backend enhancement.
- **Escape-hatch misuse.** Mitigated by: default off, loud warning, audit record with
  true posture, `intake` never exposing it, and fail-closed when `--provider` is a
  non-ZDR one without `--synthetic-data`.
- **Free-tier / hosted data terms.** The reason for synthetic-only; the real-data gate is
  recorded in ADR-006, not opened here.

## Global constraints

- Python; `from __future__ import annotations`; OpenSpec docstrings on public API.
- Every function handles errors explicitly; domain-specific errors; **no bare/blind
  except**.
- Tests: mock data only, **no network, no live API keys**; SDK imports lazy so the suite
  runs with the extras absent.
- Never log prompt text or a child's name; only ids/lengths/posture.
- `ruff check .` (E,F,I,B,UP,BLE, line-length 100) and `mypy` clean on new code.
- The privacy law (`no_training AND zero_retention` to send real story text) is not
  weakened; the escape is explicit, default-off, synthetic-only.
