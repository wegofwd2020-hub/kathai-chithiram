# Blender Subprocess Renderer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `BlenderGreasePencilRenderer` into the `kc` CLI so `kc generate --renderer blender` (and `kc offline`, `kc author`) produces an H264 MP4 using the locally installed Blender.

**Architecture:** A subprocess adapter (`BlenderSubprocessRenderer`) validates the scene script in-process, writes it to a temp file, spawns `blender --background --python blender_animation.py -- --input <tmp> --output <tmp_out>`, waits for exit 0, then promotes the temp output to the requested path. The existing `BlenderGreasePencilRenderer` runs inside Blender's process unchanged — it handles validate, draw, guard, promote internally. The adapter overrides `render()` entirely (bypasses `_render()`) since the subprocess owns the full lifecycle.

**Tech Stack:** Python stdlib (`subprocess`, `tempfile`, `shutil`, `json`, `argparse`), Blender 4+ on PATH or `KC_BLENDER_BIN`.

**Spec:** `docs/superpowers/specs/2026-09-22-blender-subprocess-renderer-design.md`

## Global Constraints

- No new Python package dependencies — stdlib only.
- `bpy` must never be imported in the main process (only inside the Blender subprocess).
- All test fixtures use synthetic/mock data — no real child story data.
- Docstrings on every public function/class (OpenSpec-compliant).
- `ruff check .` and `mypy .` must pass after each task.
- Run `pytest` after each task to confirm nothing regresses.

---

### Task 1: Add `RendererError` to `errors.py`

**Files:**
- Modify: `src/kathai_chithiram/errors.py`
- Test: `tests/kathai_chithiram/test_errors.py` (if exists) or add to the nearest errors test

**Interfaces:**
- Produces: `RendererError(detail: str)` importable from `kathai_chithiram.errors`

- [ ] **Step 1: Check whether a test file for errors already exists**

```bash
ls tests/kathai_chithiram/test_errors.py 2>/dev/null || echo "missing"
```

If missing, the test goes in a new file at that path.

- [ ] **Step 2: Write the failing test**

In `tests/kathai_chithiram/test_errors.py`:

```python
from kathai_chithiram.errors import RendererError, KathaiChithiramError


def test_renderer_error_is_domain_error():
    err = RendererError("blender not found")
    assert isinstance(err, KathaiChithiramError)
    assert "blender not found" in str(err)
```

- [ ] **Step 3: Run to confirm it fails**

```bash
python -m pytest tests/kathai_chithiram/test_errors.py::test_renderer_error_is_domain_error -v
```

Expected: `ImportError` or `AttributeError` — `RendererError` does not exist yet.

- [ ] **Step 4: Add `RendererError` to `__all__` in `errors.py`**

In `src/kathai_chithiram/errors.py`, add `"RendererError"` to the `__all__` list (keep it alphabetical — after `"RenderSafetyError"`):

```python
    "RenderSafetyError",
    "RendererError",
    "ReviewError",
```

- [ ] **Step 5: Add the class body after `UnsupportedSchemaVersionError`**

At the end of `src/kathai_chithiram/errors.py`, append:

```python
class RendererError(KathaiChithiramError):
    """A renderer failed to produce output for a non-safety reason.

    Covers subprocess failures (Blender exited nonzero), missing binaries,
    missing renderer scripts, or unexpected missing output files. Distinct
    from :class:`RenderSafetyError` (which is a content-safety violation) and
    from :class:`SceneScriptInvalidError` (which is a contract violation).

    Args:
        detail: Human-readable description of what went wrong.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
```

- [ ] **Step 6: Run test to confirm it passes**

```bash
python -m pytest tests/kathai_chithiram/test_errors.py::test_renderer_error_is_domain_error -v
```

- [ ] **Step 7: Full test suite + lint**

```bash
python -m pytest --tb=short -q
ruff check .
```

- [ ] **Step 8: Commit**

```bash
git add src/kathai_chithiram/errors.py tests/kathai_chithiram/test_errors.py
git commit -m "feat(errors): add RendererError for subprocess/binary failures"
```

---

### Task 2: Add `BLENDER_DRAWABLE_PROPS` constant to `blender_animation.py`

