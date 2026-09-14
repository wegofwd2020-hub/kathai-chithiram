# Multi-provider generation (Gemini + Qwen) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `GeminiProvider` + `QwenProvider` behind the existing `wegofwd-llm` seam, selectable via `kc generate --provider`, with a default-off, loudly-logged `--synthetic-data` escape that lets non-ZDR providers run on synthetic data only — the no-training/zero-retention law otherwise unchanged.

**Architecture:** Two new `LLMProvider` adapters (lazy-importing their SDKs) plus one new gateway parameter, `allow_untrusted_provider` (default `False`). The gateway still refuses non-compliant providers by default; the escape permits them with a loud warning while the identifier-leak hard-stop still runs. Structured output uses JSON mode + the existing validate-and-repair loop. Anthropic remains the default provider.

**Tech Stack:** Python; `google-genai` SDK (Gemini); `openai` SDK pointed at an OpenAI-compatible endpoint (Qwen); pytest; ruff; mypy.

**Spec:** `docs/superpowers/specs/2026-09-14-multi-provider-gemini-qwen-design.md`

## Global Constraints

- Python; `from __future__ import annotations` at the top of every new module.
- **Privacy law not weakened:** the gateway's `no_training AND zero_retention` refusal stays. The escape is explicit, default `False`, synthetic-only, and logged loud. Providers report their **true** posture — never fake `no_training=True`.
- Errors: domain-specific (`ProviderUnavailableError` for a missing SDK; `ProviderResponseError` for empty/blocked replies; `ProviderConfigError` for a missing key/posture); **no bare/blind except** (catch specific exceptions).
- OpenSpec docstrings (Args/Returns/Raises) on every public function/class.
- SDK imports are **lazy** (`importlib.import_module` in a helper) so the suite runs with the extras absent. Tests use **fake SDK clients — no network, no live keys, mock data only**.
- Never log prompt text or a child's name — only ids / lengths / posture.
- `ruff check .` (select E,F,I,B,UP,BLE, line-length 100) and `mypy` clean on new code.
- Test/tooling: from the kathai repo root, `.venv/bin/python -m pytest`, `.venv/bin/ruff check .`, `.venv/bin/python -m mypy src` (or per-file). This repo is the current working directory; normal `cd` is fine here.

---

## File Structure

- `src/kathai_chithiram/wegofwd_llm/gateway.py` — add `allow_untrusted_provider`.
- `src/kathai_chithiram/generation/generator.py` — thread the flag through.
- `src/kathai_chithiram/wegofwd_llm/gemini_provider.py` — new adapter.
- `src/kathai_chithiram/wegofwd_llm/qwen_provider.py` — new adapter.
- `src/kathai_chithiram/wegofwd_llm/__init__.py` — export new providers/builders.
- `src/kathai_chithiram/cli.py` — `--provider`, `--synthetic-data`, `_build_provider`.
- `pyproject.toml` — `[gemini]`, `[qwen]` extras (+ into `dev`).
- `docs/ADR_006_domain_model_strategy.md`, `CLAUDE.md` — multi-provider note.
- `tests/kathai_chithiram/wegofwd_llm/…`, `tests/kathai_chithiram/test_cli_provider.py` — mirrored tests.

---

## Task 1: Gateway escape hatch — `allow_untrusted_provider`

**Files:**
- Modify: `src/kathai_chithiram/wegofwd_llm/gateway.py`
- Test: `tests/kathai_chithiram/wegofwd_llm/test_gateway_untrusted.py`

**Interfaces:**
- Consumes: existing `run_generation`, `ProviderConfig` (`provider_id`, `no_training`, `zero_retention`, `is_privacy_compliant`), `ProviderConfigError`, `IdentifierLeakError`, `pseudonymize`, `count_identifiers`.
- Produces: `run_generation(..., allow_untrusted_provider: bool = False)` — when the config is not privacy-compliant, raises `ProviderConfigError` unless `allow_untrusted_provider=True`, in which case it logs a loud warning and proceeds. Default `False` = unchanged behaviour.

- [ ] **Step 1: Write the failing tests**

Create `tests/kathai_chithiram/wegofwd_llm/test_gateway_untrusted.py`:

