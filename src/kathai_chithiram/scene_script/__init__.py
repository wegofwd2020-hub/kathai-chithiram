"""The scene script: the stable contract between generation and rendering.

See ``docs/SCENE_SCRIPT_CONTRACT.md``. Generation emits a scene script; a
renderer consumes it. A script is validated against the contract and the
content-safety rules *before* any rendering — invalid scripts are rejected,
not rendered.
"""

from __future__ import annotations

from kathai_chithiram.scene_script.schema import (
    ALLOWED_TRANSITIONS,
    MAX_CAPTION_CHARS,
    MAX_FLASH_HZ,
    SCENE_SCRIPT_SCHEMA_V1,
    SUPPORTED_MAJOR_VERSION,
)
from kathai_chithiram.scene_script.validation import validate_scene_script

__all__ = [
    "ALLOWED_TRANSITIONS",
    "MAX_CAPTION_CHARS",
    "MAX_FLASH_HZ",
    "SCENE_SCRIPT_SCHEMA_V1",
    "SUPPORTED_MAJOR_VERSION",
    "validate_scene_script",
]
