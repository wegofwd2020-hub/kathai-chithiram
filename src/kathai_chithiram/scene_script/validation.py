"""Validate a scene script against the v1 and v2 contracts before any rendering.

This is the safety gate described in ``docs/CONTENT_SAFETY.md`` §5.2 and
``docs/SCENE_SCRIPT_CONTRACT.md`` §3–5: a script is checked here *before* a
renderer ever sees it. A script that violates any rule is **rejected, not
rendered**, and the rejection is logged without any raw story text.

Three layers run in order:

1. **Structural** — the JSON Schema in :mod:`kathai_chithiram.scene_script.schema`
   (types, enums, numeric ranges, string lengths, required fields).
2. **Cross-field safety** — rules a JSON Schema cannot express on its own:
   caption must match narration, no scene may carry a content-safety flag, and
   the declared total duration must equal the sum of scene durations.
3. **Story grammar (v2 only)** — checks author/perspective/intent semantics, the
   closed art vocabulary, the gated ``experiential`` intent, and the
   instructional-first-person rule (``SCENE_SCRIPT_CONTRACT.md`` §5.2).

All failures surface as :class:`SceneScriptInvalidError`, whose message is safe
to log (no captions, narration, or names — only rule ids, lengths, and counts).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, NoReturn

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError, best_match

from kathai_chithiram.errors import SceneScriptInvalidError
from kathai_chithiram.scene_script.schema import (
    SCENE_SCRIPT_SCHEMAS,
    SUPPORTED_MAJOR_VERSIONS,
)

__all__ = ["validate_scene_script"]

logger = logging.getLogger(__name__)

# One validator per supported major, compiled once at import and reused.
_SCHEMA_VALIDATORS = {
    major: Draft202012Validator(schema) for major, schema in SCENE_SCRIPT_SCHEMAS.items()
}

# When the closed art vocabulary (v2) rejects a value, surface it under a
# field-specific rule id rather than the generic ``schema.enum``, so a caller can
# tell an undrawable setting from an undrawable prop. The offending value is
# still never logged — only the rule id, scene index, and field name.
_VOCAB_ENUM_RULES = {
    "setting": "scene.setting.unknown",
    "props": "scene.props.unknown",
    "pose": "scene.character.pose.unknown",
    "expression": "scene.character.expression.unknown",
}


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

    major = _check_supported_version(script)
    _check_structure(script, major)
    _check_cross_field_safety(script)
    if major >= 2:
        _check_story_grammar(script)


def _check_supported_version(script: Mapping[str, Any]) -> int:
    """Return the schema MAJOR, rejecting versions this validator cannot handle."""
    raw_version = script.get("schema_version")
    if not isinstance(raw_version, str) or "." not in raw_version:
        _reject(
            "schema_version.malformed",
            "schema_version must be a 'MAJOR.MINOR' string",
            field="schema_version",
        )

    major_text = raw_version.split(".", 1)[0]
    try:
        major = int(major_text)
    except ValueError:
        _reject(
            "schema_version.malformed",
            "schema_version MAJOR component is not an integer",
            field="schema_version",
        )

    if major not in SUPPORTED_MAJOR_VERSIONS:
        _reject(
            "schema_version.unsupported_major",
            f"unsupported schema MAJOR {major}; supported: {sorted(SUPPORTED_MAJOR_VERSIONS)}",
            field="schema_version",
        )
    return major


def _check_structure(script: Mapping[str, Any], major: int) -> None:
    """Run the JSON Schema layer, sanitizing any error before it escapes.

    ``jsonschema`` error messages embed the offending instance value, which for
    a scene script is exactly the raw caption/narration/name we must never log.
    We therefore reconstruct a message from the *schema-side* constraint only
    (the keyword and its limit) plus the structural path — never the instance.

    The schema is selected by ``major``; a v2 enum violation on an art field is
    relabelled to its field-specific ``scene.*.unknown`` rule id.
    """
    error = best_match(_SCHEMA_VALIDATORS[major].iter_errors(dict(script)))
    if error is None:
        return

    scene_index, field = _locate(error)
    constraint = _safe_constraint(error)
    rule = f"schema.{error.validator}"
    if error.validator == "enum" and field in _VOCAB_ENUM_RULES:
        rule = _VOCAB_ENUM_RULES[field]
    _reject(
        rule,
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


def _check_story_grammar(script: Mapping[str, Any]) -> None:
    """Enforce the ADR-001 story-grammar gate (v2 only).

    Structure is already valid here, so ``author`` / ``perspective`` / ``intent``
    exist and hold enum-valid values. Two rules apply:

    * ``intent == "experiential"`` is gated (ADR-001 D2/D4) — the experiential
      track stays deferred until its preconditions are met, and encoding the gate
      in the contract keeps it alive across a prompt edit or a provider swap.
    * the instructional track must be first-person (ADR-001 D2).
    """
    if script["intent"] == "experiential":
        _reject(
            "story.intent.gated",
            "experiential intent is gated (ADR-001 D4) until its preconditions are met",
            field="intent",
        )

    if script["intent"] == "instructional" and script["perspective"] != "first_person":
        _reject(
            "story.instructional.requires_first_person",
            "instructional stories must be authored in the first person (ADR-001 D2)",
            field="perspective",
        )


def _reject(
    rule: str,
    detail: str,
    *,
    scene_index: int | None = None,
    field: str | None = None,
) -> NoReturn:
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