```python
"""The synthetic-data escape: a non-compliant provider runs only when explicitly allowed."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from kathai_chithiram.errors import IdentifierLeakError, ProviderConfigError
from kathai_chithiram.privacy.pseudonymize import NameMapping
from kathai_chithiram.wegofwd_llm.gateway import run_generation
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, LLMResponse, ProviderConfig

_NONCOMPLIANT = ProviderConfig(provider_id="gemini:test", no_training=False, zero_retention=False)
_MAPPING = NameMapping(real_name="Milo", token="CHILD")
_STORY = "Milo brushes his teeth. Milo smiles."


@dataclass
class _Capturing:
    requests: list[LLMRequest] = field(default_factory=list)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(text="ok")


def test_noncompliant_refused_by_default() -> None:
    with pytest.raises(ProviderConfigError):
        run_generation(
            story_text=_STORY, mapping=_MAPPING, provider=_Capturing(),
            config=_NONCOMPLIANT, request_id="r1",
        )


def test_noncompliant_allowed_with_flag() -> None:
    provider = _Capturing()
    result = run_generation(
        story_text=_STORY, mapping=_MAPPING, provider=provider,
        config=_NONCOMPLIANT, request_id="r1", allow_untrusted_provider=True,
    )
    assert result.response.text == "ok"
    assert len(provider.requests) == 1
    # posture recorded truthfully
    assert result.record.no_training is False and result.record.zero_retention is False
    # pseudonymised: the child's real name never reaches the provider
    assert "Milo" not in provider.requests[0].prompt
    assert "CHILD" in provider.requests[0].prompt


def test_identifier_hard_stop_still_runs_under_flag() -> None:
    # A mapping whose token does not actually replace the name leaves a residual
    # identifier; the hard-stop must still fire even under the synthetic override.
    leaky = NameMapping(real_name="Milo", token="Milo")  # token == name -> nothing stripped
    with pytest.raises(IdentifierLeakError):
        run_generation(
            story_text=_STORY, mapping=leaky, provider=_Capturing(),
            config=_NONCOMPLIANT, request_id="r1", allow_untrusted_provider=True,
        )
```

> Note: confirm `NameMapping`'s real field names by reading `src/kathai_chithiram/privacy/pseudonymize.py`; adjust the `NameMapping(...)` construction in the test to match (the concept — real name vs token — is what matters).

- [ ] **Step 2: Run the tests, verify they fail**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/wegofwd_llm/test_gateway_untrusted.py -q`
Expected: FAIL — `run_generation()` has no `allow_untrusted_provider` (the default-refuse test may pass already; the flag tests fail on an unexpected-keyword error).

- [ ] **Step 3: Add the parameter + escape logic**

In `src/kathai_chithiram/wegofwd_llm/gateway.py`, add `allow_untrusted_provider: bool = False` to `run_generation`'s keyword-only params (place it immediately before `clock`). Replace the existing compliance refusal block:

```python
    if not config.is_privacy_compliant:
        raise ProviderConfigError(
            config.provider_id,
            "provider must guarantee both no-training and zero-retention "
            "to receive child story text",
        )
```

with:

```python
    if not config.is_privacy_compliant:
        if not allow_untrusted_provider:
            raise ProviderConfigError(
                config.provider_id,
                "provider must guarantee both no-training and zero-retention "
                "to receive child story text",
            )
        logger.warning(
            "wegofwd-llm: DISPATCHING TO NON-COMPLIANT PROVIDER under synthetic-data "
            "override - provider=%s no_training=%s zero_retention=%s request=%s. "
            "SYNTHETIC / DEV DATA ONLY; never real story data.",
            config.provider_id,
            config.no_training,
            config.zero_retention,
            request_id,
        )
```

Update the function's docstring to document `allow_untrusted_provider` (Args + a Raises note that a non-compliant config still raises `ProviderConfigError` unless the flag is set). Leave everything after it (pseudonymize, `count_identifiers`/`IdentifierLeakError`, logging, dispatch, record) unchanged — the hard-stop must keep running.

- [ ] **Step 4: Run the tests, verify they pass**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/wegofwd_llm/test_gateway_untrusted.py -q`
Expected: PASS (3 tests). Also run the existing gateway tests to confirm no regression:
`.venv/bin/python -m pytest tests/kathai_chithiram/wegofwd_llm/ -q`

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/wegofwd_llm/gateway.py tests/kathai_chithiram/wegofwd_llm/test_gateway_untrusted.py
git commit -m "feat(wegofwd-llm): gateway synthetic-data escape (allow_untrusted_provider), default off"
```

---

## Task 2: Thread the flag through `generate_scene_script`

**Files:**
- Modify: `src/kathai_chithiram/generation/generator.py`
- Test: `tests/kathai_chithiram/generation/test_generator_untrusted.py`

**Interfaces:**
- Consumes: `run_generation(..., allow_untrusted_provider=)` (Task 1).
- Produces: `generate_scene_script(..., allow_untrusted_provider: bool = False)` — passed into every `run_generation` call; default `False` = unchanged.

- [ ] **Step 1: Write the failing test**

Create `tests/kathai_chithiram/generation/test_generator_untrusted.py`:

```python
"""generate_scene_script threads the synthetic-data escape into the gateway."""

from __future__ import annotations

import json

import pytest

from kathai_chithiram.errors import ProviderConfigError
from kathai_chithiram.generation.generator import generate_scene_script
from kathai_chithiram.privacy.pseudonymize import NameMapping
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, LLMResponse, ProviderConfig

