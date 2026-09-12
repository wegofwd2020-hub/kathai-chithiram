# KC-21 — Retrieval grounding for story generation — design

Status: proposed (awaiting review)
Date: 2026-09-12
Ticket: KC-21 (ADR-009 rollout — "retrieval grounding for story generation"). Ungated.
Shaping ADRs: ADR-009 D1 (Kathai Chithiram retrieves from the corpus to *ground generation*),
ADR-010 (retrieval-first; facts in the corpus, not weights), ADR-011 (rights/provenance).
Consumes: the `wegofwd-arivu` corpus (`SqliteCorpus.retrieve`, merged PR #4).

## Problem

Generation today (`generation/generator.py`) turns a parent's story into a scene script from
the model's priors plus the safety/contract prompt. ADR-009 D1 says the animation should be
*grounded*: "a story about a first dental visit informed by published desensitisation practice
rather than a model's priors." The `wegofwd-arivu` corpus now exists and exposes lexical
retrieval (`open_corpus(path).retrieve(query, limit) -> list[Chunk]`, `Chunk = text +
source_id + licence_ref + currency`, returning `[]` on no match). This ticket wires that
retrieval into generation as an **additive, optional** grounding step.

## Goal and non-goals

**Goal.** Before generating, retrieve the most relevant cited practice passages from the corpus
(queried with the pseudonymised story) and inject them into the generation prompt as a labelled,
cited "reference practice" block, so the scene script is informed by published practice. Record
which sources grounded each script. **The feature is purely additive: with no corpus, no
matches, or the dependency absent, generation behaves exactly as today.**

**Non-goals.**
- Ingesting the corpus (a separate operational run; the corpus may be empty — grounding then
  no-ops). This ships *ready and dormant*.
- Changing the scene-script contract, the validator, the repair loop, or the human-review gate.
  Grounding informs the prompt; the output still passes `validate_scene_script` and KC-7 review.
- Vector/semantic retrieval (arivu is lexical FTS today; this seam is agnostic to which).
- Showing citations to the child (the animation is child-facing; grounding is generation-time
  only). Source ids are recorded for audit, not rendered.

## Decisions from brainstorming

- **Query = the pseudonymised story text** (data minimisation; and retrieval is local anyway).
- **Dependency = an optional extra `[grounding]`**, lazily imported; absent → grounding skipped.
- **Record the grounding source ids** on the generation result (audit/traceability).
- **Graceful degradation is a hard requirement**, not a nicety.

## Components and data flow

### 1. `GroundingSource` seam (new) — `generation/grounding.py`
Kathai defines its own tiny types so the core generation modules never import `wegofwd-arivu`:

```python
@dataclass(frozen=True)
class GroundingPassage:
    text: str
    source_id: str
    licence_ref: str

class GroundingSource(Protocol):
    def retrieve(self, query: str, *, limit: int = 5) -> list[GroundingPassage]: ...
```

- `build_grounding_block(passages: list[GroundingPassage]) -> str` — renders the cited
  reference-practice block for the prompt. **Empty passages → `""`** (so the prompt is
  unchanged). The block instructs: *"The following are published reference passages (cited by
  source). Let them inform calm, accurate, literal steps. Do NOT quote them verbatim and do NOT
  copy their wording into narration."* Each passage is shown with its `source_id`.

### 2. `ArivuGroundingSource` (new, concrete) — same module, lazy arivu import
- Factory `open_grounding_source(db_path: str | None) -> GroundingSource | None`:
  - `db_path` falsy → returns `None` (grounding off).
  - imports `wegofwd_arivu` lazily; `ImportError` (extra not installed) → returns `None`.
  - otherwise returns an `ArivuGroundingSource` bound to the corpus path.
- `ArivuGroundingSource.retrieve` opens the corpus (`open_corpus(path)`), calls
  `corpus.retrieve(query, limit=limit)`, maps each `Chunk` → `GroundingPassage`
  (`text`, `source_id`, `licence_ref`), and returns them. **Fails safe**: any
  `StoreError`/`OSError`/missing-file → return `[]` (log a safe warning; grounding is
  best-effort, never breaks generation). Never raises to the caller.

### 3. `generate_scene_script` wiring — `generation/generator.py`
- New optional keyword `grounding: GroundingSource | None = None`.
- Once per call (constant across repair attempts), **before the loop**:
  - `query = pseudonymize(story_text, mapping)` (the same minimised text the model sees).
  - `passages = grounding.retrieve(query, limit=…) if grounding else []` (wrapped so a
    misbehaving source can never break generation — but the concrete source already fails safe).
  - `grounding_block = build_grounding_block(passages)`.
- Pass `grounding_block` into `build_scene_script_system_prefix(...)` so it sits inside the
  **per-story cacheable prefix** (constant across that story's attempts; KC-12's caching holds).
- `GeneratedSceneScript` gains `grounding_source_ids: tuple[str, ...]` — the de-duplicated
  source ids that grounded this script (empty tuple when none). Audit/traceability.

