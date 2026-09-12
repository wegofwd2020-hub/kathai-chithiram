# KC-21 Retrieval Grounding for Story Generation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ground Kathai Chithiram generation with cited practice passages retrieved from the `wegofwd-arivu` corpus — purely additive, so with no corpus / no match / the extra absent, generation is byte-identical to today.

**Architecture:** A `GroundingSource` seam with kathai-local types (`GroundingPassage`) keeps the core generation modules free of any `wegofwd-arivu` import; the concrete `ArivuGroundingSource` imports arivu lazily behind an optional `[grounding]` extra and fails safe. `generate_scene_script` queries the corpus with the pseudonymised story, injects a cited block into the per-story cacheable prompt prefix, and records the grounding source-ids on the result.

**Tech Stack:** Python ≥3.10, `wegofwd-arivu` (optional extra), pytest.

**Spec:** `docs/superpowers/specs/2026-09-12-retrieval-grounding-generation-design.md`

## Global Constraints

- **Language:** Python. Match surrounding style.
- **Exceptions:** no bare `except`; raise domain-specific errors with context. The concrete grounding source **fails safe** (returns `[]`, never raises) so grounding can never break generation; the `GroundingSource` protocol documents this contract, and the generator trusts it (no broad catch in the generator).
- **Docstrings:** OpenSpec-compliant on every public function/class.
- **Tests:** mock data only; **no real child data, no network, no live model**. Inject a `FakeGroundingSource`; never open a real corpus in tests.
- **Additive / graceful degradation (hard requirement):** with `grounding=None` (or empty results), `build_scene_script_system_prefix` output is **byte-identical to today's** and `GeneratedSceneScript.grounding_source_ids == ()`. Existing generator/prompt tests must stay green unchanged.
- **Privacy:** the corpus is queried with the **pseudonymised** story (`pseudonymize(story_text, mapping)`), never the raw name; retrieval is local/in-process; never log passage text or the query — only counts and `source_id`s.
- **No arivu import in core modules:** `wegofwd_arivu` is imported **only inside `ArivuGroundingSource` / `open_grounding_source`**, lazily. `grounding.py`'s protocol/types/`build_grounding_block` and `generator.py` must not import it.
- **Test env:** repo-local `.venv`. `.venv/bin/python -m pytest tests -q`; `.venv/bin/ruff check .`; `.venv/bin/mypy .` (or the repo's configured mypy invocation). Run the full suite green before each commit.
- **Frozen dataclasses** for the new value types; new fields defaulted (backward compatible).

---

### Task 1: The grounding seam — types, protocol, and the prompt block

**Files:**
- Create: `src/kathai_chithiram/generation/grounding.py`
- Test: `tests/kathai_chithiram/generation/test_grounding.py`

**Interfaces:**
- Produces: `GroundingPassage(text: str, source_id: str, licence_ref: str)` (frozen);
  `GroundingSource` Protocol with `retrieve(self, query: str, *, limit: int = 5) -> list[GroundingPassage]` (contract: fails safe, never raises);
  `build_grounding_block(passages: list[GroundingPassage]) -> str` (`""` when empty).

- [ ] **Step 1: Write the failing test**

Create `tests/kathai_chithiram/generation/test_grounding.py`:

```python
"""Tests for the grounding seam types and the prompt block (KC-21)."""

from __future__ import annotations

from kathai_chithiram.generation.grounding import (
    GroundingPassage,
    build_grounding_block,
)


def _passages() -> list[GroundingPassage]:
    return [
        GroundingPassage(text="Warm up to the toothbrush gradually.", source_id="cdc:oral-1", licence_ref="cdc:pd"),
        GroundingPassage(text="Use a visual schedule for the routine.", source_id="ed:idea-2", licence_ref="ed:pd"),
    ]


def test_block_is_empty_when_no_passages() -> None:
    assert build_grounding_block([]) == ""


def test_block_cites_each_source_and_forbids_verbatim() -> None:
    block = build_grounding_block(_passages())
    assert "cdc:oral-1" in block
    assert "ed:idea-2" in block
    assert "REFERENCE PRACTICE" in block
    assert "verbatim" in block.lower()
    # the passage text is present (shown to the model, not the child)
    assert "visual schedule" in block
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/test_grounding.py -q`
Expected: FAIL — `ModuleNotFoundError: kathai_chithiram.generation.grounding`.

- [ ] **Step 3: Write the module**

Create `src/kathai_chithiram/generation/grounding.py`:

```python
"""Retrieval grounding for scene-script generation (KC-21).

Optional: consumes the ``wegofwd-arivu`` corpus to inform generation with cited
practice passages (ADR-009 D1, ADR-010). Purely additive — with no corpus, no
matches, or the ``grounding`` extra absent, generation is unchanged. ``wegofwd-
arivu`` is imported lazily and only in :class:`ArivuGroundingSource` /
:func:`open_grounding_source`, so the core generation modules never depend on it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "ArivuGroundingSource",
    "GroundingPassage",
    "GroundingSource",
    "build_grounding_block",
    "open_grounding_source",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GroundingPassage:
    """A cited reference passage used to ground generation.

    Holds public reference material only — never personal data. ``source_id`` and
    ``licence_ref`` are log-safe identifiers (never document text).

    Args:
        text: The reference passage shown to the model (not to the child).
        source_id: The corpus source's stable, log-safe id.
        licence_ref: A reference to that source's recorded licence terms.
    """

    text: str
    source_id: str
    licence_ref: str


@runtime_checkable
class GroundingSource(Protocol):
    """A source of cited reference passages for grounding.

    Implementations MUST **fail safe**: return ``[]`` rather than raise, so
    grounding can never break generation.
    """

    def retrieve(self, query: str, *, limit: int = 5) -> list[GroundingPassage]:
        """Return up to ``limit`` cited passages relevant to ``query`` (or ``[]``)."""
        ...


def build_grounding_block(passages: list[GroundingPassage]) -> str:
    """Render cited reference passages as a prompt block.

    Args:
        passages: The retrieved passages; an empty list means "no grounding".

    Returns:
        A labelled, cited block for the system-prompt prefix, or ``""`` when
        there are no passages (so the prompt is unchanged).
    """
    if not passages:
        return ""
    lines = [
        "REFERENCE PRACTICE (cited; for grounding only)",
        "The following are published reference passages. Let them inform calm, "
        "accurate, literal steps. Do NOT quote them verbatim and do NOT copy "
        "their wording into narration or captions.",
        "",
    ]
    lines.extend(f"- [{p.source_id}] {p.text}" for p in passages)
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/test_grounding.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/generation/grounding.py tests/kathai_chithiram/generation/test_grounding.py
git commit -m "feat(grounding): GroundingSource seam + cited prompt block"
```

---

### Task 2: `ArivuGroundingSource` + `open_grounding_source` (lazy, fail-safe)

**Files:**
- Modify: `src/kathai_chithiram/generation/grounding.py`
- Test: `tests/kathai_chithiram/generation/test_grounding.py`

**Interfaces:**
- Consumes: `GroundingPassage`, `GroundingSource` (Task 1); `wegofwd_arivu.open_corpus`, `wegofwd_arivu.errors.StoreError` (imported lazily).
- Produces: `ArivuGroundingSource(db_path: str)` implementing `GroundingSource`;
  `open_grounding_source(db_path: str | None) -> GroundingSource | None` (returns `None` when `db_path` is falsy or the `wegofwd-arivu` extra is not installed).

- [ ] **Step 1: Write the failing tests**

Append to `tests/kathai_chithiram/generation/test_grounding.py`:

```python
from kathai_chithiram.generation.grounding import (  # noqa: E402
    ArivuGroundingSource,
    open_grounding_source,
)


def test_open_grounding_source_none_path_is_disabled() -> None:
    assert open_grounding_source(None) is None
    assert open_grounding_source("") is None


def test_open_grounding_source_none_when_extra_absent(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *a, **k):
        if name == "wegofwd_arivu" or name.startswith("wegofwd_arivu."):
            raise ImportError("wegofwd-arivu not installed")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    assert open_grounding_source("/tmp/whatever.corpus.db") is None


def test_arivu_source_fails_safe_on_missing_corpus() -> None:
    # Pointing at a path with no valid corpus must yield [] (never raise),
    # so grounding degrades to "no support" rather than breaking generation.
    src = ArivuGroundingSource("/nonexistent/dir/does-not-exist.corpus.db")
    assert src.retrieve("toothbrushing routine") == []
```

Note for the implementer: `test_arivu_source_fails_safe_on_missing_corpus` requires the `wegofwd-arivu` extra to be importable (install it into `.venv` if absent: `.venv/bin/python -m pip install -e '.[grounding]'` — but the extra is added in Task 6). If the extra is not yet installed when running this task, mark this one test `@pytest.mark.skipif` on `wegofwd_arivu` import failure so the suite stays green; the fail-safe path is still covered by `test_open_grounding_source_none_when_extra_absent`. Prefer installing the extra locally so the test runs for real.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/test_grounding.py -q`
Expected: FAIL — `ImportError: cannot import name 'ArivuGroundingSource'`.

- [ ] **Step 3: Add the concrete source + factory**

Append to `src/kathai_chithiram/generation/grounding.py`:

```python
def open_grounding_source(db_path: str | None) -> GroundingSource | None:
    """Build a grounding source over the corpus at ``db_path``, or ``None``.

    Returns ``None`` (grounding off) when ``db_path`` is falsy or the optional
    ``wegofwd-arivu`` dependency is not installed — the caller then generates
    exactly as it does without grounding.

    Args:
        db_path: Filesystem path to a ``wegofwd-arivu`` SQLite corpus, or ``None``.

    Returns:
        An :class:`ArivuGroundingSource`, or ``None`` when grounding is unavailable.
    """
    if not db_path:
        return None
    try:
        import wegofwd_arivu  # noqa: F401  (probe the optional extra)
    except ImportError:
        logger.info("grounding disabled: the 'grounding' extra (wegofwd-arivu) is not installed")
        return None
    return ArivuGroundingSource(db_path)


@dataclass(frozen=True)
class ArivuGroundingSource:
    """A :class:`GroundingSource` backed by a local ``wegofwd-arivu`` SQLite corpus.

    Fails safe: any corpus error (missing/invalid DB, read error) returns ``[]``,
    so grounding is best-effort and never breaks generation. ``wegofwd-arivu`` is
    imported here, lazily, so importing this module never requires the extra.

    Args:
        db_path: Filesystem path to the corpus database.
    """

    db_path: str

    def retrieve(self, query: str, *, limit: int = 5) -> list[GroundingPassage]:
        """Retrieve up to ``limit`` cited passages for ``query``; ``[]`` on any error."""
        from wegofwd_arivu import open_corpus
        from wegofwd_arivu.errors import StoreError

        try:
            with open_corpus(self.db_path) as corpus:
                chunks = corpus.retrieve(query, limit=limit)
        except (StoreError, OSError) as exc:
            logger.warning(
                "grounding retrieval failed (%s); proceeding ungrounded", type(exc).__name__
            )
            return []
        return [
            GroundingPassage(text=c.text, source_id=c.source_id, licence_ref=c.licence_ref)
            for c in chunks
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/test_grounding.py -q`
Expected: PASS (with the fail-safe test running if the extra is installed, else skipped).

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/generation/grounding.py tests/kathai_chithiram/generation/test_grounding.py
git commit -m "feat(grounding): lazy fail-safe ArivuGroundingSource + factory"
```

---

### Task 3: Prompt prefix accepts an optional grounding block

**Files:**
- Modify: `src/kathai_chithiram/generation/scene_script_prompt.py`
- Test: `tests/kathai_chithiram/generation/test_scene_script_prompt.py`

**Interfaces:**
- Produces: `build_scene_script_system_prefix(*, child_token: str = DEFAULT_CHILD_TOKEN, grounding_block: str = "") -> str` — when `grounding_block` is non-empty it is inserted (after the safety rules, before `OUTPUT FORMAT`); when `""` the output is byte-identical to the pre-KC-21 prefix.
- Consumes: nothing new.

- [ ] **Step 1: Write the failing tests**

Append to `tests/kathai_chithiram/generation/test_scene_script_prompt.py`:

```python
# --- KC-21: optional grounding block ---------------------------------------


def test_empty_grounding_block_is_byte_identical() -> None:
    base = build_scene_script_system_prefix(child_token="CHILD")
    with_empty = build_scene_script_system_prefix(child_token="CHILD", grounding_block="")
    assert with_empty == base


def test_grounding_block_is_inserted_when_present() -> None:
    block = "REFERENCE PRACTICE (cited; for grounding only)\n- [cdc:oral-1] warm up gradually"
    prefix = build_scene_script_system_prefix(child_token="CHILD", grounding_block=block)
    assert "cdc:oral-1" in prefix
    assert "REFERENCE PRACTICE" in prefix
    # the safety rules and the contract are still present
    assert "You MUST" in prefix
    assert "total_duration_s" in prefix
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/test_scene_script_prompt.py -k grounding -v`
Expected: FAIL — `build_scene_script_system_prefix() got an unexpected keyword argument 'grounding_block'`.

- [ ] **Step 3: Add the parameter**

In `src/kathai_chithiram/generation/scene_script_prompt.py`, change the signature of
`build_scene_script_system_prefix` to accept `grounding_block: str = ""` and insert it into the
`sections` list only when non-empty, immediately **after** the `safety` entry and its following
blank line, before `"OUTPUT FORMAT"`. The existing body builds a `sections` list beginning with
`[safety, "", "OUTPUT FORMAT", ...]`; change that start to:

```python
    sections: list[str] = [safety]
    if grounding_block:
        sections += ["", grounding_block]
    sections += [
        "",
        "OUTPUT FORMAT",
        # ... the rest of the existing sections unchanged ...
```

Keep every other section exactly as-is. Update the function's docstring Args to document
`grounding_block` (optional cited reference block; empty means the prefix is unchanged).
Also update `build_scene_script_system_prompt` **only if** it needs to thread the new argument
— it does NOT (grounding is applied at the prefix level by the generator, Task 4); leave
`build_scene_script_system_prompt` unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/test_scene_script_prompt.py -q`
Expected: PASS — including all pre-existing prompt tests (the empty-block path is byte-identical).

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/generation/scene_script_prompt.py tests/kathai_chithiram/generation/test_scene_script_prompt.py
git commit -m "feat(generation): optional grounding block in the system prefix"
```

---

### Task 4: Wire grounding into `generate_scene_script`

**Files:**
- Modify: `src/kathai_chithiram/generation/generator.py`
- Test: `tests/kathai_chithiram/generation/test_generator.py`

**Interfaces:**
- Consumes: `GroundingSource`, `build_grounding_block` (Task 1); `build_scene_script_system_prefix(..., grounding_block=)` (Task 3); `pseudonymize` from `kathai_chithiram.privacy`.
- Produces: `generate_scene_script(..., grounding: GroundingSource | None = None)`;
  `GeneratedSceneScript` gains `grounding_source_ids: tuple[str, ...]` (default `()`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/kathai_chithiram/generation/test_generator.py`:

```python
from dataclasses import dataclass, field  # noqa: E402
from kathai_chithiram.generation.grounding import GroundingPassage  # noqa: E402


@dataclass
class FakeGroundingSource:
    passages: list[GroundingPassage]
    queries: list[str] = field(default_factory=list)

    def retrieve(self, query: str, *, limit: int = 5) -> list[GroundingPassage]:
        self.queries.append(query)
        return list(self.passages)


def test_grounding_injects_block_and_records_source_ids() -> None:
    passages = [
        GroundingPassage(text="warm up to the brush", source_id="cdc:oral-1", licence_ref="cdc:pd"),
        GroundingPassage(text="use a visual schedule", source_id="cdc:oral-1", licence_ref="cdc:pd"),
        GroundingPassage(text="first dental visit tips", source_id="ed:idea-2", licence_ref="ed:pd"),
    ]
    grounding = FakeGroundingSource(passages)
    provider = ScriptedProvider(replies=[json.dumps(_valid_script())])
    result = generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
        grounding=grounding,
    )
    # source ids recorded, de-duplicated, order-preserving
    assert result.grounding_source_ids == ("cdc:oral-1", "ed:idea-2")
    # the cited block reached the system prompt
    assert "cdc:oral-1" in provider.requests[0].system_prompt
    assert "REFERENCE PRACTICE" in provider.requests[0].system_prompt


def test_grounding_query_is_pseudonymised() -> None:
    grounding = FakeGroundingSource([])
    generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=ScriptedProvider(replies=[json.dumps(_valid_script())]),
        config=COMPLIANT,
        request_id="req-1",
        grounding=grounding,
    )
    assert grounding.queries, "grounding was queried"
    q = grounding.queries[0]
    assert MOCK_CHILD_NAME not in q          # real name never sent to the corpus
    assert "CHILD" in q                       # the token took its place


def test_no_grounding_leaves_prompt_and_ids_unchanged() -> None:
    provider = ScriptedProvider(replies=[json.dumps(_valid_script())])
    result = generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
    )
    assert result.grounding_source_ids == ()
    assert "REFERENCE PRACTICE" not in provider.requests[0].system_prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/test_generator.py -k grounding -v`
Expected: FAIL — `generate_scene_script() got an unexpected keyword argument 'grounding'`.

- [ ] **Step 3: Implement the wiring**

In `src/kathai_chithiram/generation/generator.py`:

3a. Add imports:
```python
from kathai_chithiram.generation.grounding import GroundingSource, build_grounding_block
from kathai_chithiram.privacy.pseudonymize import pseudonymize
```
(`NameMapping` is already imported; confirm `pseudonymize` import path matches the module — it is `kathai_chithiram.privacy.pseudonymize.pseudonymize`, the same function the gateway uses.)

3b. Add the field to `GeneratedSceneScript` (after `attempts`), keeping it frozen and defaulted:
```python
    grounding_source_ids: tuple[str, ...] = ()
