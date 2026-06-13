"""Validate a scene script against the v1 contract before any rendering.

This is the safety gate described in ``docs/CONTENT_SAFETY.md`` §5.2 and
``docs/SCENE_SCRIPT_CONTRACT.md`` §3: a script is checked here *before* a
renderer ever sees it. A script that violates any rule is **rejected, not
rendered**, and the rejection is logged without any raw story text.

Two layers run in order:

1. **Structural** — the JSON Schema in :mod:`kathai_chithiram.scene_script.schema`
   (types, enums, numeric ranges, string lengths, required fields).
2. **Cross-field safety** — rules a JSON Schema cannot express on its own:
   caption must match narration, no scene may carry a content-safety flag, and
   the declared total duration must equal the sum of scene durations.

All failures surface as :class:`SceneScriptInvalidError`, whose message is safe
to log (no captions, narration, or names — only rule ids, lengths, and counts).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError, best_match

from kathai_chithiram.errors import SceneScriptInvalidError
from kathai_chithiram.scene_script.schema import (
    SCENE_SCRIPT_SCHEMA_V1,
    SUPPORTED_MAJOR_VERSION,
)

__all__ = ["validate_scene_script"]

logger = logging.getLogger(__name__)

# Compiled once at import; reused for every validation call.
_SCHEMA_VALIDATOR = Draft202012Validator(SCENE_SCRIPT_SCHEMA_V1)


def validate_scene_script(script: Mapping[str, Any]) -> None:
    """Validate a scene script; return ``None`` if it is safe to render.

    Args:
        script: The decoded scene-script document (e.g. from ``json.loads``).
            Treated as read-only.

    Returns:
        None. The function's contract is "raises iff invalid".

    Raises:
        SceneScriptInvalidError: If the script violates the contract or a
            content-safety rule. The error's ``rule`` attribute identifies the
            specific failure, and its message contains no raw story text.
    """
    if not isinstance(script, Mapping):
        _reject(
            "schema.type",
            f"top-level scene script must be a JSON object, got {type(script).__name__}",
        )

    _check_supported_version(script)
    _check_structure(script)
    _check_cross_field_safety(script)


def _check_supported_version(script: Mapping[str, Any]) -> None:
    """Reject schema versions whose MAJOR this validator does not understand."""
    raw_version = script.get("schema_version")
    if not isinstance(raw_version, str) or "." not in raw_version:
        _reject(
            "schema_version.malformed",
            "schema_version must be a 'MAJOR.MINOR' string",
            field="schema_version",
        )
        return  # unreachable; aids type-narrowing for static checkers

    major_text = raw_version.split(".", 1)[0]
    try:
        major = int(major_text)
    except ValueError:
        _reject(
            "schema_version.malformed",
            "schema_version MAJOR component is not an integer",
            field="schema_version",
        )
        return  # unreachable

    if major != SUPPORTED_MAJOR_VERSION:
        _reject(
            "schema_version.unsupported_major",
            f"unsupported schema MAJOR {major}; this renderer supports {SUPPORTED_MAJOR_VERSION}",
            field="schema_version",
        )


def _check_structure(script: Mapping[str, Any]) -> None:
    """Run the JSON Schema layer, sanitizing any error before it escapes.

    ``jsonschema`` error messages embed the offending instance value, which for
    a scene script is exactly the raw caption/narration/name we must never log.
    We therefore reconstruct a message from the *schema-side* constraint only
    (the keyword and its limit) plus the structural path — never the instance.
    """
    error = best_match(_SCHEMA_VALIDATOR.iter_errors(dict(script)))
    if error is None:
        return

    scene_index, field = _locate(error)
    constraint = _safe_constraint(error)
    _reject(
        f"schema.{error.validator}",
        f"structural rule '{error.validator}' failed at {_path_str(error)}{constraint}",
        scene_index=scene_index,
        field=field,
    )


def _check_cross_field_safety(script: Mapping[str, Any]) -> None:
    """Enforce safety rules that span multiple fields.

    Structure is already valid here, so fields exist with the right types.
    """
    scenes = script["scenes"]
    duration_sum = 0.0

    for position, scene in enumerate(scenes):
        scene_index = scene["index"]
        duration_sum += scene["duration_s"]

        flags = scene.get("content_flags") or []
        if flags:
            _reject(
                "scene.content_flags.present",
                f"scene carries {len(flags)} content-safety flag(s); whole script rejected",
                scene_index=scene_index,
                field="content_flags",
            )

        if scene["caption"] != scene["narration"]:
            _reject(
                "scene.caption.mismatch",
                "caption must match narration verbatim",
                scene_index=scene_index,
                field="caption",
            )

        if scene["index"] != position + 1:
            _reject(
                "scene.index.non_sequential",
                f"scene index {scene['index']} is out of order at position {position + 1}",
                scene_index=scene_index,
                field="index",
            )

    declared_total = script["total_duration_s"]
    if abs(declared_total - duration_sum) > 1e-6:
        _reject(
            "total_duration_s.mismatch",
            f"declared total_duration_s={declared_total} != sum of scene durations={duration_sum}",
            field="total_duration_s",
        )


def _reject(
    rule: str,
    detail: str,
    *,
    scene_index: int | None = None,
    field: str | None = None,
) -> None:
    """Log the rejection (without raw story text) and raise.

    Centralizing this guarantees every rejection is logged consistently and
    that only safe fields (rule id, scene index, field name) ever reach a log.
    """
    logger.warning(
        "scene-script rejected: rule=%s scene=%s field=%s",
        rule,
        scene_index,
        field,
    )
    raise SceneScriptInvalidError(rule, detail, scene_index=scene_index, field=field)


def _locate(error: ValidationError) -> tuple[int | None, str | None]:
    """Derive a 1-based scene index and field name from an error's path."""
    path = list(error.absolute_path)
    scene_index: int | None = None
    if len(path) >= 2 and path[0] == "scenes" and isinstance(path[1], int):
        # Scene indices in the document are 1-based; the array position is 0-based.
        scene_index = path[1] + 1
    field = next((p for p in reversed(path) if isinstance(p, str)), None)
    return scene_index, field


def _path_str(error: ValidationError) -> str:
    """Render the error's structural path without any instance values."""
    if not error.absolute_path:
        return "<root>"
    parts = []
    for token in error.absolute_path:
        parts.append(f"[{token}]" if isinstance(token, int) else token)
    return ".".join(p for p in parts if not p.startswith("[")) or "<root>"


def _safe_constraint(error: ValidationError) -> str:
    """Describe the violated constraint using schema-side values only.

    ``error.validator_value`` is the schema's own limit (e.g. the 140-char cap,
    the allowed-transition list) — never the offending instance — so it is safe
    to include. ``error.instance`` and ``error.message`` are deliberately unused.
    """
    if error.validator in {"additionalProperties", "type"}:
        # Avoid echoing unexpected property names or instance types verbatim.
        return ""
    return f" (allowed: {error.validator_value!r})"
