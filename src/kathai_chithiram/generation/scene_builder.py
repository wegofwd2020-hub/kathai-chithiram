"""Shared, deterministic lowering of captions into a contract-valid scene script.

Both non-LLM authoring paths — offline story segmentation
(:mod:`kathai_chithiram.generation.offline`) and the guided story template
(:mod:`kathai_chithiram.authoring.template`) — end with the same job: turn a list
of already-pseudonymized captions into scenes with calm defaults, and assemble +
validate the top-level script. This module is that one shared lowering, so the two
paths cannot drift.

Each scene's setting, props, character expression/pose, and duration are **inferred
from the caption** by keyword when not supplied, and any of them may be **overridden**
by a caller that knows better (the template lets an author set them explicitly). The
inferred strings deliberately match the render-time art layer's vocabulary, so an
inferred value and its backdrop/figure stay aligned. Captions passed here must already
be pseudonymized (the child's name stripped); :func:`guard_no_identifier` is the
belt-and-braces check that no identifier survived (KC-2).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from kathai_chithiram.errors import IdentifierLeakError
from kathai_chithiram.privacy.pseudonymize import NameMapping, count_identifiers
from kathai_chithiram.scene_script.validation import validate_scene_script

__all__ = [
    "DEFAULT_FPS",
    "assemble_scene_script",
    "build_scene_dict",
    "guard_no_identifier",
]

#: Default frames per second for a generated script.
DEFAULT_FPS = 24
_DEFAULT_SETTING = "a calm, quiet place"

# Ordered (keywords, setting) — first match wins. The setting strings deliberately
# contain the keywords the render-time art layer recognizes (e.g. "a bathroom" holds
# "bath"), so an inferred setting and its backdrop stay aligned.
_SETTING_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("bath", "sink", "toilet", "toothbrush", "teeth", "brush"), "a bathroom"),
    (("bed", "sleep", "asleep", "nap", "pillow", "bedtime", "night"), "a bedroom"),
    (("kitchen", "cook", "meal", "breakfast", "dinner", "lunch", "eat"), "a kitchen"),
    (("classroom", "school", "teacher", "lesson", "desk"), "a classroom"),
    (("park", "garden", "outside", "outdoor", "playground", "tree", "beach", "yard"), "outdoors"),
)

# Ordered (keywords, canonical prop). The canonical names match the render-time prop
# registry, so an inferred prop is one the renderer knows how to draw.
_PROP_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("toothbrush", "brush", "teeth"), "toothbrush"),
    (("toothpaste", "paste"), "toothpaste"),
    (("ball",), "ball"),
    (("book", "reading"), "book"),
    (("block",), "blocks"),
    (("teddy", "bear", "doll", " toy", "toys"), "toy"),
    (("cup", "juice", "milk", "bottle"), "cup"),
    (("apple", "fruit"), "apple"),
    (("backpack", "school bag", "rucksack"), "backpack"),
    (("spoon",), "spoon"),
    (("shoe", "sneaker", "trainer"), "shoes"),
    (("plate", "lunch", "dinner", "breakfast", "meal", "food"), "plate"),
)
_MAX_INFERRED_PROPS = 2

_SLEEPY_CAP = ("sleep", "asleep", "nap", "tired", "yawn", "bedtime", "drowsy")
_WORRIED_CAP = ("scared", "afraid", "worried", "nervous", "upset", "sad", "cried", "anxious")
_HAPPY_CAP = ("smil", "happ", "laugh", "proud", "glad", "excit", "cheer", "giggle", "joy")
_WAVE_CAP = ("wave", "hello", "hiya", "goodbye", "greet")


def build_scene_dict(
    index: int,
    caption: str,
    *,
    setting: str | None = None,
    props: Sequence[str] | None = None,
    expression: str | None = None,
    pose: str | None = None,
    sfx: Sequence[str] | None = None,
    duration_s: int | None = None,
    narration_volume: float = 0.7,
) -> dict[str, Any]:
    """Build one contract-shaped scene dict from an (already-pseudonymized) caption.

    Any of ``setting`` / ``props`` / ``expression`` / ``pose`` / ``duration_s`` left
    ``None`` is inferred from the caption; a supplied value is used verbatim.

    Args:
        index: 1-based scene index.
        caption: The scene caption == narration (name already stripped).
        setting: Override for the scene setting.
        props: Override for the prop list (``None`` = infer; an empty sequence = no
            props).
        expression: Override for the character's expression.
        pose: Override for the character's pose.
        sfx: The scene's sfx cues (``None``/empty = none).
        duration_s: Fixed duration (2–8 s); ``None`` sizes it to the caption.
        narration_volume: Per-scene narration level.

    Returns:
        A scene dict matching the scene-script contract.
    """
    return {
        "index": index,
        "duration_s": duration_s if duration_s is not None else _reading_duration_s(caption),
        "narration": caption,
        "caption": caption,  # contract: caption must match narration verbatim
        "setting": setting if setting is not None else _infer_setting(caption),
        "characters": [
            {
                "id": "child",
                "pose": pose if pose is not None else _infer_pose(caption),
                "expression": expression if expression is not None else _infer_expression(caption),
            }
        ],
        "props": list(props) if props is not None else _infer_props(caption),
        "transition_in": "fade",
        "transition_out": "fade",
        "audio": {"narration_volume": narration_volume, "sfx": list(sfx) if sfx else []},
    }


def assemble_scene_script(
    *,
    scenes: list[dict[str, Any]],
    story_id: str,
    title: str,
    fps: int = DEFAULT_FPS,
    locale: str = "en-US",
) -> dict[str, Any]:
    """Wrap ``scenes`` in the top-level script fields, validate, and return it.

    Args:
        scenes: The scene dicts (from :func:`build_scene_dict`), in order.
        story_id: Opaque id recorded on the script.
        title: The story title (already pseudonymized).
        fps: Frames per second (8–30).
        locale: BCP-47-ish locale tag.

    Returns:
        A validated scene-script document.

    Raises:
        SceneScriptInvalidError: If the assembled script fails contract/safety
            validation.
    """
    script: dict[str, Any] = {
        "schema_version": "1.0",
        "story_id": story_id,
        "title": title,
        "child_token": "CHILD",
        "locale": locale,
        "total_duration_s": sum(scene["duration_s"] for scene in scenes),
        "fps": fps,
        "safety": {"max_flash_hz": 3, "max_scene_cuts_per_min": 20, "reviewed_by_human": False},
        "scenes": scenes,
    }
    validate_scene_script(script)
    return script


def guard_no_identifier(captions: Sequence[str], mapping: NameMapping) -> None:
    """Raise if any child identifier survived pseudonymization in ``captions``.

    A residual match after pseudonymization is a hard stop (KC-2 / DPIA R1): the
    child's name must never reach the stored script. Only the count is surfaced.

    Args:
        captions: The pseudonymized texts to check.
        mapping: The identifier→token mapping.

    Raises:
        IdentifierLeakError: If any identifier remains.
    """
    residual = sum(count_identifiers(caption, mapping) for caption in captions)
    if residual:
        raise IdentifierLeakError(residual)


def _infer_setting(caption: str) -> str:
    """Infer a scene ``setting`` string from the caption's keywords."""
    text = caption.lower()
    for keywords, setting in _SETTING_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return setting
    return _DEFAULT_SETTING


def _infer_props(caption: str) -> list[str]:
    """Infer up to ``_MAX_INFERRED_PROPS`` prop labels from the caption's keywords."""
    text = caption.lower()
    props: list[str] = []
    for keywords, prop in _PROP_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            props.append(prop)
        if len(props) >= _MAX_INFERRED_PROPS:
            break
    return props


def _infer_expression(caption: str) -> str:
    """Infer the character's expression from the caption (sleepy > worried > happy)."""
    text = caption.lower()
    if any(word in text for word in _SLEEPY_CAP):
        return "sleepy"
    if any(word in text for word in _WORRIED_CAP):
        return "worried"
    if any(word in text for word in _HAPPY_CAP):
        return "happy"
    return "calm"


def _infer_pose(caption: str) -> str:
    """Infer the character's pose from the caption."""
    return "waving" if any(word in caption.lower() for word in _WAVE_CAP) else "standing"


def _reading_duration_s(caption: str) -> int:
    """Give a caption enough time on screen to be read, within the 2–8 s band.

    Roughly two-thirds of a second per word, so short captions get a calm 2–3 s and
    longer ones up to the contract's 8 s ceiling.
    """
    words = len(caption.split())
    return max(2, min(8, round(1 + 0.6 * words)))
