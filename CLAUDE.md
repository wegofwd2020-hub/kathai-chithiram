# Kathai Chithiram — CLAUDE.md

Durable instructions for working in this repo. Read before writing code.

## What this is
Kathai Chithiram turns a parent's written story into a short, calm, captioned
animation designed to be understood by a child with special needs. Pipeline:
`parent story → generation (wegofwd-llm) → scene script → renderer → animation`.

## Sensitivity (read first)
This repo processes **personal stories about real children**, often children with
disabilities. Treat all story text and child data as special-category data.
- Obey `PRIVACY.md` (collection, retention, deletion, no-training, minimization).
- Obey `docs/CONTENT_SAFETY.md` for anything that affects generated output.
- Never log raw story text or a child's real name in plaintext.

## Architecture rules
- The **scene script is the contract** (`docs/SCENE_SCRIPT_CONTRACT.md`). Generation
  emits a valid scene script; renderers consume it. Generation never calls a
  renderer directly.
- Generation goes through the shared **`wegofwd-llm`** seam (provider-agnostic). Do
  not hard-code a single LLM provider.
- A scene script is **validated against the contract + safety rules before any
  rendering**. Invalid scripts are rejected, not rendered.

## Code conventions (WeGoFwd standards)
- **Language:** Python. All application code is Python.
- **Exception handling:** every function handles errors explicitly; do not swallow
  exceptions — raise domain-specific errors with context. No bare `except`.
- **Docstrings:** OpenSpec-compliant docstrings on every public function/class.
- **Tests:** every new function ships with a test file and **mock data**. Tests live
  in `tests/` mirroring source layout. Renderers must pass the shared scene-script
  conformance suite (mock scripts → asserts).
- **No real child data in tests or fixtures** — use synthetic mock stories only.

## Commands
- `pytest` — run tests
- `ruff check .` / `mypy .` — lint / typecheck

## Current state
Prototype: two reference renderers (`generate_animation.py` v1 matplotlib,
`blender_animation.py` v2 Blender) and one hand-built story ("Silas Shines His
Smile"). Human review gate is required before any output reaches a child.

## Gotchas
- Keep the human-in-the-loop review until automated safety enforcement is tested.
- The child's real name is a render-time substitution only — it must not appear in
  stored scene scripts or logs.