# Reuse the repo's scene-script test helpers if present; otherwise a minimal valid
# script JSON string. Read tests/kathai_chithiram/generation/test_generator.py for the
# canonical _valid_script() helper and ScriptedProvider, and import/copy them here.
from tests.kathai_chithiram.generation.test_generator import (  # type: ignore
    ScriptedProvider,
    _mapping,
    _valid_script,
)

_NONCOMPLIANT = ProviderConfig(provider_id="qwen:test", no_training=False, zero_retention=False)


def test_untrusted_refused_by_default() -> None:
    with pytest.raises(ProviderConfigError):
        generate_scene_script(
            story_text="a synthetic story",
            mapping=_mapping(),
            provider=ScriptedProvider(replies=[json.dumps(_valid_script())]),
            config=_NONCOMPLIANT,
            request_id="req-1",
        )


def test_untrusted_allowed_with_flag() -> None:
    result = generate_scene_script(
        story_text="a synthetic story",
        mapping=_mapping(),
        provider=ScriptedProvider(replies=[json.dumps(_valid_script())]),
        config=_NONCOMPLIANT,
        request_id="req-1",
        allow_untrusted_provider=True,
    )
    assert result.script  # a validated scene script came back
```

> If importing helpers from `test_generator.py` is awkward, read that file and inline a `ScriptedProvider` + a `_valid_script()` here. The point: a non-compliant config is refused by default and accepted with the flag.

- [ ] **Step 2: Run the test, verify it fails**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/test_generator_untrusted.py -q`
Expected: FAIL — `generate_scene_script()` has no `allow_untrusted_provider`.

- [ ] **Step 3: Add and thread the parameter**

In `src/kathai_chithiram/generation/generator.py`:
- Add `allow_untrusted_provider: bool = False` to `generate_scene_script`'s keyword-only params (place it immediately after `max_attempts`, before `grounding`).
- Document it in the docstring: "When ``True``, permits a non-privacy-compliant provider to run (synthetic/dev data only). Default ``False`` keeps the no-training/zero-retention refusal. See the gateway."
- In **every** `run_generation(...)` call inside the function, add `allow_untrusted_provider=allow_untrusted_provider,`.

- [ ] **Step 4: Run the test, verify it passes**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/test_generator_untrusted.py -q`
Expected: PASS. Run existing generator tests too: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/ -q`.

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/generation/generator.py tests/kathai_chithiram/generation/test_generator_untrusted.py
git commit -m "feat(generation): thread allow_untrusted_provider through generate_scene_script"
```

---

## Task 3: `GeminiProvider`

**Files:**
- Create: `src/kathai_chithiram/wegofwd_llm/gemini_provider.py`
- Test: `tests/kathai_chithiram/wegofwd_llm/test_gemini_provider.py`

**Interfaces:**
- Consumes: `LLMRequest`, `LLMResponse` (`wegofwd_llm.provider`); `ProviderUnavailableError`, `ProviderResponseError`, `ProviderConfigError` (`kathai_chithiram.errors`).
- Produces: `GeminiProvider` (satisfies `LLMProvider`), `DEFAULT_GEMINI_MODEL`, `GEMINI_API_KEY_ENV`, `build_gemini_provider(*, model=…, effort=…, env=…) -> GeminiProvider`.

- [ ] **Step 1: Write the failing tests**

Create `tests/kathai_chithiram/wegofwd_llm/test_gemini_provider.py`:

```python
"""GeminiProvider: builds the google-genai call, JSON mode on schema, maps text out."""

from __future__ import annotations

from typing import Any

import pytest

from kathai_chithiram.errors import ProviderResponseError
from kathai_chithiram.wegofwd_llm.gemini_provider import GeminiProvider
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, ProviderConfig

_CFG = ProviderConfig(provider_id="gemini:test", no_training=False, zero_retention=False)


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, *, model: str, contents: str, config: dict[str, Any]) -> _FakeResponse:
        self.calls.append({"model": model, "contents": contents, "config": config})
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text: str = '{"ok": true}') -> None:
        self.models = _FakeModels(text)


def _req(**over: Any) -> LLMRequest:
    base: dict[str, Any] = dict(prompt="hello", config=_CFG, system_prompt="", output_schema=None)
    base.update(over)
    return LLMRequest(**base)


def test_completes_and_returns_text() -> None:
    client = _FakeClient(text='{"scene": 1}')
    provider = GeminiProvider(client=client, model="gemini-x")
    assert provider.complete(_req()).text == '{"scene": 1}'
    call = client.models.calls[0]
    assert call["model"] == "gemini-x"
    assert call["contents"] == "hello"


def test_json_mode_set_when_schema_present() -> None:
    client = _FakeClient()
    provider = GeminiProvider(client=client, model="gemini-x")
    provider.complete(_req(output_schema={"type": "object"}))
    assert client.models.calls[0]["config"]["response_mime_type"] == "application/json"


def test_system_instruction_passed_when_present() -> None:
    client = _FakeClient()
    provider = GeminiProvider(client=client, model="gemini-x")
    provider.complete(_req(system_prompt="be calm"))
    assert client.models.calls[0]["config"]["system_instruction"] == "be calm"


