"""Tests for the guided story template and its lowering to a scene script."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kathai_chithiram.authoring import (
    StoryStep,
    StoryTemplate,
    load_template,
    template_from_mapping,
    template_to_scene_script,
)
from kathai_chithiram.authoring import template as template_mod
from kathai_chithiram.errors import IdentifierLeakError
from kathai_chithiram.privacy.pseudonymize import NameMapping
from kathai_chithiram.scene_script.schema import MAX_CAPTION_CHARS
from kathai_chithiram.scene_script.validation import validate_scene_script


def _mapping() -> NameMapping:
    return NameMapping.for_child("Silas")


def _template() -> StoryTemplate:
    return StoryTemplate(
        title="Silas Brushes His Teeth",
        steps=(
            StoryStep(text="Silas stands at the sink and takes a slow breath."),
            StoryStep(text="He picks up his toothbrush.", props=("toothbrush",)),
            StoryStep(text="He smiles proudly at the mirror.", expression="happy"),
        ),
    )


# ── model validation ────────────────────────────────────────────────────────────
def test_step_rejects_blank_text():
    with pytest.raises(ValueError, match="non-empty"):
        StoryStep(text="   ")


def test_step_rejects_overlong_text():
    with pytest.raises(ValueError, match="characters"):
        StoryStep(text="x" * (MAX_CAPTION_CHARS + 1))


def test_template_needs_a_title_and_a_step():
    with pytest.raises(ValueError, match="title"):
        StoryTemplate(title=" ", steps=(StoryStep(text="a step"),))
    with pytest.raises(ValueError, match="at least one step"):
        StoryTemplate(title="t", steps=())


# ── lowering ────────────────────────────────────────────────────────────────────
def test_one_step_becomes_one_scene_and_validates():
    script = template_to_scene_script(_template(), _mapping(), story_id="s1")
    validate_scene_script(script)  # contract-valid
    assert len(script["scenes"]) == 3
    assert script["story_id"] == "s1"


def test_child_name_never_appears_in_the_script():
    script = template_to_scene_script(_template(), _mapping(), story_id="s1")
    assert "Silas" not in str(script)  # title + captions all tokenized
    assert script["child_token"] == "CHILD"
    assert script["scenes"][0]["caption"].startswith("CHILD")


def test_step_overrides_are_applied_and_the_rest_inferred():
    script = template_to_scene_script(_template(), _mapping(), story_id="s1")
    scenes = script["scenes"]
    assert scenes[0]["setting"] == "a bathroom"  # inferred from "sink"
    assert scenes[1]["props"] == ["toothbrush"]  # explicit override
    assert scenes[2]["characters"][0]["expression"] == "happy"  # explicit override


def test_leak_is_a_hard_stop(monkeypatch):
    # If pseudonymization were bypassed, a surviving identifier must stop lowering.
    monkeypatch.setattr(template_mod, "pseudonymize", lambda text, mapping: text)
    with pytest.raises(IdentifierLeakError):
        template_to_scene_script(_template(), _mapping(), story_id="s1")


# ── parsing ─────────────────────────────────────────────────────────────────────
def test_template_from_mapping_parses_steps_and_options():
    data = {
        "title": "A calm day",
        "fps": 12,
        "steps": [
            {"text": "CHILD plays."},
            {"text": "CHILD rests.", "setting": "a bedroom", "props": ["teddy"]},
        ],
    }
    template = template_from_mapping(data)
    assert template.fps == 12
    assert len(template.steps) == 2
    assert template.steps[1].setting == "a bedroom"
    assert template.steps[1].props == ("teddy",)


def test_missing_title_is_rejected():
    with pytest.raises(ValueError, match="title"):
        template_from_mapping({"steps": [{"text": "a"}]})


def test_unknown_step_field_is_rejected():
    with pytest.raises(ValueError, match="unknown field"):
        template_from_mapping({"title": "t", "steps": [{"text": "a", "colour": "blue"}]})


def test_load_template_reads_a_file(tmp_path: Path):
    path = tmp_path / "t.json"
    path.write_text(
        json.dumps({"title": "t", "steps": [{"text": "CHILD waves."}]}), encoding="utf-8"
    )
    template = load_template(path)
    assert template.title == "t"


def test_invalid_json_is_rejected(tmp_path: Path):
    path = tmp_path / "t.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_template(path)


# ── shipped examples ─────────────────────────────────────────────────────────────
def test_shipped_example_templates_lower_to_valid_scripts():
    # Guard: every example in docs/examples/ must load, lower, validate, and not leak.
    examples = Path(__file__).resolve().parents[3] / "docs" / "examples"
    files = sorted(examples.glob("*.json"))
    assert files, "no example templates found"
    alex = NameMapping.for_child("Alex")  # the examples' sample name
    for path in files:
        script = template_to_scene_script(load_template(path), alex, story_id="ex")
        validate_scene_script(script)
        assert "Alex" not in json.dumps(script)  # the sample name is stripped to the token