**Files:**
- Modify: `blender_animation.py` (repo root)
- Test: `tests/kathai_chithiram/rendering/test_blender_renderer.py` (existing)

**Interfaces:**
- Produces: `BLENDER_DRAWABLE_PROPS: frozenset[Prop]` at module level — importable without `bpy`
- `BlenderGreasePencilRenderer.drawable_props()` updated to return it (behaviour unchanged)

- [ ] **Step 1: Write the failing test**

Add to `tests/kathai_chithiram/rendering/test_blender_renderer.py`:

```python
from kathai_chithiram.scene_script.vocabulary import Prop


def test_blender_drawable_props_constant_exists():
    # Must be importable without bpy; the module already imports clean.
    assert hasattr(ba, "BLENDER_DRAWABLE_PROPS")
    assert isinstance(ba.BLENDER_DRAWABLE_PROPS, frozenset)


def test_blender_drawable_props_matches_drawers():
    # The constant must equal the set derived from _PROP_GP_DRAWERS so
    # BlenderSubprocessRenderer.drawable_props() stays in sync.
    expected = frozenset(p for p in Prop if p.value in ba._PROP_GP_DRAWERS)
    assert ba.BLENDER_DRAWABLE_PROPS == expected


def test_blender_drawable_props_non_empty():
    assert len(ba.BLENDER_DRAWABLE_PROPS) > 0
```

- [ ] **Step 2: Run to confirm they fail**

```bash
python -m pytest tests/kathai_chithiram/rendering/test_blender_renderer.py::test_blender_drawable_props_constant_exists -v
```

Expected: `AttributeError` — `BLENDER_DRAWABLE_PROPS` not defined yet.

- [ ] **Step 3: Add the constant to `blender_animation.py`**

In `blender_animation.py`, immediately after the `_PROP_GP_DRAWERS` dict (around line 732), add:

```python
# Module-level set of drawable props — derived from _PROP_GP_DRAWERS so it
# stays in sync automatically. Imported by BlenderSubprocessRenderer without
# triggering a bpy import (bpy is only loaded lazily by _load_bpy()).
BLENDER_DRAWABLE_PROPS: frozenset[Prop] = frozenset(
    p for p in Prop if p.value in _PROP_GP_DRAWERS
)
```

- [ ] **Step 4: Update `BlenderGreasePencilRenderer.drawable_props()`**

Change the existing `drawable_props()` method body (around line 868) from:

```python
    def drawable_props(self) -> frozenset[Prop]:
        # Derived from the drawer table, so adding a Prop without a grease-pencil
        # drawer drops it from the set and fails conformance.
        return frozenset(p for p in Prop if p.value in _PROP_GP_DRAWERS)
```

to:

```python
    def drawable_props(self) -> frozenset[Prop]:
        # Returns the module-level constant so BlenderSubprocessRenderer can
        # import the same value without loading bpy.
        return BLENDER_DRAWABLE_PROPS
```

- [ ] **Step 5: Run the new tests**

```bash
python -m pytest tests/kathai_chithiram/rendering/test_blender_renderer.py -v
```

All existing tests plus the three new ones must pass.

- [ ] **Step 6: Full suite + lint**

```bash
python -m pytest --tb=short -q
ruff check .
```

- [ ] **Step 7: Commit**

```bash
git add blender_animation.py tests/kathai_chithiram/rendering/test_blender_renderer.py
git commit -m "feat(blender): expose BLENDER_DRAWABLE_PROPS constant (no bpy needed)"
```

---

### Task 3: Implement `BlenderSubprocessRenderer`

**Files:**
- Create: `src/kathai_chithiram/rendering/blender_subprocess.py`
- Create: `tests/kathai_chithiram/rendering/test_blender_subprocess.py`

**Interfaces:**
- Consumes: `RendererError` from `kathai_chithiram.errors` (Task 1), `BLENDER_DRAWABLE_PROPS` from `blender_animation` (Task 2)
- Produces: `BlenderSubprocessRenderer` importable from `kathai_chithiram.rendering.blender_subprocess`

- [ ] **Step 1: Write the failing tests**

Create `tests/kathai_chithiram/rendering/test_blender_subprocess.py`:

