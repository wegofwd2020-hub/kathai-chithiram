# Kathai Chithiram — Scene-Script Contract

**Status:** Draft v0.2 (2026-09-10) — v1 (§2–4) and v2 (§5) both supported

§2–4 describe **v1** (the original free-text contract); **§5** describes **v2**, which closes the art vocabulary and adds the story grammar. The validator supports both.

The scene script is the stable contract between **generation** (`wegofwd-llm` turns a parent's story into structure) and **rendering** (a renderer turns structure into video). Renderers may evolve — matplotlib today, Blender tomorrow — but they all consume this contract. Generation never talks to a renderer directly; it only emits a valid scene script. Generation optionally grounds the scene script in cited corpus passages (KC-21) when `KC_ARIVU_DB` points at a `wegofwd-arivu` corpus; grounding is additive and never bypasses validation or the human-review gate.

```
parent story ──▶ generation ──▶ [ SCENE SCRIPT ] ──▶ renderer ──▶ animation
                                  (this contract)
```

---

## 1. Why a contract

- **Renderer independence.** Swap or add renderers without touching generation.
- **Safety enforcement point.** A script is validated against `CONTENT_SAFETY.md` rules *before* any pixels are rendered.
- **Testability.** Generation can be tested by asserting on script structure; renderers by feeding known scripts (mock data).

## 2. Format

A scene script is a single JSON document. `schema_version` is mandatory and gates compatibility.

```json
{
  "schema_version": "1.0",
  "story_id": "uuid",
  "title": "Silas Shines His Smile",
  "child_token": "CHILD",            // placeholder; real name reinserted at render only
  "locale": "en-US",
  "total_duration_s": 44,
  "fps": 24,
  "safety": {
    "max_flash_hz": 3,
    "max_scene_cuts_per_min": 20,
    "reviewed_by_human": false
  },
  "scenes": [
    {
      "index": 1,
      "duration_s": 4,
      "narration": "Silas walks to the bathroom sink.",
      "caption": "Silas walks to the bathroom sink.",
      "setting": "bathroom",
      "characters": [{ "id": "child", "pose": "standing", "expression": "calm" }],
      "props": ["sink", "toothbrush"],
      "transition_in": "fade",
      "transition_out": "fade",
      "audio": { "narration_volume": 0.7, "sfx": [] }
    }
  ]
}
```

## 3. Field rules (validation)

| Field | Rule |
|---|---|
| `schema_version` | Required; renderer must reject unknown major versions. |
| `child_token` | A placeholder only. Real name is **never** stored in the script; reinserted at render time from session memory (see `PRIVACY.md` §6). |
| `fps` | 8–30. |
| `scenes[].duration_s` | 2–8 s per scene (predictable pacing). |
| `scenes[].narration` / `caption` | Caption must match narration; both ≤ 140 chars; plain language. |
| `transition_in/out` | One of `cut`(discouraged), `fade`, `dissolve`. No flash transitions. |
| `safety.max_flash_hz` | ≤ 3. Renderer enforces. |
| `characters[].id` | Stable across scenes (visual consistency). |
| Banned content | Any scene flagged by the content-safety check fails the whole script. |

A script that violates any rule is **rejected, not rendered**, and the failure is logged without raw story text.

## 4. Versioning

- `schema_version` is `MAJOR.MINOR`. Additive, backward-compatible fields bump MINOR; breaking changes bump MAJOR and require updating every renderer in the same change.
- Renderers declare the MAJOR versions they support.
- **Supported majors today: `{1, 2}`.** The validator selects the schema by major, so v1 and v2 scripts coexist. v1 is described above; v2 is §5. Generation now emits v2.

Generation constrains its output to the v2 JSON schema at decode time using the
provider's structured-output mechanism (on the Anthropic path,
`output_config.format` with `type: json_schema`). This makes structural
violations (wrong types, out-of-vocabulary art, missing fields) unrepresentable
on a compliant provider. It is a *partial* constraint — structure only — so the
validator in `scene_script/validation.py` remains the enforcement point for every
numeric, length, pattern, and cross-field rule, and an invalid script is still
rejected, not rendered.

## 5. Scene-script v2 — closed art vocabulary and story grammar

v2 is additive over v1: every v1 rule above still holds. It closes the fields that decide what a child *sees*, and adds the story's voice and purpose (ADR-007). Because the validator picks the schema by major, **v1 scripts are unaffected** — their free-text art fields still validate and still degrade at render time as before.

### 5.1 Closed art vocabulary

In v1, `setting`, `props[]`, `characters[].pose`, and `characters[].expression` are free strings: an unrecognised value passes validation and then **degrades silently** at render time (a "supermarket" becomes a blank calm room, and nothing reports it). In v2 those four fields are **closed enums generated from the vocabulary registry** (`src/kathai_chithiram/scene_script/vocabulary.py`) — the single source of truth for what every renderer can draw:

