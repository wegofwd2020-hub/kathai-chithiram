"""Transitions through the real matplotlib renderer: frames actually change.

These import-skip without matplotlib/Pillow. They render frames in-process (no
file, no ffmpeg) and inspect luminance, so a fade genuinely darkens the boundary
and a dissolve genuinely blends toward the neighbouring scene — not just that a
plan was computed.
"""

from __future__ import annotations

import copy

import pytest
from tests.kathai_chithiram.rendering.fake_renderer import tiny_script

from kathai_chithiram.rendering.pipeline import build_render_plan


def _renderer():
    pytest.importorskip("matplotlib")
    pytest.importorskip("PIL")
    from generate_animation import MatplotlibStickFigureRenderer

    return MatplotlibStickFigureRenderer()


def _two_scene_script(*, fps: int = 8, duration_s: int = 2) -> dict:
    """A minimal valid 2-scene script (indices 1-2 map to real scene art)."""
    script = tiny_script(fps=fps, duration_s=duration_s)
    scene2 = copy.deepcopy(script["scenes"][0])
    scene2["index"] = 2
    scene2["narration"] = scene2["caption"] = "CHILD smiles."
    script["scenes"].append(scene2)
    script["total_duration_s"] = duration_s * 2
    return script


def _set_transitions(script: dict, kind: str) -> dict:
    """Set every scene's in/out transition to ``kind`` on a copy of ``script``."""
    script = copy.deepcopy(script)
    for scene in script["scenes"]:
        scene["transition_in"] = kind
        scene["transition_out"] = kind
    return script


def _first_scene_frame(renderer, script: dict):
    """The first frame of scene 1 (index 0 after the 1-second title card)."""
    plan = build_render_plan(script)
    frames = renderer._composited_frames(plan)
    return frames[plan.fps]  # title card is exactly `fps` frames


def test_fade_in_darkens_the_first_scene_frame():
    renderer = _renderer()
    faded = _first_scene_frame(renderer, _set_transitions(tiny_script(fps=8, duration_s=2), "fade"))
    cut = _first_scene_frame(renderer, _set_transitions(tiny_script(fps=8, duration_s=2), "cut"))

    # Same art; the fade blends it toward black, so it is markedly darker.
    assert faded.mean() < cut.mean()
    assert faded.mean() < cut.mean() * 0.6


def test_cut_leaves_the_first_scene_frame_untouched():
    renderer = _renderer()
    cut = _set_transitions(tiny_script(fps=8, duration_s=2), "cut")
    plan = build_render_plan(cut)
    frames = renderer._composited_frames(plan)
    # With a hard cut the composited frame is the raw (content-driven) art, unchanged.
    from generate_animation import scene_from_content

    scene = plan.scenes[0]
    raw = scene_from_content(scene.setting, scene.caption, scene.props, 0)
    assert (frames[plan.fps] == raw).all()


def test_dissolve_blends_toward_the_neighbour_not_black():
    renderer = _renderer()
    # Scene 2's first frame: a dissolve pulls in scene 1's (bright) content, so it
    # is brighter than the same frame under a fade (which pulls in black).
    dissolve = _set_transitions(_two_scene_script(), "dissolve")
    fade = _set_transitions(_two_scene_script(), "fade")
    plan_d = build_render_plan(dissolve)
    plan_f = build_render_plan(fade)
    scene2_start = plan_d.fps + plan_d.scenes[0].frame_count

    frame_d = renderer._composited_frames(plan_d)[scene2_start]
    frame_f = renderer._composited_frames(plan_f)[scene2_start]
    assert frame_d.mean() > frame_f.mean()


def test_faded_render_still_passes_the_safety_guard():
    # A full render (guard runs inside render()); fades/dissolves must not trip the
    # flash / high-contrast seizure guards. No raise = pass. Uses small scripts (a
    # full-length demo render is far slower and adds no guard coverage here).
    renderer = _renderer()
    renderer.render(_set_transitions(tiny_script(fps=8, duration_s=2), "fade"), output_path=None)
    renderer.render(_set_transitions(_two_scene_script(), "dissolve"), output_path=None)