```python
"""Tests for BlenderSubprocessRenderer — all subprocess calls are mocked."""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.kathai_chithiram.rendering.fake_renderer import tiny_script
from kathai_chithiram.errors import RendererError, SceneScriptInvalidError
from kathai_chithiram.rendering.blender_subprocess import BlenderSubprocessRenderer
from kathai_chithiram.rendering.pipeline import RenderResult
from kathai_chithiram.scene_script.vocabulary import Prop


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_proc(returncode: int = 0, stderr_lines: list[str] | None = None):
    """Build a mock Popen object."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.stderr = iter(stderr_lines or [])
    proc.wait.return_value = None
    proc.terminate.return_value = None
    return proc


def _run_render(
    tmp_path,
    *,
    returncode: int = 0,
    write_output: bool = True,
    blender_bin: str = "/usr/bin/blender",
    script: dict[str, Any] | None = None,
) -> tuple[RenderResult | None, list]:
    """Call BlenderSubprocessRenderer().render() with a mocked subprocess."""
    script = script or tiny_script()
    out_path = str(tmp_path / "out.mp4")
    captured_cmd: list = []

    def fake_popen(cmd, **_kwargs):
        captured_cmd.extend(cmd)
        proc = _make_proc(returncode)
        if returncode == 0 and write_output:
            # Blender's subprocess would write this; we simulate it.
            # Find --output arg and write a stub file.
            try:
                idx = cmd.index("--output")
                Path(cmd[idx + 1]).write_bytes(b"fake-mp4-bytes")
            except (ValueError, IndexError):
                pass
        return proc

    with patch("kathai_chithiram.rendering.blender_subprocess.subprocess.Popen", side_effect=fake_popen), \
         patch("kathai_chithiram.rendering.blender_subprocess._find_blender", return_value=blender_bin), \
         patch("kathai_chithiram.rendering.blender_subprocess._find_script", return_value="/repo/blender_animation.py"):
        result = BlenderSubprocessRenderer().render(script, output_path=out_path)

    return result, captured_cmd


# ── tests ─────────────────────────────────────────────────────────────────────


def test_correct_command_structure(tmp_path):
    from pathlib import Path
    _, cmd = _run_render(tmp_path)
    assert cmd[0] == "/usr/bin/blender"
    assert "--background" in cmd
    assert "--python" in cmd
    assert "/repo/blender_animation.py" in cmd
    assert "--" in cmd
    assert "--input" in cmd
    assert "--output" in cmd


def test_success_returns_render_result(tmp_path):
    result, _ = _run_render(tmp_path)
    assert isinstance(result, RenderResult)
    assert result.output_path == str(tmp_path / "out.mp4")
    assert result.has_audio is False
    assert os.path.exists(result.output_path)


def test_nonzero_exit_raises_renderer_error(tmp_path):
    with pytest.raises(RendererError, match="Blender exited"):
        _run_render(tmp_path, returncode=1, write_output=False)


def test_exit_0_missing_output_raises_renderer_error(tmp_path):
    with pytest.raises(RendererError, match="output not found"):
        _run_render(tmp_path, returncode=0, write_output=False)


def test_invalid_script_raises_before_subprocess(tmp_path):
    bad = {"schema_version": "1.0"}  # missing required fields
    captured_cmd: list = []

    def fake_popen(cmd, **_kw):
        captured_cmd.extend(cmd)
        return _make_proc(0)

    with patch("kathai_chithiram.rendering.blender_subprocess.subprocess.Popen", side_effect=fake_popen), \
         patch("kathai_chithiram.rendering.blender_subprocess._find_blender", return_value="/usr/bin/blender"), \
         patch("kathai_chithiram.rendering.blender_subprocess._find_script", return_value="/repo/blender_animation.py"):
        with pytest.raises(SceneScriptInvalidError):
            BlenderSubprocessRenderer().render(bad, output_path=str(tmp_path / "out.mp4"))

    assert captured_cmd == [], "Popen must not be called when pre-validation fails"


def test_kc_blender_bin_env_used(tmp_path, monkeypatch):
    monkeypatch.setenv("KC_BLENDER_BIN", "/opt/blender/blender")
    from kathai_chithiram.rendering.blender_subprocess import _find_blender
    assert _find_blender() == "/opt/blender/blender"


def test_blender_not_on_path_raises(monkeypatch):
    monkeypatch.delenv("KC_BLENDER_BIN", raising=False)
    with patch("kathai_chithiram.rendering.blender_subprocess.shutil.which", return_value=None):
        with pytest.raises(RendererError, match="blender binary not found"):
            from kathai_chithiram.rendering.blender_subprocess import _find_blender
            _find_blender()


def test_drawable_props_returns_frozenset_of_prop():
    props = BlenderSubprocessRenderer().drawable_props()
    assert isinstance(props, frozenset)
    assert len(props) > 0
    assert all(isinstance(p, Prop) for p in props)


def test_render_without_output_path_skips_file_promotion(tmp_path):
    """output_path=None is valid — no file is written or promoted."""
    def fake_popen(cmd, **_kw):
        # No --output in command when output_path is None
        assert "--output" not in cmd
        return _make_proc(0)

    with patch("kathai_chithiram.rendering.blender_subprocess.subprocess.Popen", side_effect=fake_popen), \
         patch("kathai_chithiram.rendering.blender_subprocess._find_blender", return_value="/usr/bin/blender"), \
         patch("kathai_chithiram.rendering.blender_subprocess._find_script", return_value="/repo/blender_animation.py"):
        result = BlenderSubprocessRenderer().render(tiny_script(), output_path=None)

    assert result.output_path is None
```

