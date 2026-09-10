"""Tests for the KC-3 scene-script validation safety gate.

Covers the happy path, each structural rule, each cross-field safety rule, and
— critically — that a rejection never leaks raw story text into the error or
the logs (PRIVACY.md §6, CONTENT_SAFETY.md §5).
"""

from __future__ import annotations

import logging

import pytest
from mock_scripts import valid_scene_script, valid_scene_script_v2

from kathai_chithiram.errors import SceneScriptInvalidError
from kathai_chithiram.scene_script import validate_scene_script

# A sentinel that stands in for raw story text / a child's real name. If it ever
# appears in an exception message or a log record, privacy has been violated.
SECRET = "ZZ_REAL_CHILD_NAME_LEAK_SENTINEL"


def test_valid_script_passes() -> None:
    # Returns None and does not raise.
    assert validate_scene_script(valid_scene_script()) is None


def test_non_object_rejected() -> None:
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(["not", "an", "object"])  # type: ignore[arg-type]
    assert exc.value.rule == "schema.type"


# --- schema_version gating -------------------------------------------------


def test_unsupported_major_rejected() -> None:
    script = valid_scene_script()
    script["schema_version"] = "3.0"  # 1 and 2 are supported; 3 is not
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "schema_version.unsupported_major"


def test_malformed_version_rejected() -> None:
    script = valid_scene_script()
    script["schema_version"] = "v1"
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "schema_version.malformed"


# --- structural (JSON Schema) rules ---------------------------------------


def test_missing_required_field_rejected() -> None:
    script = valid_scene_script()
    del script["fps"]
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "schema.required"


def test_unexpected_field_rejected() -> None:
    script = valid_scene_script()
    script["surprise"] = "nope"
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "schema.additionalProperties"


def test_fps_out_of_range_rejected() -> None:
    script = valid_scene_script()
    script["fps"] = 60
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "schema.maximum"
    assert exc.value.field == "fps"


@pytest.mark.parametrize("bad_duration", [1, 9])
def test_scene_duration_out_of_range_rejected(bad_duration: int) -> None:
    script = valid_scene_script()
    script["scenes"][0]["duration_s"] = bad_duration
    # Fix the total so we isolate the per-scene duration rule.
    script["total_duration_s"] = bad_duration + script["scenes"][1]["duration_s"]
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule in {"schema.minimum", "schema.maximum"}
    assert exc.value.scene_index == 1


def test_disallowed_transition_rejected() -> None:
    script = valid_scene_script()
    script["scenes"][0]["transition_in"] = "flash"
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "schema.enum"


def test_flash_hz_above_limit_rejected() -> None:
    script = valid_scene_script()
    script["safety"]["max_flash_hz"] = 5
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "schema.maximum"


def test_lowercase_child_token_rejected() -> None:
    script = valid_scene_script()
    script["child_token"] = "silas"  # a real lowercase name must not be stored
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "schema.pattern"
    assert exc.value.field == "child_token"


# --- cross-field safety rules ---------------------------------------------


def test_caption_narration_mismatch_rejected() -> None:
    script = valid_scene_script()
    script["scenes"][0]["caption"] = "CHILD walks to the swing."
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "scene.caption.mismatch"
    assert exc.value.scene_index == 1


def test_content_flag_fails_whole_script() -> None:
    script = valid_scene_script()
    script["scenes"][1]["content_flags"] = ["frightening_imagery"]
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "scene.content_flags.present"
    assert exc.value.scene_index == 2


def test_total_duration_mismatch_rejected() -> None:
    script = valid_scene_script()
    script["total_duration_s"] = 99
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "total_duration_s.mismatch"


def test_non_sequential_scene_index_rejected() -> None:
    script = valid_scene_script()
    script["scenes"][1]["index"] = 5
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "scene.index.non_sequential"


# --- privacy: rejections must not leak raw story text ----------------------


def test_overlong_caption_does_not_leak_text(caplog: pytest.LogCaptureFixture) -> None:
    script = valid_scene_script()
    leaky = f"{SECRET} " * 40  # > 140 chars, contains the sentinel
    script["scenes"][0]["narration"] = leaky
    script["scenes"][0]["caption"] = leaky

    with caplog.at_level(logging.WARNING):
        with pytest.raises(SceneScriptInvalidError) as exc:
            validate_scene_script(script)

    assert exc.value.rule == "schema.maxLength"
    assert SECRET not in str(exc.value)
    assert SECRET not in caplog.text


