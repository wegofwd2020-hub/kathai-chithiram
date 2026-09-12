"""Tests for the scene-script generation prompt.

The prompt is the first enforcement point, so two things must hold: the worked
example it shows the model is itself contract-valid (else we teach the model to
emit invalid output), and the prompt actually carries the safety rules, the
contract, and the child token.
"""

from __future__ import annotations

import copy

from kathai_chithiram.generation.scene_script_prompt import (
    EXAMPLE_SCENE_SCRIPT,
    build_scene_script_system_prefix,
    build_scene_script_system_prompt,
)
from kathai_chithiram.scene_script.validation import validate_scene_script


def test_example_is_contract_valid() -> None:
    # The example shown to the model must pass the same gate the model's output
    # will face — otherwise the prompt demonstrates an invalid target.
    validate_scene_script(copy.deepcopy(EXAMPLE_SCENE_SCRIPT))


def test_prompt_carries_safety_rules_and_contract() -> None:
    prompt = build_scene_script_system_prompt()
    # A content-safety MUST rule is present (it layers on build_generation_system_prompt).
    assert "You MUST" in prompt
    assert "flashing" in prompt
    # The contract is conveyed as a JSON schema with the key envelope fields.
    assert "total_duration_s" in prompt
    assert "child_token" in prompt
    # The cross-field rules a schema cannot express are spelled out.
    assert "caption" in prompt and "narration" in prompt
    # It instructs single-object JSON output.
    assert "JSON object" in prompt


def test_prompt_uses_supplied_child_token() -> None:
    prompt = build_scene_script_system_prompt(child_token="KIDDO")
    assert "KIDDO" in prompt
    assert "Refer to the child only as 'KIDDO'" in prompt


def test_repair_feedback_is_appended_only_when_present() -> None:
    base = build_scene_script_system_prompt()
    assert "previous attempt was rejected" not in base

    repaired = build_scene_script_system_prompt(
        repair_feedback="validation rule 'scene.caption.mismatch' (scene 2) failed",
    )
    assert "previous attempt was rejected" in repaired
    assert "scene.caption.mismatch" in repaired


# --- KC-12: cacheable prefix / volatile suffix split -----------------------


def test_prefix_is_stable_and_excludes_repair_feedback() -> None:
    # The static prefix is byte-identical across attempts (so it can be cached)
    # and never carries the volatile repair feedback.
    prefix = build_scene_script_system_prefix(child_token="CHILD")
    assert prefix == build_scene_script_system_prefix(child_token="CHILD")
    assert "previous attempt was rejected" not in prefix
    # It still carries the static contract material.
    assert "You MUST" in prefix
    assert "total_duration_s" in prefix


def test_full_prompt_is_prefix_plus_repair_suffix() -> None:
    prefix = build_scene_script_system_prefix(child_token="CHILD")
    # First attempt (no feedback) is exactly the prefix — nothing volatile yet.
    assert build_scene_script_system_prompt(child_token="CHILD") == prefix
    # A repair attempt keeps the prefix byte-for-byte and only adds the suffix.
    full = build_scene_script_system_prompt(
        child_token="CHILD",
        repair_feedback="validation rule 'scene.caption.mismatch' (scene 2) failed",
    )
    assert full.startswith(prefix)
    suffix = full[len(prefix) :]
    assert "scene.caption.mismatch" in suffix
    # The changed part a repair re-asks is far smaller than the cached prefix.
    assert len(suffix) < len(prefix)


# --- KC-12: v2 emission ----------------------------------------------------


def test_example_is_v2() -> None:
    assert EXAMPLE_SCENE_SCRIPT["schema_version"] == "2.0"
    assert EXAMPLE_SCENE_SCRIPT["author"] in ("parent", "therapist")
    assert EXAMPLE_SCENE_SCRIPT["perspective"] == "first_person"
    assert EXAMPLE_SCENE_SCRIPT["intent"] == "instructional"


def test_example_uses_closed_vocabulary() -> None:
    from kathai_chithiram.scene_script.vocabulary import (
        Background,
        Expression,
        Gesture,
        Prop,
    )

    settings = {b.value for b in Background}
    props = {p.value for p in Prop}
    poses = {g.value for g in Gesture}
    expressions = {e.value for e in Expression}
    for scene in EXAMPLE_SCENE_SCRIPT["scenes"]:
        assert scene["setting"] in settings
        assert set(scene["props"]) <= props
        for character in scene["characters"]:
            assert character["pose"] in poses
            assert character["expression"] in expressions


def test_prefix_embeds_v2_schema_and_grammar() -> None:
    prefix = build_scene_script_system_prefix(child_token="CHILD")
    # v2 schema id and the story-grammar fields are present.
    assert "scene-script/v2.json" in prefix
    assert "author" in prefix and "perspective" in prefix and "intent" in prefix
    # It steers the model to the instructional, first-person track.
    assert "instructional" in prefix
    assert "first_person" in prefix


# --- KC-21: optional grounding block ---------------------------------------


def test_empty_grounding_block_is_byte_identical() -> None:
    base = build_scene_script_system_prefix(child_token="CHILD")
    with_empty = build_scene_script_system_prefix(child_token="CHILD", grounding_block="")
    assert with_empty == base


def test_grounding_block_is_inserted_when_present() -> None:
    block = "REFERENCE PRACTICE (cited; for grounding only)\n- [cdc:oral-1] warm up gradually"
    prefix = build_scene_script_system_prefix(child_token="CHILD", grounding_block=block)
    assert "cdc:oral-1" in prefix
    assert "REFERENCE PRACTICE" in prefix
    # the safety rules and the contract are still present
    assert "You MUST" in prefix
    assert "total_duration_s" in prefix
