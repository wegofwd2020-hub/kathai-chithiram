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
