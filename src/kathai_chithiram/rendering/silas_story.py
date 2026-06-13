"""The "Silas Shines His Smile" demo, expressed as a valid scene script.

This is the hand-built reference story from the prototype, now stored as a
contract-conformant scene script (KC-3) with the child referred to by the
``CHILD`` token. A renderer consumes this through the shared pipeline; the real
display name ("Silas") is reinserted at render time via :func:`silas_mapping`.

"Silas" is a fictional sample name, not a real child (CLAUDE.md).
"""

from __future__ import annotations

from typing import Any

from kathai_chithiram.privacy.pseudonymize import NameMapping

__all__ = ["SILAS_DISPLAY_NAME", "SILAS_SCENE_SCRIPT", "silas_mapping"]

#: The display name reinserted into the tokenized script at render time.
SILAS_DISPLAY_NAME = "Silas"

_CAPTIONS = (
    ("bathroom", "CHILD stands at the sink and takes a deep breath to centre himself."),
    ("bathroom", "He uses a full-hand grip to hold the toothbrush securely."),
    ("bathroom", "He rests the brush on the sink and squeezes a pea-sized amount of paste."),
    ("bathroom", "He holds the brush under cool water for three seconds — one, two, three."),
    ("bathroom", "Small circles on the front teeth — he counts slowly to ten."),
    ("bathroom", "Side teeth — left side, count to five. Right side, count to five."),
    ("bathroom", "He tilts the brush vertically for the inside surfaces — up-and-down strokes."),
    ("bathroom", "Back-and-forth on the molars — like a train on a track."),
    ("bathroom", "He rinses the brush, looks in the mirror and sees his bright smile!"),
    ("bedroom", "Teeth clean, mind calm — CHILD feels proud and ready to shine his smile!"),
)

_SCENE_DURATION_S = 4
_FPS = 24


def _scene(index: int, setting: str, text: str) -> dict[str, Any]:
    """Build one contract-conformant scene (caption mirrors narration)."""
    return {
        "index": index,
        "duration_s": _SCENE_DURATION_S,
        "narration": text,
        "caption": text,
        "setting": setting,
        "characters": [{"id": "child", "pose": "standing", "expression": "calm"}],
        "props": ["sink", "toothbrush"],
        "transition_in": "fade",
        "transition_out": "fade",
        "audio": {"narration_volume": 0.7, "sfx": []},
    }


#: The demo story as a validated-on-use v1 scene script.
SILAS_SCENE_SCRIPT: dict[str, Any] = {
    "schema_version": "1.0",
    "story_id": "11111111-1111-1111-1111-111111111111",
    "title": "CHILD Shines His Smile",
    "child_token": "CHILD",
    "locale": "en-US",
    "total_duration_s": _SCENE_DURATION_S * len(_CAPTIONS),
    "fps": _FPS,
    "safety": {
        "max_flash_hz": 3,
        "max_scene_cuts_per_min": 20,
        "reviewed_by_human": False,
    },
    "scenes": [
        _scene(i + 1, setting, text) for i, (setting, text) in enumerate(_CAPTIONS)
    ],
}


def silas_mapping() -> NameMapping:
    """Return the render-time name mapping (token ``CHILD`` -> "Silas")."""
    return NameMapping(identifiers=(SILAS_DISPLAY_NAME,), display_name=SILAS_DISPLAY_NAME)