def test_empty_reply_raises() -> None:
    provider = GeminiProvider(client=_FakeClient(text="   "), model="gemini-x")
    with pytest.raises(ProviderResponseError):
        provider.complete(_req())
```

- [ ] **Step 2: Run the tests, verify they fail**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/wegofwd_llm/test_gemini_provider.py -q`
Expected: FAIL — module absent.

- [ ] **Step 3: Implement the provider**

Create `src/kathai_chithiram/wegofwd_llm/gemini_provider.py`:

```python
"""GeminiProvider — a concrete LLMProvider backed by Google's google-genai SDK.

Non-goal by construction: this provider does NOT assert a privacy posture. Whether a
request may carry real story text is decided by the ``ProviderConfig`` the caller
builds and enforced at the gateway (PRIVACY.md §6). The AI Studio free tier is not a
no-training / zero-retention endpoint, so callers give it a non-compliant config and it
runs only under the gateway's explicit synthetic-data escape.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Mapping
from typing import Any

from kathai_chithiram.errors import (
    ProviderConfigError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, LLMResponse

__all__ = [
    "DEFAULT_GEMINI_MODEL",
    "GEMINI_API_KEY_ENV",
    "GeminiProvider",
    "build_gemini_provider",
]

#: Default model; overridable. Model ids move fast — verify against the installed SDK.
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"


def _load_genai() -> Any:
    """Import the optional ``google-genai`` SDK, or raise ``ImportError`` if absent."""
    return importlib.import_module("google.genai")


class GeminiProvider:
    """Generate completions with a Gemini model via the google-genai SDK.

    Args:
        model: The Gemini model id.
        client: An injected google-genai client (tests supply a fake); when ``None``
            the SDK client is constructed from ``api_key``.
        api_key: The Gemini API key (AI Studio). Required when ``client`` is ``None``.

    Raises:
        ProviderUnavailableError: If the ``google-genai`` SDK is not installed.
    """

    def __init__(self, *, model: str = DEFAULT_GEMINI_MODEL, client: Any | None = None,
                 api_key: str | None = None) -> None:
        if client is None:
            try:
                genai = _load_genai()
            except ImportError as exc:
                raise ProviderUnavailableError(
                    f"gemini:{model}",
                    "the 'google-genai' SDK is not installed; install it with: "
                    "pip install 'kathai-chithiram[gemini]'",
                ) from exc
            client = genai.Client(api_key=api_key)
        self._client = client
        self._model = model

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Send ``request`` to Gemini and return its text reply.

        Args:
            request: The outbound request (prompt already pseudonymised by the gateway).

        Returns:
            The model's :class:`LLMResponse`.

        Raises:
            ProviderResponseError: If the model returns no usable text.
        """
        config: dict[str, Any] = {}
        if request.system_prompt:
            config["system_instruction"] = request.system_prompt
        if request.output_schema is not None:
            # JSON mode (KC-12 partial constraint): "return JSON". The scene-script
            # schema still reaches the model via the prompt; the validate-and-repair
            # loop is the correctness guarantee.
            config["response_mime_type"] = "application/json"
        response = self._client.models.generate_content(
            model=self._model, contents=request.prompt, config=config
        )
        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise ProviderResponseError(self._model, "the model returned no text content")
        return LLMResponse(text=text)


def build_gemini_provider(
    *, model: str = DEFAULT_GEMINI_MODEL, env: Mapping[str, str] | None = None
) -> GeminiProvider:
    """Build a GeminiProvider from ``GEMINI_API_KEY``; fails closed if the key is absent.

    Args:
        model: The Gemini model id.
        env: Environment mapping (defaults to ``os.environ``).

    Returns:
        A configured :class:`GeminiProvider`.

    Raises:
        ProviderConfigError: If ``GEMINI_API_KEY`` is not set.
    """
    source = os.environ if env is None else env
    key = source.get(GEMINI_API_KEY_ENV)
    if not key:
        raise ProviderConfigError(
            f"gemini:{model}",
            f"{GEMINI_API_KEY_ENV} is not set; cannot construct the Gemini provider",
        )
    return GeminiProvider(model=model, api_key=key)
```

> The `config` dict is passed straight to `generate_content` — the google-genai SDK accepts a dict and coerces it to `GenerateContentConfig`. If the installed SDK rejects the dict, switch to `google.genai.types.GenerateContentConfig(**config)` (lazy-import `google.genai.types`); the fake-client tests are unaffected because they read `config` as a mapping — in that case update the fake to accept the typed object. Verify against the installed SDK during this task.

- [ ] **Step 4: Run the tests, verify they pass**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/wegofwd_llm/test_gemini_provider.py -q`
Expected: PASS (4 tests). Ruff + mypy on the new file.

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/wegofwd_llm/gemini_provider.py tests/kathai_chithiram/wegofwd_llm/test_gemini_provider.py
git commit -m "feat(wegofwd-llm): GeminiProvider (google-genai, JSON mode, lazy import)"
```