```
Document it in the class docstring Args: "The de-duplicated corpus source ids that grounded this script (empty when generation was ungrounded)."

3c. Add the parameter to `generate_scene_script` (after `max_attempts`, before `clock`):
```python
    grounding: GroundingSource | None = None,
```
Document it: "Optional corpus grounding source; when provided, cited practice passages relevant to the (pseudonymised) story are injected into the prompt prefix. Must fail safe (never raise). ``None`` → generation is ungrounded."

3d. **Before** the attempt loop (right after the `request_id`/`max_attempts` validation, before building `system_prefix`), compute grounding once:
```python
    # Grounding is per-story (constant across repair attempts). Query the corpus
    # with the pseudonymised story so the child's name never reaches it (retrieval
    # is local and the corpus holds no personal data). Empty/absent -> no grounding.
    if grounding is not None:
        passages = grounding.retrieve(pseudonymize(story_text, mapping))
    else:
        passages = []
    grounding_block = build_grounding_block(passages)
    grounding_source_ids = tuple(dict.fromkeys(p.source_id for p in passages))
```

3e. Pass `grounding_block` into the prefix build:
```python
    system_prefix = build_scene_script_system_prefix(
        child_token=mapping.token, grounding_block=grounding_block
    )
```

3f. Include the ids on **every** `return GeneratedSceneScript(...)` (the success return inside the loop):
```python
        return GeneratedSceneScript(
            script=script,
            records=tuple(records),
            attempts=attempt,
            grounding_source_ids=grounding_source_ids,
        )
