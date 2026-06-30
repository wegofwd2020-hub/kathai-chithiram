"""Shared renderer conformance suite (SCENE_SCRIPT_CONTRACT §6).

Every renderer that consumes the contract must pass these checks: it subclasses
the shared base, declares the v1 MAJOR, and rejects an invalid script before
drawing anything. The two reference renderers (matplotlib, Blender) are exercised
alongside a fake one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from blender_animation import BlenderGreasePencilRenderer
from fake_renderer import FakeRenderer, tiny_script
from generate_animation import MatplotlibStickFigureRenderer

from kathai_chithiram.errors import SceneScriptInvalidError
from kathai_chithiram.privacy.pseudonymize import NameMapping
from kathai_chithiram.rendering import SceneScriptRenderer

# Every renderer that claims to consume the contract.
ALL_RENDERERS = [
    FakeRenderer(),
    MatplotlibStickFigureRenderer(),
    BlenderGreasePencilRenderer(),
]


@pytest.fixture(params=ALL_RENDERERS, ids=lambda r: r.name)
def renderer(request: pytest.FixtureRequest) -> SceneScriptRenderer:
    return request.param


def test_is_scene_script_renderer(renderer: SceneScriptRenderer) -> None:
    assert isinstance(renderer, SceneScriptRenderer)


def test_declares_v1_support(renderer: SceneScriptRenderer) -> None:
    assert 1 in renderer.supported_majors


def test_rejects_invalid_script_before_drawing(renderer: SceneScriptRenderer) -> None:
    # Caption that doesn't match narration -> contract violation. Must be caught
    # by the shared validation step, before any renderer-specific work or heavy
    # dependency (matplotlib / bpy) is touched.
    bad = tiny_script()
    bad["scenes"][0]["caption"] = "mismatched caption"
    with pytest.raises(SceneScriptInvalidError):
        renderer.render(bad)


# --- renderer-specific -----------------------------------------------------


def test_matplotlib_real_render_passes_guard() -> None:
    # A genuine end-to-end render (no file written, so no ffmpeg needed):
    # validates, reinserts the name, draws frames, and passes the safety guard.
    mapping = NameMapping(identifiers=("Milo",), display_name="Milo")
    result = MatplotlibStickFigureRenderer().render(
        tiny_script(fps=8, duration_s=2), mapping=mapping, output_path=None
    )
    assert result.output_path is None
    # 8 title frames + 16 scene frames (2 s at 8 fps).
    assert len(result.safety_report.luminances) == 24
    assert result.safety_report.narration_volume == 0.0


def test_matplotlib_writes_real_mp4_file(tmp_path: Path) -> None:
    # The file-output path through the pipeline (draft -> guard -> promote). This
    # exercises the real ffmpeg encode, which the guard-only test above skips, so
    # it catches draft-naming regressions that break extension-based container
    # inference.
    pytest.importorskip("imageio")
    pytest.importorskip("imageio_ffmpeg")
    out = tmp_path / "out.mp4"
    result = MatplotlibStickFigureRenderer().render(
        tiny_script(fps=8, duration_s=2),
        mapping=NameMapping(identifiers=("Milo",), display_name="Milo"),
        output_path=str(out),
    )
    assert result.output_path == str(out)
    assert out.exists() and out.stat().st_size > 0
    # The draft must have been promoted, not left behind, under either name.
    assert not (tmp_path / "out.draft.mp4").exists()
    assert not (tmp_path / "out.mp4.draft").exists()


def test_blender_requires_bpy_but_validates_first() -> None:
    renderer = BlenderGreasePencilRenderer()
    # Valid script, but bpy is unavailable here -> a clear, gated error from the
    # drawing step (proves the lazy import path).
    with pytest.raises(RuntimeError, match="Blender"):
        renderer.render(tiny_script(), output_path=None)
