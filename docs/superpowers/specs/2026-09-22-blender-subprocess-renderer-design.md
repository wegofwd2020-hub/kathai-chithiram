# Blender Subprocess Renderer — Design Spec

**Date:** 2026-09-22
**Status:** Approved for implementation
**ADR context:** ADR-007 D3 (vocabulary conformance), rendering pipeline (`docs/SCENE_SCRIPT_CONTRACT.md`)

---

## Goal

Wire the existing `BlenderGreasePencilRenderer` (v2, `blender_animation.py`) into the
`kc` CLI via a subprocess adapter so that `kc generate --renderer blender` (and
`kc offline`, `kc author`) produces an H264 MP4 using the locally installed Blender
instead of the matplotlib stick-figure renderer.

---

## Architecture

Three files change. No new Python dependencies.

### 1. `blender_animation.py` (repo root — existing)

Two additions; no existing logic changed.

**a) `BLENDER_DRAWABLE_PROPS` constant**

Extract the drawable-props set to a module-level constant so the subprocess wrapper
can import it without triggering a `bpy` import:

```python
# Derived from _PROP_GP_DRAWERS; used by BlenderSubprocessRenderer so it can
# declare drawable_props() without loading bpy.
BLENDER_DRAWABLE_PROPS: frozenset[Prop] = frozenset(
    p for p in Prop if p.value in _PROP_GP_DRAWERS
)
```

`BlenderGreasePencilRenderer.drawable_props()` is updated to return this constant
instead of recomputing.

**b) CLI arg handler in `main()`**

Blender passes everything after `--` to the Python script via `sys.argv`. Extend
`main()` to detect and handle two forms:

- **No args** (existing): render the bundled Silas demo to `silas_shines_his_smile_v2.mp4`
- **`-- --input <json_path> --output <mp4_path>`**: read scene script from `<json_path>`,
  call `BlenderGreasePencilRenderer().render(script, output_path=<mp4_path>)`, exit 0 on
  success or 1 on any exception (print traceback to stderr).

Argument parsing uses `argparse` on the post-`--` slice of `sys.argv`. The
`--name-mapping <json_path>` flag is optional; when present it is read and passed as the
`mapping` parameter to `render()`.

### 2. `src/kathai_chithiram/rendering/blender_subprocess.py` (new)

`BlenderSubprocessRenderer(SceneScriptRenderer)` — the in-process adapter.

```
name              = "blender-grease-pencil-v2"   # same as the wrapped renderer
supported_majors  = frozenset({1, 2})
```

**`render()` — overrides the base entirely**

```
1. validate_scene_script(script)
       ↓ SceneScriptInvalidError on failure (before any subprocess)
2. _find_blender() → path
       ↓ RendererError if not found
3. _find_script() → path to blender_animation.py
       ↓ RendererError if not found
4. json.dump(script) → NamedTemporaryFile (auto-deleted)
   [optional] json.dump(mapping) → second temp file
5. subprocess.Popen([blender, "--background", "--python", script_path,
                     "--", "--input", tmp_json, "--output", output_path,
                     *(["--name-mapping", tmp_mapping] if mapping)])
       stderr streamed live to sys.stderr (progress visible)
6. wait() → returncode
       0 + output_path exists → RenderResult(output_path=output_path, has_audio=False)
       0 + output_path missing → RendererError("Blender exited 0 but output not found")
       nonzero             → RendererError(last 20 lines of stderr)
```

**`drawable_props()`**

Imports `BLENDER_DRAWABLE_PROPS` from `blender_animation` (module added to `sys.path`
the same way `_load_default_renderer()` does today). Returns it directly.

**`_render()`**

Raises `NotImplementedError("BlenderSubprocessRenderer.render() bypasses _render()")`.
Never called because `render()` is fully overridden.

**`_find_blender()`**

Priority order:
1. `KC_BLENDER_BIN` environment variable
2. `shutil.which("blender")`
3. `RendererError("blender binary not found; set KC_BLENDER_BIN or add blender to PATH")`

**`_find_script()`**

Locates `blender_animation.py` relative to the package root (two `parents` above
`__file__` of `cli.py`). Raises `RendererError` if not found.

**RenderResult fields**

The subprocess runs the full safety guard internally. The parent returns:

```python
RenderResult(
    plan=build_render_plan(script),   # re-built in-process for the result object
    safety_report=_CALM_REPORT,       # structural constant (same as GP renderer)
    output_path=output_path,
    has_audio=False,
)
```

`_CALM_REPORT` mirrors the structural report `BlenderGreasePencilRenderer._render()`
returns (calm by construction, no audio).

