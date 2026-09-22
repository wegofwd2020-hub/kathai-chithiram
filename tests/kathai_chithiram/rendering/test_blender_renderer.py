"""Unit tests for the Blender renderer's pure, bpy-free decision logic.

The grease-pencil drawing needs Blender's ``bpy`` and is verified by running the
``blender`` binary; here we cover the parts that decide *what* to draw (demo vs
content-driven dispatch, prop mapping, backdrop coverage), which import and run
without Blender.
"""

from __future__ import annotations

import blender_animation as ba
from tests.kathai_chithiram.rendering.fake_renderer import tiny_script

from kathai_chithiram.rendering.pipeline import build_render_plan
from kathai_chithiram.rendering.scene_art_hints import Background
from kathai_chithiram.rendering.silas_story import SILAS_SCENE_SCRIPT, silas_mapping
from kathai_chithiram.scene_script.vocabulary import Prop


def test_module_imports_without_bpy():
    # bpy is loaded lazily, so the module (and its content-art helpers) import fine.
    assert hasattr(ba, "build_scene_content")
    assert hasattr(ba, "_BACKDROP")
    assert hasattr(ba, "_apply_transitions")  # fade/dissolve overlay is wired


def test_demo_is_detected_by_title():
    demo = build_render_plan(SILAS_SCENE_SCRIPT, mapping=silas_mapping())
    assert ba._is_demo_story(demo)  # keeps its bespoke per-scene builders
    assert not ba._is_demo_story(build_render_plan(tiny_script()))  # → content-driven


def test_every_background_has_a_blender_backdrop():
    # Guard: a new Background enum member must not KeyError in build_scene_content.
    assert set(ba._BACKDROP) == set(Background)


def test_canonical_prop_maps_known_and_skips_unknown():
    assert ba._canonical_prop("a red ball") == "ball"
    assert ba._canonical_prop("her backpack") == "backpack"
    assert ba._canonical_prop("an apple") == "apple"
    assert ba._canonical_prop("a spaceship") is None


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
