"""Content-driven scene art through the real matplotlib renderer.

Import-skips without matplotlib/Pillow. Confirms arbitrary stories are drawn from
their setting/caption (not the demo's index-keyed frames) and that the demo still
keeps its bespoke art.
"""

from __future__ import annotations

import numpy as np
import pytest

from kathai_chithiram.rendering.pipeline import build_render_plan
from kathai_chithiram.rendering.silas_story import SILAS_SCENE_SCRIPT


def _renderer():
    pytest.importorskip("matplotlib")
    pytest.importorskip("PIL")
    from generate_animation import MatplotlibStickFigureRenderer

    return MatplotlibStickFigureRenderer()


def _scene(index: int, setting: str, text: str) -> dict:
    return {
        "index": index,
        "duration_s": 2,
        "narration": text,
        "caption": text,
        "setting": setting,
        "characters": [{"id": "child", "pose": "standing", "expression": "calm"}],
        "props": [],
        "transition_in": "cut",
        "transition_out": "cut",
        "audio": {"narration_volume": 0.7, "sfx": []},
    }


def _arbitrary_script() -> dict:
    return {
        "schema_version": "1.0",
        "story_id": "arb",
        "title": "A Calm Day",  # not the demo → content-driven art
        "child_token": "CHILD",
        "locale": "en-US",
        "total_duration_s": 4,
        "fps": 8,
        "safety": {"max_flash_hz": 3, "max_scene_cuts_per_min": 20, "reviewed_by_human": False},
        "scenes": [
            _scene(1, "the park", "CHILD played happily in the park."),
            _scene(2, "the bedroom", "CHILD was tired and went to sleep."),
        ],
    }


def _first_frame_of_scene(renderer, script: dict, scene_pos: int):
    plan = build_render_plan(script)
    frames = renderer._composited_frames(plan)
    offset = plan.fps + sum(s.frame_count for s in plan.scenes[:scene_pos])
    return frames[offset]


def test_arbitrary_scenes_are_not_the_demo_frames():
    from generate_animation import SCENE_ART

    renderer = _renderer()
    script = _arbitrary_script()
    park = _first_frame_of_scene(renderer, script, 0)

    plan = build_render_plan(script)
    demo_scene_1 = SCENE_ART[1](0, plan.scenes[0].caption)  # the silas bathroom art
    # An arbitrary park scene must not borrow the demo's index-1 brushing frame.
    assert not np.array_equal(park, demo_scene_1)


def test_different_settings_produce_different_art():
    renderer = _renderer()
    script = _arbitrary_script()
    park = _first_frame_of_scene(renderer, script, 0)
    bedroom = _first_frame_of_scene(renderer, script, 1)
    # A park (sky + grass + sun) and a bedroom (dark window) differ in luminance.
    assert not np.array_equal(park, bedroom)
    assert abs(float(park.mean()) - float(bedroom.mean())) > 1.0


def test_content_art_render_passes_the_safety_guard():
    renderer = _renderer()
    renderer.render(_arbitrary_script(), output_path=None)  # no raise = guards pass


def test_plan_carries_scene_props():
    script = _arbitrary_script()
    script["scenes"][0]["props"] = ["ball", "book"]
    plan = build_render_plan(script)
    assert plan.scenes[0].props == ("ball", "book")


def test_recognized_props_change_the_frame():
    _renderer()  # ensure matplotlib/PIL
    from generate_animation import scene_from_content

    with_props = scene_from_content(
        "a park", "She played.", ("ball", "book"), "standing", "calm", 0
    )
    without = scene_from_content("a park", "She played.", (), "standing", "calm", 0)
    assert not np.array_equal(with_props, without)  # props were drawn


def test_unrecognized_props_are_ignored():
    _renderer()
    from generate_animation import scene_from_content

    unknown = scene_from_content(
        "a park", "She played.", ("spaceship", "dragon"), "standing", "calm", 0
    )
    none = scene_from_content("a park", "She played.", (), "standing", "calm", 0)
    assert np.array_equal(unknown, none)  # nothing recognized → identical frame


def test_character_expression_drives_the_face():
    _renderer()
    from generate_animation import scene_from_content

    caption = "She looked at the window."  # neutral caption; expression must decide
    sleepy = scene_from_content("a room", caption, (), "standing", "sleepy", 0)
    happy = scene_from_content("a room", caption, (), "standing", "happy", 0)
    assert not np.array_equal(sleepy, happy)  # eyes-closed vs smiling


def test_script_expression_overrides_the_caption():
    _renderer()
    from generate_animation import scene_from_content

    # Caption says "smiled", but the script's sleepy expression wins.
    caption = "She smiled a big happy smile."
    honored = scene_from_content("a room", caption, (), "standing", "sleepy", 0)
    as_caption = scene_from_content("a room", caption, (), "standing", "happy", 0)
    assert not np.array_equal(honored, as_caption)


def test_render_with_props_passes_the_safety_guard():
    renderer = _renderer()
    script = _arbitrary_script()
    script["scenes"][0]["props"] = ["ball"]
    script["scenes"][1]["props"] = ["teddy bear", "cup"]
    renderer.render(script, output_path=None)  # no raise = guards pass with props


def test_demo_story_still_uses_its_bespoke_art():
    from generate_animation import SCENE_ART, _is_demo_story

    renderer = _renderer()
    plan = build_render_plan(SILAS_SCENE_SCRIPT)
    assert _is_demo_story(plan)  # the demo is detected by its title
    frame = renderer._scene_frame(plan.scenes[0], 0, demo=True)
    expected = SCENE_ART[1](0, plan.scenes[0].caption)
    assert np.array_equal(frame, expected)
