"""Tests for the shared caption→scene lowering used by offline + the template."""

from __future__ import annotations

import pytest

from kathai_chithiram.errors import IdentifierLeakError, SceneScriptInvalidError
from kathai_chithiram.generation.scene_builder import (
    assemble_scene_script,
    build_scene_dict,
    guard_no_identifier,
)
from kathai_chithiram.privacy.pseudonymize import NameMapping


# ── build_scene_dict: inference vs overrides ────────────────────────────────────
def test_infers_setting_props_expression_from_the_caption():
    scene = build_scene_dict(1, "CHILD brushes his teeth at the sink.")
    assert scene["setting"] == "a bathroom"
    assert "toothbrush" in scene["props"]
    assert scene["caption"] == scene["narration"]
    assert 2 <= scene["duration_s"] <= 8


def test_infers_the_classroom_setting():
    from kathai_chithiram.generation.scene_builder import _infer_setting

    assert _infer_setting("CHILD sits at the desk in the classroom.") == "a classroom"
    assert _infer_setting("CHILD walks to school.") == "a classroom"


def test_infers_the_new_props():
    from kathai_chithiram.generation.scene_builder import _infer_props

    assert "apple" in _infer_props("CHILD eats an apple.")
    assert "backpack" in _infer_props("CHILD packs the backpack.")
    assert "spoon" in _infer_props("CHILD holds the spoon.")
    assert "shoes" in _infer_props("CHILD puts on their shoes.")


def test_explicit_overrides_win_over_inference():
    scene = build_scene_dict(
        1,
        "CHILD stands still.",
        setting="outdoors",
        props=["ball"],
        expression="happy",
        pose="waving",
        duration_s=5,
    )
    assert scene["setting"] == "outdoors"
    assert scene["props"] == ["ball"]
    assert scene["characters"][0]["expression"] == "happy"
    assert scene["characters"][0]["pose"] == "waving"
    assert scene["duration_s"] == 5


def test_empty_props_override_means_no_props():
    # An explicit empty list is honored (no props), distinct from None (infer).
    scene = build_scene_dict(1, "CHILD brushes his teeth.", props=[])
    assert scene["props"] == []


# ── assemble + validate ─────────────────────────────────────────────────────────
def test_assemble_produces_a_contract_valid_script():
    scenes = [build_scene_dict(1, "CHILD waves hello."), build_scene_dict(2, "CHILD smiles.")]
    script = assemble_scene_script(scenes=scenes, story_id="s1", title="CHILD's day")
    assert script["story_id"] == "s1"
    assert script["child_token"] == "CHILD"
    assert script["total_duration_s"] == sum(s["duration_s"] for s in script["scenes"])


def test_assemble_rejects_an_invalid_script():
    # caption != narration violates the contract's cross-field rule.
    bad = build_scene_dict(1, "CHILD waves.")
    bad["caption"] = "different"
    with pytest.raises(SceneScriptInvalidError):
        assemble_scene_script(scenes=[bad], story_id="s1", title="t")


# ── the KC-2 leak guard ─────────────────────────────────────────────────────────
def test_guard_passes_tokenized_captions():
    guard_no_identifier(["CHILD brushes his teeth."], NameMapping.for_child("Silas"))


def test_guard_raises_on_a_surviving_identifier():
    with pytest.raises(IdentifierLeakError):
        guard_no_identifier(["Silas brushes his teeth."], NameMapping.for_child("Silas"))
