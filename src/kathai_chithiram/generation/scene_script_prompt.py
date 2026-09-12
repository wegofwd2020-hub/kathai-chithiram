"""Build the system prompt that drives scene-script generation.

The content-safety prompt (:mod:`kathai_chithiram.generation.system_prompt`)
says *what* a story may contain; this module adds *how* the model must shape its
output: a single JSON object conforming to the scene-script v2 contract
(``docs/SCENE_SCRIPT_CONTRACT.md`` §3), including the rules a JSON Schema cannot
express on its own (caption must match narration, sequential scene indices, the
declared total duration must equal the sum of scene durations, no content-safety
flags), the story-grammar fields (author/perspective/intent, closed art vocabulary),
and a worked example.

The model only ever sees the placeholder ``child_token`` — never a real name
(PRIVACY.md §6 / KC-2). The emitted script is validated against the contract
before any rendering (KC-3); this prompt is the *first* line of defence, not the
last, so it is paired with the validate-and-repair loop in
:mod:`kathai_chithiram.generation.generator`.
"""

from __future__ import annotations

import json
from typing import Any

from kathai_chithiram.generation.system_prompt import build_generation_system_prompt
from kathai_chithiram.privacy.pseudonymize import DEFAULT_CHILD_TOKEN
from kathai_chithiram.scene_script.schema import SCENE_SCRIPT_SCHEMA_V2

__all__ = [
    "EXAMPLE_SCENE_SCRIPT",
    "build_scene_script_system_prefix",
    "build_scene_script_system_prompt",
]

#: A synthetic, fully contract-valid example shown to the model so it has a
#: concrete target shape. Wholly fictional; the child appears only as the token
#: (CLAUDE.md: no real child data). A test asserts this passes
#: :func:`kathai_chithiram.scene_script.validation.validate_scene_script`.
EXAMPLE_SCENE_SCRIPT: dict[str, Any] = {
    "schema_version": "2.0",
    "story_id": "00000000-0000-0000-0000-000000000001",
    "title": "Brushing Teeth With CHILD",
    "child_token": "CHILD",
    "locale": "en-US",
    "author": "parent",
    "perspective": "first_person",
    "intent": "instructional",
    "total_duration_s": 8,
    "fps": 24,
    "safety": {
        "max_flash_hz": 3,
        "max_scene_cuts_per_min": 12,
        "reviewed_by_human": False,
    },
    "scenes": [
        {
            "index": 1,
            "duration_s": 4,
            "narration": "I pick up my toothbrush.",
            "caption": "I pick up my toothbrush.",
            "setting": "bathroom",
            "characters": [{"id": "child", "pose": "rest", "expression": "calm"}],
            "props": ["toothbrush", "toothpaste"],
            "transition_in": "fade",
            "transition_out": "dissolve",
            "audio": {"narration_volume": 0.7, "sfx": []},
        },
        {
            "index": 2,
            "duration_s": 4,
            "narration": "I brush and I smile.",
            "caption": "I brush and I smile.",
            "setting": "bathroom",
            "characters": [{"id": "child", "pose": "wave", "expression": "smile"}],
            "props": ["toothbrush"],
            "transition_in": "dissolve",
            "transition_out": "fade",
            "audio": {"narration_volume": 0.7, "sfx": []},
        },
    ],
}


def _cross_field_rules(child_token: str) -> str:
    """Render the rules the JSON Schema cannot express, as model instructions.

    These mirror ``validation._check_cross_field_safety`` exactly, so a model
    that follows them produces output the validator accepts on the first try.
    """
    return "\n".join(
        f"- {rule}"
        for rule in (
            f"Refer to the child only as '{child_token}' in every field; never a real name.",
            "Each scene's 'caption' MUST be identical to its 'narration', character for character.",
            "Scene 'index' values MUST start at 1 and increase by 1 with no gaps, in array order.",
            "'total_duration_s' MUST equal the exact sum of every scene's 'duration_s'.",
            "Do not emit any 'content_flags'; a single flagged scene rejects the whole script.",
            "Keep each narration one short, literal sentence (140 characters or fewer).",
            "Set 'author' to 'parent', 'perspective' to 'first_person',"
            " and 'intent' to 'instructional'.",
            "Write narration in the first person ('I ...');"
            " instructional stories must be first person.",
            "Choose 'setting', 'props', each character's 'pose', and each character's"
            " 'expression' only from the enumerated values in the schema above;"
            " do not invent new ones.",
        )
    )