---

## Task 4: `QwenProvider`

**Files:**
- Create: `src/kathai_chithiram/wegofwd_llm/qwen_provider.py`
- Test: `tests/kathai_chithiram/wegofwd_llm/test_qwen_provider.py`

**Interfaces:**
- Consumes: `LLMRequest`, `LLMResponse`; `ProviderUnavailableError`, `ProviderResponseError`, `ProviderConfigError`.
- Produces: `QwenProvider`, `DEFAULT_QWEN_MODEL`, `QWEN_API_KEY_ENV`, `QWEN_BASE_URL_ENV`, `build_qwen_provider(*, model=…, base_url=…, env=…) -> QwenProvider`.

- [ ] **Step 1: Write the failing tests**

Create `tests/kathai_chithiram/wegofwd_llm/test_qwen_provider.py`:

```python
"""QwenProvider: OpenAI-compatible chat.completions, JSON mode on schema, maps text out."""

from __future__ import annotations

from typing import Any

import pytest

from kathai_chithiram.errors import ProviderResponseError
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, ProviderConfig
from kathai_chithiram.wegofwd_llm.qwen_provider import QwenProvider

_CFG = ProviderConfig(provider_id="qwen:test", no_training=False, zero_retention=False)


class _Msg:
    def __init__(self, content: str) -> None:
        self.message = type("M", (), {"content": content})()


class _Completion:
    def __init__(self, content: str) -> None:
        self.choices = [_Msg(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Completion:
        self.calls.append(kwargs)
        return _Completion(self._content)


class _FakeClient:
    def __init__(self, content: str = '{"ok": true}') -> None:
        self.chat = type("C", (), {"completions": _FakeCompletions(content)})()


def _req(**over: Any) -> LLMRequest:
    base: dict[str, Any] = dict(prompt="hello", config=_CFG, system_prompt="", output_schema=None)
    base.update(over)
    return LLMRequest(**base)


def test_completes_and_returns_text() -> None:
    client = _FakeClient(content='{"scene": 1}')
    provider = QwenProvider(client=client, model="qwen-x")
    assert provider.complete(_req()).text == '{"scene": 1}'
    call = client.chat.completions.calls[0]
    assert call["model"] == "qwen-x"
    assert call["messages"][-1] == {"role": "user", "content": "hello"}


def test_system_message_added_when_present() -> None:
    client = _FakeClient()
    provider = QwenProvider(client=client, model="qwen-x")
    provider.complete(_req(system_prompt="be calm"))
    assert client.chat.completions.calls[0]["messages"][0] == {"role": "system", "content": "be calm"}


def test_json_mode_set_when_schema_present() -> None:
    client = _FakeClient()
    provider = QwenProvider(client=client, model="qwen-x")
    provider.complete(_req(output_schema={"type": "object"}))
    assert client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}


def test_empty_reply_raises() -> None:
    provider = QwenProvider(client=_FakeClient(content="  "), model="qwen-x")
    with pytest.raises(ProviderResponseError):
        provider.complete(_req())
```

- [ ] **Step 2: Run the tests, verify they fail**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/wegofwd_llm/test_qwen_provider.py -q`
Expected: FAIL — module absent.

- [ ] **Step 3: Implement the provider**

Create `src/kathai_chithiram/wegofwd_llm/qwen_provider.py`:

```python
"""QwenProvider — a concrete LLMProvider backed by an OpenAI-compatible Qwen endpoint.

Uses the ``openai`` SDK pointed at a Qwen-hosting base URL (e.g. DashScope's
OpenAI-compatible mode). Like every provider, it asserts no privacy posture of its own:
the gateway decides, from the caller's ``ProviderConfig``, whether real story text may
flow (a hosted Qwen API is treated non-compliant until its terms are verified).
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Mapping
from typing import Any

from kathai_chithiram.errors import (
    ProviderConfigError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, LLMResponse

__all__ = [
    "DEFAULT_QWEN_MODEL",
    "QWEN_API_KEY_ENV",
    "QWEN_BASE_URL_ENV",
    "QwenProvider",
    "build_qwen_provider",
]

DEFAULT_QWEN_MODEL = "qwen-plus"
QWEN_API_KEY_ENV = "QWEN_API_KEY"
QWEN_BASE_URL_ENV = "QWEN_BASE_URL"


def _load_openai() -> Any:
    """Import the optional ``openai`` SDK, or raise ``ImportError`` if absent."""
    return importlib.import_module("openai")


class QwenProvider:
    """Generate completions with a Qwen model via an OpenAI-compatible endpoint.

    Args:
        model: The Qwen model id.
        client: An injected OpenAI-compatible client (tests supply a fake); when
            ``None`` a client is built from ``api_key`` and ``base_url``.
        api_key: The API key for the Qwen host. Required when ``client`` is ``None``.
        base_url: The OpenAI-compatible base URL. Required when ``client`` is ``None``.

    Raises:
        ProviderUnavailableError: If the ``openai`` SDK is not installed.
    """

    def __init__(self, *, model: str = DEFAULT_QWEN_MODEL, client: Any | None = None,
                 api_key: str | None = None, base_url: str | None = None) -> None:
        if client is None:
            try:
                openai = _load_openai()
            except ImportError as exc:
                raise ProviderUnavailableError(
                    f"qwen:{model}",
                    "the 'openai' SDK is not installed; install it with: "
                    "pip install 'kathai-chithiram[qwen]'",
                ) from exc
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._client = client
        self._model = model

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Send ``request`` to the Qwen endpoint and return its text reply.

        Args:
            request: The outbound request (prompt already pseudonymised by the gateway).

        Returns:
            The model's :class:`LLMResponse`.

        Raises:
            ProviderResponseError: If the model returns no usable text.
        """
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        kwargs: dict[str, Any] = {"model": self._model, "messages": messages}
        if request.output_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
        completion = self._client.chat.completions.create(**kwargs)
        text = (completion.choices[0].message.content or "") if completion.choices else ""
        if not text.strip():
            raise ProviderResponseError(self._model, "the model returned no text content")
        return LLMResponse(text=text)


