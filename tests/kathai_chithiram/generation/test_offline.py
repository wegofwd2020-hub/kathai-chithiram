"""Tests for the offline (no-LLM) deterministic scene-script generator."""

from __future__ import annotations

import pytest

from kathai_chithiram.errors import IdentifierLeakError, SceneScriptInvalidError
from kathai_chithiram.generation import offline
from kathai_chithiram.generation.offline import build_offline_scene_script
from kathai_chithiram.privacy.pseudonymize import NameMapping
from kathai_chithiram.scene_script.schema import MAX_CAPTION_CHARS
from kathai_chithiram.scene_script.validation import validate_scene_script

_STORY = "Silas woke up calm. He brushed his teeth. Then Silas smiled!"


def _mapping() -> NameMapping:
    return NameMapping.for_child("Silas")


# ── happy path ──────────────────────────────────────────────────────────────────
def test_builds_a_contract_valid_script():
    script = build_offline_scene_script(story_text=_STORY, mapping=_mapping(), story_id="s1")
    validate_scene_script(script)  # does not raise
    assert script["story_id"] == "s1"
    assert script["child_token"] == "CHILD"
    assert len(script["scenes"]) >= 1
    for scene in script["scenes"]:
        assert scene["caption"] == scene["narration"]  # contract requires a verbatim match


def test_short_sentences_are_grouped_into_readable_scenes():
    # Three short sentences group into fewer, longer captions (no tiny fragments).
    script = build_offline_scene_script(story_text=_STORY, mapping=_mapping(), story_id="s1")
    captions = [scene["caption"] for scene in script["scenes"]]
    assert captions == ["CHILD woke up calm. He brushed his teeth.", "Then CHILD smiled!"]


def test_scene_setting_is_inferred_from_content():
    # Each sentence is long enough to be its own scene, so the settings stay distinct.
    script = build_offline_scene_script(
        story_text=(
            "He splashed happily in the warm bubbly bathtub this morning. "
            "Later she ran around the big green park with all her friends."
        ),
        mapping=_mapping(),
        story_id="s1",
    )
    settings = [scene["setting"] for scene in script["scenes"]]
    assert settings == ["a bathroom", "outdoors"]


def test_duration_scales_with_caption_length_within_the_band():
    script = build_offline_scene_script(
        story_text=(
            "She quietly walked across the whole wide sunny room to the far window. Hi!"
        ),
        mapping=_mapping(),
        story_id="s1",
    )
    for scene in script["scenes"]:
        assert 2 <= scene["duration_s"] <= 8
    # The longer caption runs longer than a two-word one.
    longest = max(script["scenes"], key=lambda s: len(s["caption"]))
    shortest = min(script["scenes"], key=lambda s: len(s["caption"]))
    assert longest["duration_s"] >= shortest["duration_s"]


def test_fixed_duration_override_still_applies():
    script = build_offline_scene_script(
        story_text=_STORY, mapping=_mapping(), story_id="s1", scene_duration_s=5
    )
    assert all(scene["duration_s"] == 5 for scene in script["scenes"])
    assert script["total_duration_s"] == 5 * len(script["scenes"])


def test_total_duration_matches_scene_sum():
    script = build_offline_scene_script(story_text=_STORY, mapping=_mapping(), story_id="s1")
    assert script["total_duration_s"] == sum(s["duration_s"] for s in script["scenes"])


# ── prop inference ──────────────────────────────────────────────────────────────
def test_props_inferred_from_caption():
    script = build_offline_scene_script(
        story_text="She kicked the ball outside. He read his book quietly at the table nearby.",
        mapping=_mapping(),
        story_id="s1",
    )
    all_props = [prop for scene in script["scenes"] for prop in scene["props"]]
    assert "ball" in all_props
    assert "book" in all_props


def test_no_props_when_no_keywords_and_cap_respected():
    script = build_offline_scene_script(
        story_text="She stood quietly and looked around the room for a while.",
        mapping=_mapping(),
        story_id="s1",
    )
    for scene in script["scenes"]:
        assert scene["props"] == []
        assert len(scene["props"]) <= 2


# ── name safety (KC-2) ──────────────────────────────────────────────────────────
def test_child_name_never_appears_in_the_script():
    script = build_offline_scene_script(story_text=_STORY, mapping=_mapping(), story_id="s1")
    assert "Silas" not in str(script)  # only the token is stored, never the name


def test_leak_is_a_hard_stop(monkeypatch):
    # If pseudonymization were bypassed, a surviving identifier must stop generation.
    monkeypatch.setattr(offline, "pseudonymize", lambda text, mapping: text)
    with pytest.raises(IdentifierLeakError):
        build_offline_scene_script(story_text=_STORY, mapping=_mapping(), story_id="s1")


# ── segmentation edges ──────────────────────────────────────────────────────────
def test_long_sentence_is_chunked_under_the_caption_limit():
    long_story = "word " * 60 + "."  # ~300 chars, one sentence
    script = build_offline_scene_script(
        story_text=long_story, mapping=_mapping(), story_id="s1"
    )
    assert len(script["scenes"]) > 1  # split into multiple captions
    assert all(len(scene["caption"]) <= MAX_CAPTION_CHARS for scene in script["scenes"])


def test_scene_count_is_capped():
    many = " ".join(f"Sentence number {i}." for i in range(100))
    script = build_offline_scene_script(
        story_text=many, mapping=_mapping(), story_id="s1", max_scenes=5
    )
    assert len(script["scenes"]) == 5


def test_empty_story_rejected():
    with pytest.raises(ValueError, match="no usable text"):
        build_offline_scene_script(story_text="   \n  ", mapping=_mapping(), story_id="s1")


def test_max_scenes_must_be_positive():
    with pytest.raises(ValueError, match="max_scenes"):
        build_offline_scene_script(
            story_text=_STORY, mapping=_mapping(), story_id="s1", max_scenes=0
        )


# ── the produced script survives its own validation gate ────────────────────────
def test_generated_script_would_not_be_rejected_by_the_renderer_gate():
    # A long, punctuation-light story still yields a valid, renderable script.
    script = build_offline_scene_script(
        story_text="the child plays quietly and feels calm and safe and warm today",
        mapping=_mapping(),
        story_id="s1",
    )
    try:
        validate_scene_script(script)
    except SceneScriptInvalidError as exc:  # pragma: no cover - guard for a real regression
        pytest.fail(f"offline script failed validation: {exc}")
