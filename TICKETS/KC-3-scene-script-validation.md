# KC-3 — Scene-script schema validation + safety gate before render

**Labels:** P0, safety
**Refs:** docs/SCENE_SCRIPT_CONTRACT.md, docs/CONTENT_SAFETY.md §5

## Acceptance criteria
- A JSON Schema for scene-script v1 exists; every script is validated before rendering.
- Structural safety rules enforced (scene 2–8 s, caption matches narration, allowed transitions, `max_flash_hz ≤ 3`, banned-content flag).
- Invalid scripts are **rejected, not rendered**; failures logged without raw story text.

## Implementation notes
- `validate_scene_script(script) -> None` raising `SceneScriptInvalidError` with the failing rule. Mock valid + invalid scripts in tests.