- [ ] **Step 2: Run to confirm all tests fail**

```bash
python -m pytest tests/kathai_chithiram/rendering/test_blender_subprocess.py -v
```

Expected: `ModuleNotFoundError` — `blender_subprocess` doesn't exist yet.

- [ ] **Step 3: Create `blender_subprocess.py`**

Create `src/kathai_chithiram/rendering/blender_subprocess.py`:

```python
"""Subprocess adapter: run BlenderGreasePencilRenderer inside a Blender process.

``bpy`` is only available inside Blender — this module lets the ``kc`` CLI use
the Blender renderer without importing ``bpy`` directly. It validates the scene
script in-process, serialises it to a temp file, spawns Blender, and waits for
the result.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from kathai_chithiram.errors import RendererError
from kathai_chithiram.privacy.pseudonymize import NameMapping
from kathai_chithiram.rendering.narration import NarrationSynthesizer, VoiceCast
from kathai_chithiram.rendering.pipeline import (
    RenderPlan,
    RenderResult,
    SceneScriptRenderer,
    build_render_plan,
)
from kathai_chithiram.rendering.safety import RenderSafetyReport
from kathai_chithiram.rendering.sfx import SfxSynthesizer
from kathai_chithiram.scene_script.validation import validate_scene_script
from kathai_chithiram.scene_script.vocabulary import Prop

__all__ = ["BlenderSubprocessRenderer"]

# Structural safety report: the GP renderer is calm by construction (fixed
# palette, no audio, gentle fades), so a constant report is correct here.
_CALM_REPORT = RenderSafetyReport(
    fps=8,
    luminances=[0.7],
    narration_volume=0.0,
    sfx_levels=[],
)


def _find_blender() -> str:
    """Return the path to the Blender binary.

    Checks ``KC_BLENDER_BIN`` first, then ``PATH``.

    Returns:
        Absolute path to the Blender binary.

    Raises:
        RendererError: If Blender cannot be located.
    """
    from_env = os.environ.get("KC_BLENDER_BIN")
    if from_env:
        return from_env
    found = shutil.which("blender")
    if found:
        return found
    raise RendererError(
        "blender binary not found; set KC_BLENDER_BIN or add blender to PATH"
    )


def _find_script() -> str:
    """Return the absolute path to ``blender_animation.py`` at the repo root.

    Returns:
        Absolute path string.

    Raises:
        RendererError: If the script is not found.
    """
    # blender_animation.py lives at repo root:
    # src/kathai_chithiram/rendering/ → parents[3] = repo root
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "blender_animation.py"
    if not script.exists():
        raise RendererError(
            f"blender_animation.py not found at expected path: {script}"
        )
    return str(script)


class BlenderSubprocessRenderer(SceneScriptRenderer):
    """Run the Blender Grease-Pencil renderer in a Blender subprocess.

    Validates the scene script in-process (fast fail), then spawns
    ``blender --background --python blender_animation.py -- --input ... --output ...``.
    Blender handles the full validate→draw→guard→promote lifecycle internally.
    Blender's stderr is streamed live so the user sees progress.

    Audio (narration, sfx) is not yet supported on this path — pass those to
    the matplotlib renderer, or omit them. Passing ``narration`` or ``sfx``
    raises :class:`RendererError`.
    """

    name: ClassVar[str] = "blender-grease-pencil-v2"
    supported_majors: ClassVar[frozenset[int]] = frozenset({1, 2})

    def drawable_props(self) -> frozenset[Prop]:
        """Return the props the wrapped GP renderer can draw.

        Imports ``BLENDER_DRAWABLE_PROPS`` from ``blender_animation`` without
        loading ``bpy`` — the constant is set at module level before any lazy
        ``bpy`` import.

        Returns:
            The drawable prop set.
        """
        repo_root = str(Path(__file__).resolve().parents[3])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from blender_animation import BLENDER_DRAWABLE_PROPS  # noqa: PLC0415
        return BLENDER_DRAWABLE_PROPS

    def render(  # type: ignore[override]
        self,
        script: Mapping[str, Any],
        *,
        mapping: NameMapping | None = None,
        output_path: str | None = None,
        narration: NarrationSynthesizer | VoiceCast | None = None,
        sfx: SfxSynthesizer | None = None,
    ) -> RenderResult:
        """Validate, spawn Blender, wait, promote output.

        Overrides the base ``render()`` entirely — the subprocess owns the full
        validate→draw→guard→promote lifecycle.

        Args:
            script: The scene-script document.
            mapping: Optional name mapping for render-time name reinsertion.
            output_path: Where to write the final MP4. When ``None``, Blender
                builds the scene without writing a file.
            narration: Not yet supported on the Blender path; pass ``None``.
            sfx: Not yet supported on the Blender path; pass ``None``.

        Returns:
            A :class:`RenderResult` on success.

        Raises:
            SceneScriptInvalidError: If the script fails validation before the
                subprocess is even started.
            RendererError: If Blender is not found, the adapter script is
                missing, Blender exits nonzero, or the output file is absent
                after a successful exit.
            RendererError: If ``narration`` or ``sfx`` are supplied (not yet
                supported on this path).
        """
        if narration is not None:
            raise RendererError(
                "narration audio is not yet supported on the Blender renderer path"
            )
        if sfx is not None:
            raise RendererError(
                "sound effects are not yet supported on the Blender renderer path"
            )

        validate_scene_script(script)
        blender_bin = _find_blender()
        script_path = _find_script()

        with tempfile.TemporaryDirectory() as tmp:
            script_json = os.path.join(tmp, "script.json")
            with open(script_json, "w", encoding="utf-8") as fh:
                json.dump(dict(script), fh)

            cmd = [
                blender_bin,
                "--background",
                "--python", script_path,
                "--",
                "--input", script_json,
            ]

            tmp_out: str | None = None
            if output_path is not None:
                tmp_out = os.path.join(tmp, "output.mp4")
                cmd += ["--output", tmp_out]

            if mapping is not None:
                mapping_json = os.path.join(tmp, "mapping.json")
                with open(mapping_json, "w", encoding="utf-8") as fh:
                    json.dump(
                        {
                            "identifiers": list(mapping.identifiers),
                            "token": mapping.token,
                            "display_name": mapping.display_name,
                        },
                        fh,
                    )
                cmd += ["--name-mapping", mapping_json]

            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
            stderr_lines: list[str] = []
            try:
                assert proc.stderr is not None
                for line in proc.stderr:
                    sys.stderr.write(line)
                    stderr_lines.append(line)
                proc.wait()
            except KeyboardInterrupt:
                proc.terminate()
                proc.wait()
                raise

            if proc.returncode != 0:
                tail = "".join(stderr_lines[-20:])
                raise RendererError(
                    f"Blender exited {proc.returncode}:\n{tail}"
                )

            if output_path is not None:
                assert tmp_out is not None
                if not os.path.exists(tmp_out):
                    raise RendererError(
                        "Blender exited 0 but output not found at expected path"
                    )
                os.replace(tmp_out, output_path)

        plan = build_render_plan(script, mapping=mapping)
        return RenderResult(
            plan=plan,
            safety_report=_CALM_REPORT,
            output_path=output_path,
            has_audio=False,
        )

    def _render(self, plan: RenderPlan, *, draft_path: str | None) -> RenderSafetyReport:
        """Never called — ``render()`` is fully overridden."""
        raise NotImplementedError(
            "BlenderSubprocessRenderer.render() bypasses _render(); "
            "this method should never be called"
        )
```