def build_scene_script_system_prefix(
    *, child_token: str = DEFAULT_CHILD_TOKEN, grounding_block: str = ""
) -> str:
    """Build the static, cacheable part of the system prompt (no repair feedback).

    This is everything that does not change between the attempts for one story:
    the content-safety rules, the JSON Schema, the cross-field rules, and the
    worked example. It is deliberately free of the volatile repair feedback, so
    it is byte-identical across a story's attempts and can be marked cacheable on
    a provider that supports prompt caching (KC-12), turning the bulk of the
    prompt into a cache read on every repair attempt.

    Args:
        child_token: The placeholder the model must use in place of any real
            name. Defaults to the pipeline's ``CHILD`` token; pass the active
            mapping's token so the example and rules agree with what the seam
            substitutes.
        grounding_block: Optional cited reference block surfaced by the retrieval
            layer (KC-21). When non-empty it is inserted after the safety rules
            and before the ``OUTPUT FORMAT`` section so the model can ground its
            output in retrieved practice evidence. When ``""`` (the default) the
            returned prefix is byte-identical to the pre-KC-21 output, preserving
            prompt-cache hits for non-grounded calls.

    Returns:
        The static system-prompt prefix.
    """
    safety = build_generation_system_prompt(child_token=child_token)
    schema = json.dumps(SCENE_SCRIPT_SCHEMA_V2, indent=2, sort_keys=True)
    example = json.dumps(EXAMPLE_SCENE_SCRIPT, indent=2, sort_keys=True)

    sections: list[str] = [safety]
    if grounding_block:
        sections += ["", grounding_block]
    sections += [
        "",
        "OUTPUT FORMAT",
        "Emit exactly one JSON object that conforms to the scene-script contract "
        "below, and nothing else — no prose, no Markdown, no code fences.",
        "",
        "The object MUST validate against this JSON Schema (Draft 2020-12):",
        schema,
        "",
        "It MUST also satisfy these rules, which the schema cannot express:",
        _cross_field_rules(child_token),
        "",
        "Here is a complete, valid example to follow (your story will differ):",
        example,
    ]
    return "\n".join(sections)


def _repair_suffix(repair_feedback: str | None) -> str:
    """Render the volatile repair-feedback suffix, or ``""`` on the first attempt."""
    if not repair_feedback:
        return ""
    return (
        "\n\nYour previous attempt was rejected. Fix it and emit a corrected "
        f"JSON object. Reason: {repair_feedback}"
    )


def build_scene_script_system_prompt(
    *,
    child_token: str = DEFAULT_CHILD_TOKEN,
    repair_feedback: str | None = None,
) -> str:
    """Build the full system prompt for one scene-script generation attempt.

    The full prompt is the cacheable prefix
    (:func:`build_scene_script_system_prefix`) followed by the volatile repair
    suffix. On the first attempt the two coincide; on a repair attempt only the
    suffix changes, which is what makes the prefix cacheable.

    Args:
        child_token: The placeholder the model must use in place of any real
            name. Defaults to the pipeline's ``CHILD`` token; pass the active
            mapping's token so the example and rules agree with what the seam
            substitutes.
        repair_feedback: Optional log-safe description of why a *previous*
            attempt failed validation (rule id and field, never raw story text).
            When present, it is appended so the model avoids repeating the same
            violation. ``None`` on the first attempt.

    Returns:
        A system-prompt string: the static prefix plus any repair feedback.
    """
    return build_scene_script_system_prefix(child_token=child_token) + _repair_suffix(
        repair_feedback
    )