| Field | Allowed values (v2) |
|---|---|
| `setting` | `bathroom`, `bedroom`, `kitchen`, `classroom`, `outdoors`, `calm` |
| `characters[].pose` | `wave`, `rest` |
| `characters[].expression` | `smile`, `sleepy`, `calm`, `neutral` |
| `props[]` | `toothbrush`, `toothpaste`, `ball`, `book`, `cup`, `block`, `toy`, `plate`, `apple`, `backpack`, `spoon`, `shoe` |
| `audio.sfx[]` | *(still free strings — vocabulary closure deferred to a later ticket)* |

An out-of-vocabulary value is **rejected, not repaired**, under a field-specific rule id — `scene.setting.unknown`, `scene.props.unknown`, `scene.character.pose.unknown`, `scene.character.expression.unknown` — logged the usual safe way (rule id, scene index, field name, **never the value**). The renderer conformance suite asserts every registry member is drawable by every renderer, so "what the model may ask for" and "what the child can see" stay identical by construction; growing the vocabulary means adding art *and* a registry member, with a failing test as the definition of done.

### 5.2 Story grammar (ADR-001)

v2 adds three **required** top-level fields naming the story's author, voice, and purpose:

| Field | Allowed values | Notes |
|---|---|---|
| `author` | `parent`, `therapist` | Child authorship is deferred entirely (ADR-001 D3); the enum omits it rather than accepting-and-refusing it. |
| `perspective` | `first_person`, `second_person`, `third_person` | The instructional track must be `first_person`. |
| `intent` | `instructional`, `experiential` | `experiential` is **gated** — structurally valid but rejected until ADR-001 D4's preconditions are met. |

Two cross-field rules apply (v2 only), enforced in the contract rather than a prompt so they survive a prompt edit, a provider swap, or a fine-tune:

- `intent: "experiential"` → rejected as `story.intent.gated`.
- `intent: "instructional"` with a non-`first_person` `perspective` → rejected as `story.instructional.requires_first_person`.

### 5.3 Example (v2)

```json
{
  "schema_version": "2.0",
  "story_id": "uuid",
  "title": "CHILD Brushes at the Sink",
  "child_token": "CHILD",
  "locale": "en-US",
  "author": "parent",
  "perspective": "first_person",
  "intent": "instructional",
  "total_duration_s": 7,
  "fps": 24,
  "safety": { "max_flash_hz": 3, "max_scene_cuts_per_min": 20, "reviewed_by_human": false },
  "scenes": [
    {
      "index": 1,
      "duration_s": 3,
      "narration": "CHILD picks up the toothbrush.",
      "caption": "CHILD picks up the toothbrush.",
      "setting": "bathroom",
      "characters": [{ "id": "child", "pose": "rest", "expression": "calm" }],
      "props": ["toothbrush", "toothpaste"],
      "transition_in": "fade",
      "transition_out": "fade",
      "audio": { "narration_volume": 0.7, "sfx": [] }
    }
  ]
}
```

See `docs/ADR_007_scene_script_v2_authoring_grammar.md` and ticket KC-13 for the rationale.

## 6. Reference renderers

| Renderer | Status | Notes |
|---|---|---|
| `generate_animation.py` | v1 | matplotlib stick figures; `MatplotlibStickFigureRenderer` |
| `blender_animation.py` | v2 | Blender Grease Pencil; `BlenderGreasePencilRenderer` |

Both subclass `kathai_chithiram.rendering.SceneScriptRenderer`, so they consume a v1 or v2 script through the shared pipeline (validate → reinsert name → version-gate → render → safety-guard → promote); both declare support for majors `{1, 2}`. New renderers must subclass it and pass the shared conformance suite (`tests/kathai_chithiram/rendering/test_conformance.py`) — including the vocabulary axis (§5.1) — before use.

## 7. Open items (tracked as tickets)

- [x] Define the JSON Schema for v1 and validate every script against it. *(KC-3: `src/kathai_chithiram/scene_script/schema.py`)*
- [x] Implement the safety validator (§3) as the gate before rendering. *(KC-3: `validate_scene_script()`)*
- [x] Add a shared renderer conformance test suite with mock scripts. *(`rendering/pipeline.py` + `test_conformance.py`)*
- [x] Migrate existing renderers to consume the contract explicitly. *(`SceneScriptRenderer` base; both reference renderers migrated)*
- [x] Close the art vocabulary and reject undrawable values; add the story grammar. *(KC-13 §5: `scene_script/vocabulary.py`, `SCENE_SCRIPT_SCHEMA_V2`, conformance vocabulary axis)*
- [ ] Close `audio.sfx[]` to a sound-bank vocabulary. *(deferred from KC-13)*