def build_qwen_provider(
    *, model: str = DEFAULT_QWEN_MODEL, base_url: str | None = None,
    env: Mapping[str, str] | None = None
) -> QwenProvider:
    """Build a QwenProvider from ``QWEN_API_KEY`` + base URL; fails closed if absent.

    Args:
        model: The Qwen model id.
        base_url: Override for the OpenAI-compatible base URL (else ``QWEN_BASE_URL``).
        env: Environment mapping (defaults to ``os.environ``).

    Returns:
        A configured :class:`QwenProvider`.

    Raises:
        ProviderConfigError: If the API key or base URL is missing.
    """
    source = os.environ if env is None else env
    key = source.get(QWEN_API_KEY_ENV)
    url = base_url or source.get(QWEN_BASE_URL_ENV)
    if not key:
        raise ProviderConfigError(f"qwen:{model}", f"{QWEN_API_KEY_ENV} is not set")
    if not url:
        raise ProviderConfigError(
            f"qwen:{model}", f"{QWEN_BASE_URL_ENV} is not set (OpenAI-compatible endpoint)"
        )
    return QwenProvider(model=model, api_key=key, base_url=url)
```

- [ ] **Step 4: Run the tests, verify they pass**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/wegofwd_llm/test_qwen_provider.py -q`
Expected: PASS (4 tests). Ruff + mypy on the new file.

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/wegofwd_llm/qwen_provider.py tests/kathai_chithiram/wegofwd_llm/test_qwen_provider.py
git commit -m "feat(wegofwd-llm): QwenProvider (OpenAI-compatible endpoint, JSON mode, lazy import)"
```

---

## Task 5: CLI provider selection + synthetic-data guard + exports

**Files:**
- Modify: `src/kathai_chithiram/wegofwd_llm/__init__.py`
- Modify: `src/kathai_chithiram/cli.py`
- Test: `tests/kathai_chithiram/test_cli_provider.py`

**Interfaces:**
- Consumes: `build_gemini_provider` (Task 3), `build_qwen_provider` (Task 4), `generate_scene_script(..., allow_untrusted_provider=)` (Task 2), the existing `_build_anthropic_provider`, `ProviderConfig`.
- Produces: `kc generate --provider {anthropic,gemini,qwen}` (default `anthropic`) and `--synthetic-data` (default off); a `_build_provider(name, *, model, effort)` factory; fail-closed when a non-ZDR provider is chosen without `--synthetic-data`.

Read `src/kathai_chithiram/cli.py` first: locate the `generate` subparser (where `--provider-no-train-zdr`, `--model`, `--effort` are added) and `_cmd_generate` (where the provider + `ProviderConfig` are built and `generate_scene_script` is called). Integrate the changes below into those existing locations.

- [ ] **Step 1: Write the failing tests**

Create `tests/kathai_chithiram/test_cli_provider.py`:

```python
"""CLI provider selection + the synthetic-data guard."""

from __future__ import annotations

import json

from kathai_chithiram import cli
from kathai_chithiram.wegofwd_llm import __all__ as seam_exports

# A scripted provider that returns a valid scene script (reuse the generation helper).
from tests.kathai_chithiram.generation.test_generator import (  # type: ignore
    ScriptedProvider,
    _valid_script,
)


def test_seam_reexports_new_providers() -> None:
    for name in ("GeminiProvider", "QwenProvider", "build_gemini_provider", "build_qwen_provider"):
        assert name in seam_exports