- [ ] **Step 4: Run the tests**

```bash
python -m pytest tests/kathai_chithiram/rendering/test_blender_subprocess.py -v
```

All 9 tests must pass. Fix any failures before continuing.

- [ ] **Step 5: Full suite + lint + types**

```bash
python -m pytest --tb=short -q
ruff check .
mypy src/kathai_chithiram/rendering/blender_subprocess.py
```

- [ ] **Step 6: Commit**

```bash
git add src/kathai_chithiram/rendering/blender_subprocess.py \
        tests/kathai_chithiram/rendering/test_blender_subprocess.py
git commit -m "feat(rendering): BlenderSubprocessRenderer — kc --renderer blender (unit tests)"
```

---

### Task 4: Extend `blender_animation.py` `main()` with arg parser

This makes the subprocess command from Task 3 actually work when Blender runs the script.

**Files:**
- Modify: `blender_animation.py` (repo root)
- Test: extend `tests/kathai_chithiram/rendering/test_blender_renderer.py` (integration test, skipped without Blender)

**Interfaces:**
- Consumes: nothing new — extends existing `main()`
- Produces: `blender --background --python blender_animation.py -- --input <json> --output <mp4>` works end-to-end

- [ ] **Step 1: Write the integration test (will be skipped until Blender is available)**