### 3. `src/kathai_chithiram/cli.py` (existing)

**Argument addition**

Add `--renderer {matplotlib,blender}` to the argument parsers for `kc generate`,
`kc offline`, and `kc author`. Default: `matplotlib`. Help text notes that `blender`
requires Blender 4+ on PATH or `KC_BLENDER_BIN`.

**`_maybe_render()` dispatch**

```python
if getattr(args, "renderer", "matplotlib") == "blender":
    renderer = _load_blender_renderer()
else:
    renderer = _load_default_renderer()
```

**`_load_blender_renderer()`**

```python
def _load_blender_renderer() -> SceneScriptRenderer:
    from kathai_chithiram.rendering.blender_subprocess import BlenderSubprocessRenderer
    return BlenderSubprocessRenderer()
```

No `sys.path` manipulation needed — `blender_subprocess` is inside the package.

---

## Data flow

```
kc generate --renderer blender [story]
  ↓
_maybe_render(args, script, store)
  ↓
BlenderSubprocessRenderer().render(script, output_path="…/draft.mp4")
  ├─ validate_scene_script(script)              [in-process; fast fail]
  ├─ write /tmp/kc_<uuid>.json
  └─ subprocess:
       blender --background --python blender_animation.py \
               -- --input /tmp/kc_<uuid>.json --output /tmp/kc_<uuid>_out.mp4
         ↓ (inside Blender process)
         BlenderGreasePencilRenderer().render(script, output_path=…)
           ├─ validate_scene_script            [again; defence-in-depth]
           ├─ build GP scene + keyframes
           ├─ bpy.ops.render.render(animation=True)  → draft.mp4
           ├─ guard_render()
           └─ os.replace(draft → output_path)
         exit 0
  ↓
os.replace(tmp_out → requested_output_path)
RenderResult returned to CLI
```

---

## Error handling

| Condition | Behaviour |
|---|---|
| `blender` not found | `RendererError` before any temp file written |
| `blender_animation.py` not found | `RendererError` before subprocess |
| Script invalid | `SceneScriptInvalidError` before subprocess |
| Blender exits nonzero | `RendererError` with last 20 lines of stderr |
| Exit 0 but file missing | `RendererError("Blender exited 0 but output not found")` |
| Keyboard interrupt | `Popen.terminate()` before re-raise; temp files cleaned |

Temp files are always cleaned up via `NamedTemporaryFile(delete=True)` or
`finally` blocks; no partial drafts reach the store.

---

## Tests

**`tests/kathai_chithiram/rendering/test_blender_subprocess.py`** (new, no Blender needed)

All subprocess calls mocked via `unittest.mock.patch("subprocess.Popen")`.

| Test | Asserts |
|---|---|
| `test_correct_command` | blender binary + `--background --python` + `--` args |
| `test_success` | exit 0 + file written → `RenderResult` with correct `output_path` |
| `test_nonzero_exit` | stderr captured → `RendererError` |
| `test_exit_0_file_missing` | `RendererError("output not found")` |
| `test_preval_fires_before_subprocess` | invalid script → `SceneScriptInvalidError`; Popen never called |
| `test_kc_blender_bin_env` | `KC_BLENDER_BIN=/custom/blender` used in command |
| `test_blender_not_on_path` | `shutil.which` returns None, no `KC_BLENDER_BIN` → `RendererError` |

**Integration test** (skipped without Blender on PATH)

```python
@pytest.mark.skipif(shutil.which("blender") is None, reason="blender not on PATH")
def test_blender_renders_silas_demo(tmp_path):
    ...
```

Renders the Silas demo to `tmp_path`; asserts file exists and is non-empty.

**Conformance suite** (`test_conformance.py`)

`BlenderSubprocessRenderer` is NOT added to `ALL_RENDERERS` — the conformance suite
runs in CI without Blender. `drawable_props()` correctness is covered by
`test_blender_subprocess.py` asserting it equals `BLENDER_DRAWABLE_PROPS`.

---

## Ratification condition (ADR-007 D3 alignment)

The `drawable_props()` constant must equal the set derived from `_PROP_GP_DRAWERS` at
all times. A test in `test_blender_subprocess.py` asserts this by importing both and
comparing — so adding a prop to the GP drawer without updating the constant breaks the
build.

---

## Out of scope

- Audio muxing for the Blender path (Blender renders silent MP4; narration/sfx wiring
  is a follow-up once the subprocess path is proven)
- Windows `blender.exe` path discovery (follow-up; Linux path works today)
- Running the Blender renderer from `kc render` (the replay command) — follow-up