def test_generate_gemini_without_synthetic_flag_fails_closed(tmp_path, capsys) -> None:
    story = tmp_path / "s.txt"
    story.write_text("a synthetic story", encoding="utf-8")
    # Inject a provider so no key is needed; the guard must still refuse (non-ZDR + no flag).
    code = cli.main(
        ["generate", "--provider", "gemini", "--story", str(story), "--child-name", "Milo"],
        provider=ScriptedProvider(replies=[json.dumps(_valid_script())]),
    )
    assert code == 2
    assert "synthetic-data" in (capsys.readouterr().err.lower())


def test_generate_gemini_with_synthetic_flag_runs(tmp_path) -> None:
    story = tmp_path / "s.txt"
    story.write_text("a synthetic story", encoding="utf-8")
    code = cli.main(
        ["generate", "--provider", "gemini", "--synthetic-data", "--no-render",
         "--story", str(story), "--child-name", "Milo"],
        provider=ScriptedProvider(replies=[json.dumps(_valid_script())]),
    )
    assert code == 0
```

> Adjust the exact `generate` flags (`--story`, `--child-name`, `--no-render`) to the repo's real argument names by reading the `generate` subparser. The behaviours to assert are: (a) the seam re-exports the new names; (b) a non-ZDR provider without `--synthetic-data` exits non-zero with a message naming the flag; (c) with the flag it runs to success.

- [ ] **Step 2: Run the tests, verify they fail**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/test_cli_provider.py -q`
Expected: FAIL — flags/exports/factory absent.

- [ ] **Step 3a: Export the new providers**

In `src/kathai_chithiram/wegofwd_llm/__init__.py`, import and add to `__all__` (keep the list ordered as it is): `GeminiProvider`, `build_gemini_provider` (from `.gemini_provider`), `QwenProvider`, `build_qwen_provider` (from `.qwen_provider`).

- [ ] **Step 3b: Add the CLI flags**

In the `generate` subparser (beside `--model` / `--effort`), add:

```python
    gen.add_argument(
        "--provider", choices=["anthropic", "gemini", "qwen"], default="anthropic",
        help="generation provider (default: anthropic). gemini/qwen require --synthetic-data.",
    )
    gen.add_argument(
        "--synthetic-data", action="store_true",
        help="attest the input is SYNTHETIC/dev data, permitting a non-ZDR provider "
             "(gemini/qwen). Never use with real story data.",
    )
```
(Use the actual subparser variable name from the file, e.g. `gen`/`p_generate`.)

- [ ] **Step 3c: Add the provider factory**

Add near `_build_anthropic_provider`:

```python
def _build_provider(name: str, *, model: str, effort: str) -> "LLMProvider | None":
    """Construct the selected provider, printing a friendly error and returning None
    on a missing key/SDK (mirrors _build_anthropic_provider)."""
    from kathai_chithiram.errors import KathaiChithiramError

    try:
        if name == "anthropic":
            return _build_anthropic_provider(model=model, effort=effort)
        if name == "gemini":
            from kathai_chithiram.wegofwd_llm.gemini_provider import build_gemini_provider
            return build_gemini_provider()
        from kathai_chithiram.wegofwd_llm.qwen_provider import build_qwen_provider
        return build_qwen_provider()
    except KathaiChithiramError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None
```
(`_build_anthropic_provider` already handles its own model/effort + error printing and returns `None`; the `try/except` here covers the gemini/qwen builders.)

- [ ] **Step 3d: Wire selection, posture, and the guard into `_cmd_generate`**

Where `_cmd_generate` builds the provider + config today, replace with:

```python
    provider_name = args.provider
    if provider_name != "anthropic" and not args.synthetic_data:
        print(
            f"error: --provider {provider_name} is not a no-training/zero-retention "
            "provider; pass --synthetic-data to use it with SYNTHETIC data only "
            "(never real story data).",
            file=sys.stderr,
        )
        return 2
    if provider is None:
        provider = _build_provider(provider_name, model=args.model, effort=args.effort)
        if provider is None:
            return 2

    if provider_name == "anthropic":
        config = ProviderConfig(
            provider_id=f"anthropic:{args.model}:zdr-key",
            no_training=args.provider_no_train_zdr,
            zero_retention=args.provider_no_train_zdr,
        )
    else:
        # gemini/qwen: truthful non-compliant posture; gated behind --synthetic-data.
        config = ProviderConfig(
            provider_id=f"{provider_name}:{args.model}",
            no_training=False,
            zero_retention=False,
        )
```

And pass the escape into the generation call:

