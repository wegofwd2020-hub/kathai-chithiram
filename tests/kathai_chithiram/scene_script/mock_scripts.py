"""Synthetic mock scene scripts for tests.

No real child data appears here (CLAUDE.md / PRIVACY.md). The story is wholly
fictional and the child is referred to only by the placeholder ``child_token``.
Every helper returns a *fresh* deep copy so a test can mutate it freely.
"""

from __future__ import annotations

import copy
from typing import Any


def valid_scene_script() -> dict[str, Any]:
    """Return a fresh, fully valid v1 scene script (a synthetic 2-scene story)."""
    script: dict[str, Any] = {
        "schema_version": "1.0",
        "story_id": "00000000-0000-0000-0000-000000000000",
        "title": "Pip Tries the Slide",
        "child_token": "CHILD",
        "locale": "en-US",
        "total_duration_s": 7,
        "fps": 24,
        "safety": {
            "max_flash_hz": 3,
            "max_scene_cuts_per_min": 20,
            "reviewed_by_human": False,
        },
        "scenes": [
            {
                "index": 1,
                "duration_s": 3,
                "narration": "CHILD walks to the slide.",
                "caption": "CHILD walks to the slide.",
                "setting": "playground",
                "characters": [{"id": "child", "pose": "standing", "expression": "calm"}],
                "props": ["slide"],
                "transition_in": "fade",
                "transition_out": "fade",
                "audio": {"narration_volume": 0.7, "sfx": []},
            },
            {
                "index": 2,
                "duration_s": 4,
                "narration": "CHILD slides down and smiles.",
                "caption": "CHILD slides down and smiles.",
                "setting": "playground",
                "characters": [{"id": "child", "pose": "sitting", "expression": "happy"}],
                "props": ["slide"],
                "transition_in": "fade",
                "transition_out": "fade",
                "audio": {"narration_volume": 0.7, "sfx": []},
            },
        ],
    }
    return copy.deepcopy(script)


def valid_scene_script_v2() -> dict[str, Any]:
    """Return a fresh, fully valid v2 scene script (synthetic, canonical vocab).

    Unlike v1's free-text art fields, v2 constrains ``setting`` / ``props`` /
    ``pose`` / ``expression`` to the closed vocabulary registry, so every value
    here is a registry member (ADR-007 D1/D2).
    """
    script: dict[str, Any] = {
        "schema_version": "2.0",
        "story_id": "00000000-0000-0000-0000-000000000001",
        "title": "CHILD Brushes at the Sink",
        "child_token": "CHILD",
        "locale": "en-US",
        "author": "parent",
        "perspective": "first_person",
        "intent": "instructional",
        "total_duration_s": 7,
        "fps": 24,
        "safety": {
            "max_flash_hz": 3,
            "max_scene_cuts_per_min": 20,
            "reviewed_by_human": False,
        },
        "scenes": [
            {
                "index": 1,
                "duration_s": 3,
                "narration": "CHILD picks up the toothbrush.",
                "caption": "CHILD picks up the toothbrush.",
                "setting": "bathroom",
                "characters": [{"id": "child", "pose": "rest", "expression": "calm"}],
                "props": ["toothbrush", "toothpaste"],
                "transition_in": "fade",
                "transition_out": "fade",
                "audio": {"narration_volume": 0.7, "sfx": []},
            },
            {
                "index": 2,
                "duration_s": 4,
                "narration": "CHILD waves and smiles.",
                "caption": "CHILD waves and smiles.",
                "setting": "calm",
                "characters": [{"id": "child", "pose": "wave", "expression": "smile"}],
                "props": [],
                "transition_in": "fade",
                "transition_out": "fade",
                "audio": {"narration_volume": 0.7, "sfx": []},
            },
        ],
    }
    return copy.deepcopy(script)