```
(The exhaustion path still `raise`s `SceneScriptGenerationError` — unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/test_generator.py -q`
Expected: PASS — the three new tests plus every existing generator test (ungrounded default unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/generation/generator.py tests/kathai_chithiram/generation/test_generator.py
git commit -m "feat(generation): ground scene-script generation via optional corpus retrieval"
```

---

### Task 5: Exports + CLI wiring (`KC_ARIVU_DB`)

**Files:**
- Modify: `src/kathai_chithiram/generation/__init__.py`
- Modify: `src/kathai_chithiram/cli.py`
- Test: `tests/kathai_chithiram/generation/test_grounding.py` (exports); `tests/kathai_chithiram/test_cli_grounding.py` (create)

**Interfaces:**
- Consumes: `open_grounding_source` (Task 2), `generate_scene_script(..., grounding=)` (Task 4).
- Produces: the grounding names re-exported from `kathai_chithiram.generation`; `_cmd_generate` passing a grounding source built from the `KC_ARIVU_DB` env var.

- [ ] **Step 1: Write the failing tests**

Append to `tests/kathai_chithiram/generation/test_grounding.py`:

```python
def test_generation_package_reexports_grounding() -> None:
    import kathai_chithiram.generation as gen

    assert hasattr(gen, "open_grounding_source")
    assert hasattr(gen, "GroundingSource")
    assert hasattr(gen, "GroundingPassage")
    assert hasattr(gen, "build_grounding_block")
```

Create `tests/kathai_chithiram/test_cli_grounding.py`:

```python
"""KC-21: the generate CLI reads KC_ARIVU_DB to build a grounding source."""

from __future__ import annotations

from kathai_chithiram import cli


def test_grounding_from_env_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("KC_ARIVU_DB", raising=False)
    assert cli._grounding_from_env() is None


def test_grounding_from_env_disabled_when_extra_absent(monkeypatch) -> None:
    monkeypatch.setenv("KC_ARIVU_DB", "/tmp/x.corpus.db")
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *a, **k):
        if name == "wegofwd_arivu" or name.startswith("wegofwd_arivu."):
            raise ImportError("absent")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    assert cli._grounding_from_env() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/test_grounding.py::test_generation_package_reexports_grounding tests/kathai_chithiram/test_cli_grounding.py -q`
Expected: FAIL — missing re-exports / `cli._grounding_from_env` undefined.

- [ ] **Step 3: Add the re-exports and CLI wiring**

3a. In `src/kathai_chithiram/generation/__init__.py`, import and add to `__all__` (keep the list ordered as it is today): `GroundingPassage`, `GroundingSource`, `build_grounding_block`, `open_grounding_source` (and optionally `ArivuGroundingSource`) from `kathai_chithiram.generation.grounding`.

3b. In `src/kathai_chithiram/cli.py`:
- Add the import: `from kathai_chithiram.generation import open_grounding_source` (alongside the existing `from kathai_chithiram.generation import ...`).
- Add a small helper near the other private helpers:
```python
_ARIVU_DB_ENV = "KC_ARIVU_DB"