def test_child_name_in_token_does_not_leak(caplog: pytest.LogCaptureFixture) -> None:
    script = valid_scene_script()
    script["child_token"] = SECRET.lower()  # fails the uppercase-token pattern

    with caplog.at_level(logging.WARNING):
        with pytest.raises(SceneScriptInvalidError) as exc:
            validate_scene_script(script)

    assert SECRET.lower() not in str(exc.value)
    assert SECRET.lower() not in caplog.text


def test_rejection_is_logged_without_text(caplog: pytest.LogCaptureFixture) -> None:
    script = valid_scene_script()
    script["scenes"][0]["caption"] = f"{SECRET} mismatch"

    with caplog.at_level(logging.WARNING):
        with pytest.raises(SceneScriptInvalidError):
            validate_scene_script(script)

    assert "scene-script rejected" in caplog.text
    assert "scene.caption.mismatch" in caplog.text
    assert SECRET not in caplog.text


# --- v2: closed art vocabulary (ADR-007 D1/D2) -----------------------------


def test_v2_canonical_script_passes() -> None:
    # A v2 script whose art fields are all registry members validates.
    assert validate_scene_script(valid_scene_script_v2()) is None


def test_v2_unknown_setting_rejected() -> None:
    script = valid_scene_script_v2()
    script["scenes"][0]["setting"] = "supermarket"  # real, but undrawable today
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "scene.setting.unknown"
    assert exc.value.scene_index == 1


def test_v2_unknown_prop_rejected() -> None:
    script = valid_scene_script_v2()
    script["scenes"][0]["props"] = ["trolley"]
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "scene.props.unknown"
    assert exc.value.scene_index == 1


def test_v2_unknown_pose_rejected() -> None:
    script = valid_scene_script_v2()
    script["scenes"][1]["characters"][0]["pose"] = "cartwheel"
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "scene.character.pose.unknown"
    assert exc.value.scene_index == 2


def test_v2_unknown_expression_rejected() -> None:
    script = valid_scene_script_v2()
    script["scenes"][0]["characters"][0]["expression"] = "furious"
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "scene.character.expression.unknown"
    assert exc.value.scene_index == 1


def test_v2_unknown_value_does_not_leak(caplog: pytest.LogCaptureFixture) -> None:
    script = valid_scene_script_v2()
    script["scenes"][0]["setting"] = SECRET  # an undrawable value must not be logged
    with caplog.at_level(logging.WARNING):
        with pytest.raises(SceneScriptInvalidError) as exc:
            validate_scene_script(script)
    assert exc.value.rule == "scene.setting.unknown"
    assert SECRET not in str(exc.value)
    assert SECRET not in caplog.text


def test_v1_free_text_art_still_allowed() -> None:
    # The v2 vocabulary rules are inapplicable to major 1: a v1 script may still
    # name an undrawable setting (it degrades at render time, as before).
    script = valid_scene_script()
    script["scenes"][0]["setting"] = "supermarket"
    assert validate_scene_script(script) is None


# --- v2: story grammar (ADR-001 author / perspective / intent) --------------


def test_v2_experiential_intent_gated() -> None:
    script = valid_scene_script_v2()
    script["intent"] = "experiential"
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "story.intent.gated"
    assert exc.value.field == "intent"


def test_v2_instructional_requires_first_person() -> None:
    script = valid_scene_script_v2()
    script["perspective"] = "third_person"  # instructional must be first-person
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "story.instructional.requires_first_person"
    assert exc.value.field == "perspective"


def test_v2_child_author_rejected() -> None:
    # ADR-001 D3 defers child authorship entirely; the enum omits it.
    script = valid_scene_script_v2()
    script["author"] = "child"
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "schema.enum"
    assert exc.value.field == "author"


def test_v2_missing_intent_rejected() -> None:
    script = valid_scene_script_v2()
    del script["intent"]
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "schema.required"


def test_v1_has_no_story_grammar_fields() -> None:
    # The grammar attributes are v2-only; a v1 script must not carry them.
    script = valid_scene_script()
    script["intent"] = "instructional"
    with pytest.raises(SceneScriptInvalidError) as exc:
        validate_scene_script(script)
    assert exc.value.rule == "schema.additionalProperties"
