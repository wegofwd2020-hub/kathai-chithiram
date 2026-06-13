"""JSON Schema and constants for scene-script v1.

This is the machine-checkable half of ``docs/SCENE_SCRIPT_CONTRACT.md`` §3.
The schema encodes every rule that can be expressed structurally (types,
enums, numeric ranges, string lengths, required fields). Cross-field rules
that a JSON Schema cannot express on its own (e.g. "caption must match
narration", "no scene may carry a content-safety flag") are enforced in
``validation.py``.

Keep this module free of any raw story content; it describes *shape*, not data.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ALLOWED_TRANSITIONS",
    "MAX_CAPTION_CHARS",
    "MAX_FLASH_HZ",
    "MAX_SCENE_DURATION_S",
    "MIN_SCENE_DURATION_S",
    "SCENE_SCRIPT_SCHEMA_V1",
    "SUPPORTED_MAJOR_VERSION",
]

# --- Contract constants (single source of truth, also reused by tests) ---

#: Major schema version this validator understands. Unknown majors are rejected.
SUPPORTED_MAJOR_VERSION = 1

#: Allowed scene transitions. ``cut`` is discouraged but legal; no flash/strobe.
ALLOWED_TRANSITIONS: tuple[str, ...] = ("cut", "fade", "dissolve")

#: Captions and narration must be short, plain language.
MAX_CAPTION_CHARS = 140

#: Seizure-safety ceiling: no flashing above this rate (Hz).
MAX_FLASH_HZ = 3

#: Predictable pacing: each scene lasts between these bounds (seconds).
MIN_SCENE_DURATION_S = 2
MAX_SCENE_DURATION_S = 8

# --- JSON Schema (Draft 2020-12) ---

SCENE_SCRIPT_SCHEMA_V1: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://kathai-chithiram.wegofwd/scene-script/v1.json",
    "title": "Kathai Chithiram scene script (v1)",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "story_id",
        "title",
        "child_token",
        "locale",
        "total_duration_s",
        "fps",
        "safety",
        "scenes",
    ],
    "properties": {
        "schema_version": {
            "type": "string",
            "pattern": r"^\d+\.\d+$",
            "description": "MAJOR.MINOR; renderer rejects unknown majors.",
        },
        "story_id": {"type": "string", "minLength": 1},
        "title": {"type": "string", "minLength": 1, "maxLength": 200},
        # A placeholder token only — never a real name. Uppercase token shape
        # is a cheap guard that a lowercase real name was not stored here.
        "child_token": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$"},
        "locale": {"type": "string", "pattern": r"^[a-z]{2}(-[A-Z]{2})?$"},
        "total_duration_s": {"type": "number", "exclusiveMinimum": 0},
        "fps": {"type": "integer", "minimum": 8, "maximum": 30},
        "safety": {
            "type": "object",
            "additionalProperties": False,
            "required": ["max_flash_hz", "max_scene_cuts_per_min", "reviewed_by_human"],
            "properties": {
                "max_flash_hz": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "maximum": MAX_FLASH_HZ,
                },
                "max_scene_cuts_per_min": {"type": "integer", "minimum": 0, "maximum": 20},
                "reviewed_by_human": {"type": "boolean"},
            },
        },
        "scenes": {
            "type": "array",
            "minItems": 1,
            "items": {"$ref": "#/$defs/scene"},
        },
    },
    "$defs": {
        "scene": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "index",
                "duration_s",
                "narration",
                "caption",
                "setting",
                "characters",
                "props",
                "transition_in",
                "transition_out",
                "audio",
            ],
            "properties": {
                "index": {"type": "integer", "minimum": 1},
                "duration_s": {
                    "type": "number",
                    "minimum": MIN_SCENE_DURATION_S,
                    "maximum": MAX_SCENE_DURATION_S,
                },
                "narration": {"type": "string", "minLength": 1, "maxLength": MAX_CAPTION_CHARS},
                "caption": {"type": "string", "minLength": 1, "maxLength": MAX_CAPTION_CHARS},
                "setting": {"type": "string", "minLength": 1},
                "characters": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/character"},
                },
                "props": {"type": "array", "items": {"type": "string"}},
                "transition_in": {"type": "string", "enum": list(ALLOWED_TRANSITIONS)},
                "transition_out": {"type": "string", "enum": list(ALLOWED_TRANSITIONS)},
                "audio": {"$ref": "#/$defs/audio"},
                # Optional output of an upstream content-safety check. Any
                # non-empty entry fails the whole script (enforced in code).
                "content_flags": {"type": "array", "items": {"type": "string"}},
            },
        },
        "character": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "pose", "expression"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "pose": {"type": "string", "minLength": 1},
                "expression": {"type": "string", "minLength": 1},
            },
        },
        "audio": {
            "type": "object",
            "additionalProperties": False,
            "required": ["narration_volume", "sfx"],
            "properties": {
                "narration_volume": {"type": "number", "minimum": 0, "maximum": 1},
                "sfx": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}