def _grounding_from_env() -> "GroundingSource | None":
    """Build a corpus grounding source from KC_ARIVU_DB, or None if unset/absent."""
    return open_grounding_source(os.environ.get(_ARIVU_DB_ENV))
```
(Import `GroundingSource` under `TYPE_CHECKING` for the annotation, or annotate as `object | None` to avoid a runtime import; match the file's existing typing style.)
- In `_cmd_generate`, pass it into the call:
```python
        result = generate_scene_script(
            story_text=story_text,
            mapping=mapping,
            provider=provider,
            config=config,
            request_id=story_id,
            max_attempts=args.max_attempts,
            grounding=_grounding_from_env(),
        )
```
Leave the offline path untouched (offline generation does not use the LLM prompt; no grounding there).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/kathai_chithiram/generation/test_grounding.py tests/kathai_chithiram/test_cli_grounding.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kathai_chithiram/generation/__init__.py src/kathai_chithiram/cli.py tests/kathai_chithiram/generation/test_grounding.py tests/kathai_chithiram/test_cli_grounding.py
git commit -m "feat(cli): wire KC_ARIVU_DB grounding into kc generate; export grounding seam"
```

---

### Task 6: The `[grounding]` extra + docs

**Files:**
- Modify: `pyproject.toml`
- Modify: `docs/SCENE_SCRIPT_CONTRACT.md`, `docs/STATE_OF_PLAY.md`

