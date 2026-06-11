# Kathai Chithiram — Scene-Script Contract (v1)

**Status:** Draft v0.1 (2026-06-11)

The scene script is the stable contract between **generation** (`wegofwd-llm` turns a parent's story into structure) and **rendering** (a renderer turns structure into video). Renderers may evolve — matplotlib today, Blender tomorrow — but they all consume this contract. Generation never talks to a renderer directly; it only emits a valid scene script.

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

## 5. Reference renderers

| Renderer | Status | Notes |
|---|---|---|
| `generate_animation.py` | v1 | matplotlib + imageio, stick figures, 24 fps |
| `blender_animation.py` | v2 | Blender Grease Pencil + compositor text cards |

Both must consume a v1 script unchanged. New renderers must pass the shared contract test suite (mock scripts → asserts) before use.

## 6. Open items (tracked as tickets)

- [ ] Define the JSON Schema for v1 and validate every script against it.
- [ ] Implement the safety validator (§3) as the gate before rendering.
- [ ] Add a shared renderer conformance test suite with mock scripts.
- [ ] Migrate existing renderers to consume the contract explicitly.
