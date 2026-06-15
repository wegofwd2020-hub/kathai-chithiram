"""Tests for the contract-consumption rendering pipeline."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fake_renderer import FakeRenderer, UnsupportedMajorRenderer, tiny_script

from kathai_chithiram.errors import (
    RenderSafetyError,
    SceneScriptInvalidError,
    UnsupportedSchemaVersionError,
)
from kathai_chithiram.rendering import build_render_plan
from kathai_chithiram.rendering.silas_story import SILAS_SCENE_SCRIPT, silas_mapping

# --- build_render_plan -----------------------------------------------------


def test_build_plan_validates_first() -> None:
    bad = tiny_script()
    bad["scenes"][0]["caption"] = "different from narration"
    with pytest.raises(SceneScriptInvalidError):
        build_render_plan(bad)


def test_build_plan_reinserts_display_name() -> None:
    plan = build_render_plan(SILAS_SCENE_SCRIPT, mapping=silas_mapping())
    assert plan.title == "Silas Shines His Smile"
    assert "CHILD" not in plan.scenes[0].caption
    assert plan.scenes[0].caption.startswith("Silas")


def test_build_plan_keeps_token_without_mapping() -> None:
    plan = build_render_plan(SILAS_SCENE_SCRIPT)
    assert "CHILD" in plan.title


def test_build_plan_frame_counts() -> None:
    plan = build_render_plan(tiny_script(fps=8, duration_s=2))
    assert plan.fps == 8
    assert plan.scenes[0].frame_count == 16
    assert plan.total_frames == 16


# --- SceneScriptRenderer base ----------------------------------------------


def test_render_without_output_passes_guard() -> None:
    result = FakeRenderer().render(tiny_script())
    assert result.output_path is None
    assert result.plan.fps == 8


def test_render_writes_and_promotes_draft(tmp_path: Path) -> None:
    out = tmp_path / "video.mp4"
    renderer = FakeRenderer()
    result = renderer.render(tiny_script(), output_path=str(out))
    assert result.output_path == str(out)
    assert out.exists()
    assert out.read_text(encoding="utf-8") == "draft-bytes"
    assert not (tmp_path / "video.mp4.draft").exists()  # draft promoted, not left


def test_unsafe_render_raises_and_removes_draft(tmp_path: Path) -> None:
    out = tmp_path / "video.mp4"
    # Alternating black/white every frame at 24 fps -> far above the 3 Hz limit.
    flashing = [0.0 if i % 2 else 1.0 for i in range(48)]
    renderer = FakeRenderer(luminances=flashing)
    with pytest.raises(RenderSafetyError):
        renderer.render(tiny_script(fps=24, duration_s=2), output_path=str(out))
    assert not out.exists()
    assert not (tmp_path / "video.mp4.draft").exists()  # unsafe draft cleaned up


def test_unsupported_major_rejected() -> None:
    with pytest.raises(UnsupportedSchemaVersionError) as exc:
        UnsupportedMajorRenderer().render(tiny_script())
    assert exc.value.major == 1
    assert exc.value.supported == [2]


def test_invalid_script_never_reaches_renderer(tmp_path: Path) -> None:
    renderer = FakeRenderer()
    bad = tiny_script()
    del bad["fps"]
    with pytest.raises(SceneScriptInvalidError):
        renderer.render(bad, output_path=str(tmp_path / "x.mp4"))
    assert renderer.render_calls == 0  # validation happened before any drawing
    assert not os.path.exists(tmp_path / "x.mp4")