No new tests (dependency + docs). This task installs the extra so Task 2's fail-safe test can run for real, and records the feature.

- [ ] **Step 1: Add the optional extra**

In `pyproject.toml` `[project.optional-dependencies]`, add (mirroring the `[render]`/`[generation]` comment style):
```toml
# Retrieval grounding (KC-21): the wegofwd-arivu corpus that generation queries to
# ground scene scripts in cited practice. Optional — the core pipeline degrades to
# ungrounded generation when it is absent. Set KC_ARIVU_DB to a corpus path to enable.
grounding = [
    "wegofwd-arivu @ git+https://github.com/wegofwd2020-hub/wegofwd-arivu@main",
]
```
Also add `"kathai-chithiram[grounding]"` to the `dev` extra so the dev env can run the fail-safe test for real.

- [ ] **Step 2: Install and run the full suite**

Run:
```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest tests -q
.venv/bin/ruff check .
.venv/bin/mypy .
```
Expected: install pulls `wegofwd-arivu`; full suite green (now including Task 2's fail-safe test running for real); ruff + mypy clean. If the git dependency cannot be fetched in this environment, note it in the report and keep Task 2's test skip-guarded; do not block the commit on network.

- [ ] **Step 3: Document it**

- `docs/SCENE_SCRIPT_CONTRACT.md`: near the generation description, add a sentence: generation optionally grounds the scene script in cited corpus passages (KC-21) when `KC_ARIVU_DB` points at a `wegofwd-arivu` corpus; grounding is additive and never bypasses validation or the human-review gate.
- `docs/STATE_OF_PLAY.md`: in the status table / what's-next, note that arivu retrieval grounding is **wired (KC-21), dormant until a corpus is ingested**.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml docs/SCENE_SCRIPT_CONTRACT.md docs/STATE_OF_PLAY.md
git commit -m "build+docs: add [grounding] extra; note KC-21 retrieval grounding"
```

---

## Final verification

- [ ] `.venv/bin/python -m pytest tests -q` — full suite green (721 pre-existing + the new grounding tests).
- [ ] `.venv/bin/ruff check .` and `.venv/bin/mypy .` — clean. Ensure `from typing import Any`/`Protocol` imports exist where used, and the lazy `wegofwd_arivu` import does not trip mypy (it may need `# type: ignore[import-untyped]` or a note if arivu ships no stubs — handle per the repo's mypy config).
- [ ] Confirm the ungrounded path is byte-identical: existing `test_scene_script_prompt.py` / `test_generator.py` pass unchanged.

## Self-review notes (author)

- **Spec coverage:** grounding seam+types+block → T1; lazy fail-safe concrete source + factory → T2; prefix block param (byte-identical when empty) → T3; generator wiring (pseudonymised query, injected block, recorded source-ids) → T4; exports + CLI `KC_ARIVU_DB` → T5; `[grounding]` extra + docs → T6. Privacy, graceful degradation, and "no arivu import in core" are enforced in the Global Constraints and each relevant task.
- **Type consistency:** `GroundingPassage(text, source_id, licence_ref)`, `GroundingSource.retrieve(query, *, limit=5) -> list[GroundingPassage]`, `build_grounding_block(list[GroundingPassage]) -> str`, `open_grounding_source(str | None) -> GroundingSource | None`, `generate_scene_script(..., grounding=None)`, `GeneratedSceneScript.grounding_source_ids: tuple[str, ...]` — used identically across tasks.
- **No live model / network:** all tests use `ScriptedProvider` + `FakeGroundingSource`; the only real-corpus touch is Task 2's fail-safe test on a nonexistent path (skip-guarded if the extra is absent).