### 4. Prompt prefix — `generation/scene_script_prompt.py`
- `build_scene_script_system_prefix(*, child_token=…, grounding_block: str = "")` — when
  `grounding_block` is non-empty, insert it as a clearly-delimited section (after the safety
  rules / before the worked example). When `""`, the prefix is **byte-identical to today's**
  (existing prompt tests unaffected; cache behaviour unchanged).

### 5. CLI wiring — `cli.py` (`kc generate`)
- Read a corpus DB path from config/env (`KC_ARIVU_DB`). Build `open_grounding_source(path)`
  and pass it to `generate_scene_script`. Unset / extra absent → `None` → generation as today.

### 6. Dependency — `pyproject.toml`
```toml
[project.optional-dependencies]
grounding = ["wegofwd-arivu @ git+https://github.com/wegofwd2020-hub/wegofwd-arivu@main"]
```
Mirrors the `[render]` / `[generation]` optional-extra pattern; core install stays dependency-light.

```
generate_scene_script(story_text, mapping, grounding?)
  query = pseudonymize(story_text, mapping)          # minimised; local
  passages = grounding.retrieve(query) or []          # fails safe -> []
  block = build_grounding_block(passages)             # [] -> ""
  prefix = build_scene_script_system_prefix(..., grounding_block=block)   # ""-> today's prefix
  → run_generation (privacy guards unchanged) → LLM → validate → repair loop
  → GeneratedSceneScript(..., grounding_source_ids=dedup(p.source_id for p in passages))
```

## Privacy & safety

- The corpus query is the **pseudonymised** story; retrieval is **local, in-process**
  (`SqliteCorpus` over a local DB), no network, and the corpus **holds no personal data**
  (ADR-009 D6). No child identifier leaves the machine via grounding.
- Injected passages are **public reference material** with log-safe `source_id`/`licence_ref`
  (ADR-011); they are shown to the *model*, never to the child.
- Grounding does **not** bypass any safety layer: the output still passes
  `validate_scene_script` (content-safety cross-field rules) and the KC-7 human-review gate.
  The block explicitly forbids verbatim copying, so retrieved wording cannot leak into
  child-facing narration unreviewed.
- Logs: never log passage text or the query; only counts and `source_id`s (log-safe).

## Error handling

- Concrete source fails safe (`[]`) on any corpus error / missing file / absent extra — grounding
  is best-effort. `generate_scene_script` also defensively treats a `None`/empty return as "no
  grounding". No new exception can break generation.
- No bare excepts; the concrete source catches `wegofwd_arivu`'s `StoreError` and `OSError`
  explicitly and returns `[]` with a safe warning log.

## Testing (mock data only; no real child data; no live model; no network)

- **`build_grounding_block`**: passages → a block containing each `source_id` and the
  don't-quote-verbatim instruction; `[]` → `""`.
- **`generate_scene_script` with a `FakeGroundingSource`** (returns fixed `GroundingPassage`s):
  the built prefix contains the cited block; `result.grounding_source_ids` == the deduped ids;
  attempts still validated/repaired as before.
- **No grounding** (`grounding=None`): the prefix is byte-identical to the no-grounding prefix;
  `grounding_source_ids == ()`; existing generator/prompt tests unchanged.
- **Privacy**: the query passed to the source contains the child *token*, not the real name
  (assert on the `FakeGroundingSource`'s recorded query).
- **`ArivuGroundingSource` fails safe**: with the `wegofwd-arivu` extra absent (simulate
  `ImportError`) `open_grounding_source(path)` → `None`; with a corpus error, `retrieve` → `[]`.
- **`open_grounding_source(None)` → `None`** (grounding off by default).
- Cache invariant: a grounded prefix is constant across a story's repair attempts (reuses the
  KC-12 cacheable-prefix test pattern).

## Files touched

- `src/kathai_chithiram/generation/grounding.py` (create) — `GroundingPassage`,
  `GroundingSource`, `build_grounding_block`, `ArivuGroundingSource`, `open_grounding_source`.
- `src/kathai_chithiram/generation/scene_script_prompt.py` — `build_scene_script_system_prefix`
  gains `grounding_block=""`.
- `src/kathai_chithiram/generation/generator.py` — `grounding` param; query/retrieve/inject;
  `GeneratedSceneScript.grounding_source_ids`.
- `src/kathai_chithiram/generation/__init__.py` — export the new public names.
- `src/kathai_chithiram/cli.py` — wire `KC_ARIVU_DB` → `open_grounding_source` into `kc generate`.
- `pyproject.toml` — add the `[grounding]` extra.
- `tests/…` — mirrored tests (grounding seam, generator wiring, prompt prefix, CLI).
- Docs: `docs/SCENE_SCRIPT_CONTRACT.md` / `docs/STATE_OF_PLAY.md` note grounding is wired
  (dormant until a corpus is ingested).

## Open items / risks

- **Corpus is empty until an ingest run.** Grounding no-ops until a DB exists at `KC_ARIVU_DB`.
  That is expected — this lands the seam ready; a later live ingest lights it up.
- **arivu pinned to `@main`** (no release tag yet). Acceptable for an optional dev extra; pin to
  a tag when arivu cuts one.
- **Retrieval quality** is lexical FTS today; grounding relevance improves when arivu gains
  vector search — the seam is agnostic, no change needed here.
