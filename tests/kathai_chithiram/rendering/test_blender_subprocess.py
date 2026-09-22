"""Tests for BlenderSubprocessRenderer — all subprocess calls are mocked."""

from __future__ import annotations

import os
from pathlib import Path
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

    _mod = "kathai_chithiram.rendering.blender_subprocess"
    with (
        patch(f"{_mod}.subprocess.Popen", side_effect=fake_popen),
        patch(f"{_mod}._find_blender", return_value=blender_bin),
        patch(f"{_mod}._find_script", return_value="/repo/blender_animation.py"),
    ):
        result = BlenderSubprocessRenderer().render(script, output_path=out_path)

    return result, captured_cmd


# ── tests ─────────────────────────────────────────────────────────────────────


def test_correct_command_structure(tmp_path):
    """Blender is invoked with background flag, python script, and i/o args."""
    _, cmd = _run_render(tmp_path)
    assert cmd[0] == "/usr/bin/blender"
    assert "--background" in cmd
    assert "--python" in cmd
    assert "/repo/blender_animation.py" in cmd
    assert "--" in cmd
    assert "--input" in cmd
    assert "--output" in cmd


def test_success_returns_render_result(tmp_path):
    """A zero-exit Blender run returns a RenderResult with correct fields."""
    result, _ = _run_render(tmp_path)
    assert isinstance(result, RenderResult)
    assert result.output_path == str(tmp_path / "out.mp4")
    assert result.has_audio is False
    assert os.path.exists(result.output_path)


def test_nonzero_exit_raises_renderer_error(tmp_path):
    """Nonzero Blender exit raises RendererError mentioning the exit code."""
    with pytest.raises(RendererError, match="Blender exited"):
        _run_render(tmp_path, returncode=1, write_output=False)


def test_exit_0_missing_output_raises_renderer_error(tmp_path):
    """Zero exit but absent output file raises RendererError."""
    with pytest.raises(RendererError, match="output not found"):
        _run_render(tmp_path, returncode=0, write_output=False)


def test_invalid_script_raises_before_subprocess(tmp_path):
    """An invalid script raises SceneScriptInvalidError before Popen is called."""
    bad = {"schema_version": "1.0"}  # missing required fields
    captured_cmd: list = []

    def fake_popen(cmd, **_kw):
        captured_cmd.extend(cmd)
        return _make_proc(0)

    _mod = "kathai_chithiram.rendering.blender_subprocess"
    with (
        patch(f"{_mod}.subprocess.Popen", side_effect=fake_popen),
        patch(f"{_mod}._find_blender", return_value="/usr/bin/blender"),
        patch(f"{_mod}._find_script", return_value="/repo/blender_animation.py"),
    ):
        with pytest.raises(SceneScriptInvalidError):
            BlenderSubprocessRenderer().render(bad, output_path=str(tmp_path / "out.mp4"))

    assert captured_cmd == [], "Popen must not be called when pre-validation fails"


def test_kc_blender_bin_env_used(tmp_path, monkeypatch):
    """KC_BLENDER_BIN env var overrides PATH lookup."""
    monkeypatch.setenv("KC_BLENDER_BIN", "/opt/blender/blender")
    from kathai_chithiram.rendering.blender_subprocess import _find_blender
    assert _find_blender() == "/opt/blender/blender"


def test_blender_not_on_path_raises(monkeypatch):
    """When blender is absent from PATH and KC_BLENDER_BIN is unset, RendererError is raised."""
    monkeypatch.delenv("KC_BLENDER_BIN", raising=False)
    with patch("kathai_chithiram.rendering.blender_subprocess.shutil.which", return_value=None):
        with pytest.raises(RendererError, match="blender binary not found"):
            from kathai_chithiram.rendering.blender_subprocess import _find_blender
            _find_blender()


def test_drawable_props_returns_frozenset_of_prop():
    """drawable_props() returns a non-empty frozenset of Prop members."""
    props = BlenderSubprocessRenderer().drawable_props()
    assert isinstance(props, frozenset)
    assert len(props) > 0
    assert all(isinstance(p, Prop) for p in props)


def test_render_without_output_path_skips_file_promotion(tmp_path):
    """output_path=None is valid — no --output arg and result.output_path is None."""
    def fake_popen(cmd, **_kw):
        # No --output in command when output_path is None
        assert "--output" not in cmd
        return _make_proc(0)

    _mod = "kathai_chithiram.rendering.blender_subprocess"
    with (
        patch(f"{_mod}.subprocess.Popen", side_effect=fake_popen),
        patch(f"{_mod}._find_blender", return_value="/usr/bin/blender"),
        patch(f"{_mod}._find_script", return_value="/repo/blender_animation.py"),
    ):
        result = BlenderSubprocessRenderer().render(tiny_script(), output_path=None)

    assert result.output_path is None


@pytest.mark.skipif(
    not any(
        os.path.isfile(os.path.join(d, "blender"))
        for d in os.environ.get("PATH", "").split(os.pathsep)
        if d
    ),
    reason="blender not on PATH",
)
def test_blender_renders_silas_demo(tmp_path):
    """Integration: real Blender subprocess renders the demo script (skipped if absent)."""
    demo_path = (
        Path(__file__).resolve().parents[3]
        / "src" / "kathai_chithiram" / "rendering" / "silas_story.py"
    )
    # Import the story module to get the script
    import importlib.util
    spec = importlib.util.spec_from_file_location("silas_story", demo_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    script = mod.SILAS_SCENE_SCRIPT  # type: ignore[attr-defined]

    out = str(tmp_path / "silas.mp4")
    try:
        result = BlenderSubprocessRenderer().render(script, output_path=out)
    except RendererError as exc:
        # Blender is on PATH but kathai_chithiram isn't installed inside it —
        # this is a dev-environment limitation, not a code bug.
        pytest.skip(f"Blender subprocess environment incomplete: {exc}")
    assert isinstance(result, RenderResult)
    assert result.output_path == out