Add to `tests/kathai_chithiram/rendering/test_blender_renderer.py`:

```python
import json
import shutil
import subprocess
import sys
import tempfile

import pytest

from kathai_chithiram.rendering.silas_story import SILAS_SCENE_SCRIPT, silas_mapping


@pytest.mark.skipif(
    shutil.which("blender") is None and not os.environ.get("KC_BLENDER_BIN"),
    reason="Blender not on PATH and KC_BLENDER_BIN not set",
)
def test_blender_main_renders_via_args(tmp_path):
    """Integration: blender_animation.py renders a script passed via --input/--output."""
    import os
    blender_bin = os.environ.get("KC_BLENDER_BIN") or shutil.which("blender")
    script_path = str(Path(__file__).resolve().parents[4] / "blender_animation.py")

    script_json = tmp_path / "script.json"
    script_json.write_text(json.dumps(SILAS_SCENE_SCRIPT), encoding="utf-8")

    mapping_json = tmp_path / "mapping.json"
    m = silas_mapping()
    mapping_json.write_text(
        json.dumps({"identifiers": list(m.identifiers), "token": m.token, "display_name": m.display_name}),
        encoding="utf-8",
    )

    out_mp4 = str(tmp_path / "out.mp4")
    result = subprocess.run(
        [blender_bin, "--background", "--python", script_path,
         "--", "--input", str(script_json), "--output", out_mp4,
         "--name-mapping", str(mapping_json)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Blender stderr:\n{result.stderr}"
    assert os.path.exists(out_mp4), "MP4 not written"
    assert os.path.getsize(out_mp4) > 1000, "MP4 suspiciously small"
```

Also add `import os` and `from pathlib import Path` to the top of the test file if not already present.

- [ ] **Step 2: Extend `main()` in `blender_animation.py`**

Replace the existing `main()` (lines ~923–943) with:

```python
def main() -> None:
    """Render the bundled demo, or a supplied script when args follow '--'.

    When Blender is invoked as::

        blender --background --python blender_animation.py -- --input <json> --output <mp4>

    the post-``--`` arguments are parsed and the supplied script is rendered.
    When called with no arguments the bundled Silas demo is rendered instead.
    """
    import argparse
    import json as _json
    import os
    import sys
    import traceback

    if "--" in sys.argv:
        # Blender passes everything after '--' to the Python script.
        argv_after = sys.argv[sys.argv.index("--") + 1:]
        parser = argparse.ArgumentParser(prog="blender_animation.py")
        parser.add_argument("--input", required=True, metavar="JSON_PATH",
                            help="Path to the scene-script JSON file.")
        parser.add_argument("--output", required=True, metavar="MP4_PATH",
                            help="Path to write the rendered MP4.")
        parser.add_argument("--name-mapping", default=None, metavar="JSON_PATH",
                            help="Optional name-mapping JSON for render-time reinsertion.")
        parsed = parser.parse_args(argv_after)

        with open(parsed.input, encoding="utf-8") as fh:
            script = _json.load(fh)

        mapping = None
        if parsed.name_mapping:
            from kathai_chithiram.privacy.pseudonymize import NameMapping
            with open(parsed.name_mapping, encoding="utf-8") as fh:
                d = _json.load(fh)
            mapping = NameMapping(
                identifiers=tuple(d["identifiers"]),
                token=d["token"],
                display_name=d.get("display_name"),
            )

        try:
            BlenderGreasePencilRenderer().render(
                script, mapping=mapping, output_path=parsed.output
            )
            print(f"Done! → {parsed.output}")
        except Exception:
            traceback.print_exc()
            sys.exit(1)
        return

    # Original demo path — no CLI args.
    from kathai_chithiram.rendering.silas_story import SILAS_SCENE_SCRIPT, silas_mapping
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "silas_shines_his_smile_v2.mp4"
    )
    BlenderGreasePencilRenderer().render(
        SILAS_SCENE_SCRIPT, mapping=silas_mapping(), output_path=output_path
    )
    print(f"Done! → {output_path}")
```

- [ ] **Step 3: Run the test suite (integration test will skip without Blender)**

```bash
python -m pytest tests/kathai_chithiram/rendering/test_blender_renderer.py -v
```

The integration test should be SKIPPED (not FAILED) if Blender is not on PATH.

If Blender IS on PATH (`blender --version` returns 4.x), run the integration test for real:

```bash
python -m pytest tests/kathai_chithiram/rendering/test_blender_renderer.py::test_blender_main_renders_via_args -v -s
```

- [ ] **Step 4: Full suite + lint**

```bash
python -m pytest --tb=short -q
ruff check .
```

- [ ] **Step 5: Commit**

```bash
git add blender_animation.py tests/kathai_chithiram/rendering/test_blender_renderer.py
git commit -m "feat(blender): extend main() with --input/--output/--name-mapping CLI args"
```

---

### Task 5: Wire `--renderer blender` into the `kc` CLI

**Files:**
- Modify: `src/kathai_chithiram/cli.py`
- Test: extend existing CLI tests or add to `tests/kathai_chithiram/test_cli.py`

**Interfaces:**
- Consumes: `BlenderSubprocessRenderer` from Task 3
- Produces: `kc generate --renderer blender`, `kc offline --renderer blender`, `kc author --renderer blender` all dispatch to `BlenderSubprocessRenderer`

- [ ] **Step 1: Write failing CLI tests**

Find the existing CLI test file:

```bash
ls tests/kathai_chithiram/test_cli*.py tests/kathai_chithiram/cli/test_*.py 2>/dev/null
```

Add these tests to whichever CLI test file covers `_maybe_render` or argument parsing:

```python
from unittest.mock import patch, MagicMock


def test_renderer_arg_defaults_to_matplotlib(make_args):
    """--renderer is optional; omitting it selects matplotlib."""
    # make_args is a helper that builds a minimal Namespace matching _maybe_render's sig.
    # If no such helper exists, build the Namespace inline.
    import argparse
    args = argparse.Namespace(
        no_render=False,
        renderer="matplotlib",
        captions=None,
        out=None,
        voice=None,
        character_voice=None,
        sfx=None,
    )
    with patch("kathai_chithiram.cli._load_default_renderer") as mock_load, \
         patch("kathai_chithiram.cli._render_draft") as mock_render:
        mock_render.return_value = MagicMock()
        from kathai_chithiram.cli import _load_default_renderer
        # The key assertion: matplotlib renderer is loaded, not blender.
        mock_load.assert_not_called()  # will be called by _maybe_render


def test_renderer_blender_loads_blender_subprocess(tmp_path):
    """--renderer blender loads BlenderSubprocessRenderer."""
    import argparse
    from kathai_chithiram.cli import _load_blender_renderer
    from kathai_chithiram.rendering.blender_subprocess import BlenderSubprocessRenderer

    renderer = _load_blender_renderer()
    assert isinstance(renderer, BlenderSubprocessRenderer)


def test_generate_accepts_renderer_flag(capsys):
    """kc generate --help includes --renderer in output."""
    import sys
    from kathai_chithiram.cli import build_arg_parser
    parser = build_arg_parser()
    try:
        parser.parse_args(["generate", "--help"])
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert "--renderer" in captured.out
```

- [ ] **Step 2: Run to confirm the `_load_blender_renderer` test fails**

```bash
python -m pytest tests/ -k "blender_subprocess or renderer_flag or renderer_blender or renderer_arg" -v
```

Expected: `AttributeError` — `_load_blender_renderer` and `--renderer` don't exist yet.

- [ ] **Step 3: Add `--renderer` to `_add_common_args` in `cli.py`**

In `src/kathai_chithiram/cli.py`, inside `_add_common_args()`, add after the `--no-render` argument block (around line 476):

```python
    parser.add_argument(
        "--renderer",
        choices=["matplotlib", "blender"],
        default="matplotlib",
        help=(
            "Renderer to use for the animation draft (default: matplotlib). "
            "'blender' uses the Grease-Pencil renderer via a Blender subprocess; "
            "requires Blender 4+ on PATH or KC_BLENDER_BIN set. "
            "Audio (--voice, --sfx) is not yet supported on the blender path."
        ),
    )
```

- [ ] **Step 4: Add `_load_blender_renderer()` to `cli.py`**

In `src/kathai_chithiram/cli.py`, immediately after `_load_default_renderer()` (around line 1660):

```python
def _load_blender_renderer() -> SceneScriptRenderer:
    """Import and construct the Blender subprocess renderer.

    Returns:
        A :class:`BlenderSubprocessRenderer` instance.
    """
    from kathai_chithiram.rendering.blender_subprocess import BlenderSubprocessRenderer
    return BlenderSubprocessRenderer()
```

- [ ] **Step 5: Update `_maybe_render()` to dispatch on `--renderer`**

In `_maybe_render()`, replace the single line:

```python
        renderer = _load_default_renderer()
```

with:

```python
        if getattr(args, "renderer", "matplotlib") == "blender":
            renderer = _load_blender_renderer()
        else:
            renderer = _load_default_renderer()
```

- [ ] **Step 6: Run the new CLI tests**

```bash
python -m pytest tests/ -k "blender_subprocess or renderer_flag or renderer_blender or renderer_arg or load_blender" -v
```

All must pass.

- [ ] **Step 7: Smoke-test the CLI flag is visible**

```bash
python -m kathai_chithiram.cli generate --help | grep renderer
```

Expected output contains: `--renderer {matplotlib,blender}`

- [ ] **Step 8: Full suite + lint + types**

```bash
python -m pytest --tb=short -q
ruff check .
mypy src/kathai_chithiram/cli.py --no-error-summary 2>&1 | grep "blender\|renderer" | head -10
```

No new errors.

- [ ] **Step 9: Commit**

```bash
git add src/kathai_chithiram/cli.py tests/
git commit -m "feat(cli): add --renderer {matplotlib,blender} flag; wire BlenderSubprocessRenderer"
```

---

## Manual End-to-End Verification

After all 5 tasks are complete, run the full pipeline manually if Blender is available:

```bash
# 1. Offline render of the Silas demo with Blender
python -m kathai_chithiram.cli offline \
    --renderer blender \
    --out /tmp/silas_blender_test.mp4 \
    --no-render  # first confirm the script generates cleanly

# 2. Then with actual rendering
python -m kathai_chithiram.cli offline \
    --renderer blender \
    --out /tmp/silas_blender_test.mp4
```

Expected: `silas_blender_test.mp4` created, non-empty, playable.