```python
        result = generate_scene_script(
            story_text=story_text,
            mapping=mapping,
            provider=provider,
            config=config,
            request_id=story_id,
            max_attempts=args.max_attempts,
            allow_untrusted_provider=args.synthetic_data,
            grounding=_grounding_from_env(),
        )
```
(Preserve the exact keyword set already present at that call site — add `allow_untrusted_provider=args.synthetic_data,` to it. `--model` currently defaults to the Anthropic model; that's fine — gemini/qwen use their own default when `args.model` is not meaningful, or the implementer may set the provider default model in the builder if `args.model` is the Anthropic default. Keep it simple: the builders use their own DEFAULT_*_MODEL and ignore `args.model` unless you add per-provider model flags later.)

- [ ] **Step 4: Run the tests, verify they pass**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/test_cli_provider.py -q`
Expected: PASS. Then the full CLI + generation suites: `.venv/bin/python -m pytest tests/kathai_chithiram/ -q`.

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/wegofwd_llm/__init__.py src/kathai_chithiram/cli.py tests/kathai_chithiram/test_cli_provider.py
git commit -m "feat(cli): --provider {anthropic,gemini,qwen} + --synthetic-data guard; export new providers"
```

---

## Task 6: Dependencies + docs (extras, ADR-006, CLAUDE.md)

**Files:**
- Modify: `pyproject.toml`
- Modify: `docs/ADR_006_domain_model_strategy.md`
- Modify: `CLAUDE.md`
- Test: none new (deps + docs) — run the full suite + ruff + mypy.

- [ ] **Step 1: Add the optional extras**

In `pyproject.toml` `[project.optional-dependencies]`, add (mirroring the `generation` extra's comment style):

```toml
# Gemini generation via the google-genai SDK (behind the wegofwd-llm seam).
gemini = [
    "google-genai>=1.0",
]
# Qwen generation via an OpenAI-compatible endpoint (behind the wegofwd-llm seam).
qwen = [
    "openai>=1.40",
]
```
Add `"kathai-chithiram[gemini]"` and `"kathai-chithiram[qwen]"` to the `dev` extra so the dev env can import the SDKs.

- [ ] **Step 2: Install and run the full suite**

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest tests -q
.venv/bin/ruff check .
.venv/bin/python -m mypy src
```
Expected: install pulls `google-genai` + `openai`; full suite green; ruff + mypy clean. If a git/network fetch of an SDK is unavailable in this environment, note it in the report and confirm the provider tests still pass with fakes (they import the SDK lazily, so absence does not break them); do not block the commit on network.

- [ ] **Step 3: Update ADR-006**

In `docs/ADR_006_domain_model_strategy.md`, add a short subsection recording: generation is multi-provider behind the `wegofwd-llm` seam (Anthropic / Gemini / Qwen); **Anthropic remains the default and the only privacy-compliant (ZDR) provider today**; Gemini (AI Studio free) and Qwen (hosted API) are **synthetic/dev only** behind the gateway's `allow_untrusted_provider` escape (`--synthetic-data`); routing **real** story data through Gemini/Qwen is gated on verifying no-training/zero-retention terms (Gemini via Vertex, or self-hosted Qwen) and building a compliant `ProviderConfig`.

- [ ] **Step 4: Update CLAUDE.md**

In `CLAUDE.md`, change the generation/model guidance so it no longer says "default to the latest Claude models". Replace with a provider-agnostic statement, e.g.: "Generation is multi-provider behind the `wegofwd-llm` seam (Anthropic, Gemini, Qwen). Anthropic is the default and the only no-training/zero-retention provider today; real story data may only go to a no-training/zero-retention provider. Gemini/Qwen are synthetic/dev only, behind `--synthetic-data`."

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml docs/ADR_006_domain_model_strategy.md CLAUDE.md
git commit -m "build+docs: [gemini]/[qwen] extras; ADR-006 + CLAUDE.md multi-provider"
```

---

## Final verification

- [ ] `.venv/bin/python -m pytest tests -q` — full suite green (existing + new).
- [ ] `.venv/bin/ruff check .` and `.venv/bin/python -m mypy src` — clean.
- [ ] Confirm the law holds: a non-compliant `ProviderConfig` is refused by `run_generation` unless `allow_untrusted_provider=True`; `kc generate --provider gemini` without `--synthetic-data` exits 2; `intake` exposes neither flag.
- [ ] Confirm the identifier hard-stop fires even under the synthetic override (Task 1 test).

## Self-review notes (author)

- **Spec coverage:** gateway escape → T1; generator thread → T2; GeminiProvider → T3; QwenProvider → T4; CLI selection + guard + exports → T5; extras + ADR-006 + CLAUDE.md → T6. Structured-output JSON-mode decision is in T3/T4; the "Anthropic stays default" decision is in T5/T6.
- **Type consistency:** `LLMRequest`/`LLMResponse`/`ProviderConfig`, `allow_untrusted_provider: bool`, `build_gemini_provider`/`build_qwen_provider`, `GeminiProvider`/`QwenProvider`, the three error types — used identically across tasks.
- **Verify-at-build items (flagged in-task, not placeholders):** exact google-genai `config` acceptance (dict vs typed), Gemini/Qwen model ids + Qwen base URL (env-driven), and the real `generate` subparser flag names + `_cmd_generate` call-site keywords. Each task tells the implementer to read the specific file and confirm before wiring.
- **Privacy law:** no task sets a fake compliant posture; the escape is default-off, loud, synthetic-only, and never on `intake`.
