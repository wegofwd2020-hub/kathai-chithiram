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
