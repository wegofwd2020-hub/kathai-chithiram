"""A structured, guided story template that lowers to a scene script (no LLM/key).

A parent needn't write free prose: they fill a simple **template** — a title and an
ordered list of **steps**, one per moment of the routine from beginning to end —
and it lowers deterministically to the same scene-script contract the renderer
consumes (ADR-005 Decision 6). One step becomes one scene. Because the author gives
the structure, each step may optionally set its own setting / props / mood / pose,
and anything left blank is inferred from the step's text (shared with the offline
path via :mod:`kathai_chithiram.generation.scene_builder`).

The template adds **no new personal data**: it holds the story text and (at lowering
time) the child's name is stripped to the token exactly as elsewhere (KC-2), so it is
not behind ADR-005's privacy gate. The human review gate still applies.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kathai_chithiram.generation.scene_builder import (
    DEFAULT_FPS,
    assemble_scene_script,
    build_scene_dict,
    guard_no_identifier,
)
from kathai_chithiram.privacy.pseudonymize import NameMapping, pseudonymize
from kathai_chithiram.scene_script.schema import MAX_CAPTION_CHARS

__all__ = [
    "MAX_TEMPLATE_STEPS",
    "StoryStep",
    "StoryTemplate",
    "load_template",
    "template_from_mapping",
    "template_to_scene_script",
]

#: A story stays a calm, short social story — cap the number of steps/scenes.
MAX_TEMPLATE_STEPS = 40
_STEP_FIELDS = frozenset({"text", "setting", "props", "expression", "pose", "sfx"})


@dataclass(frozen=True)
class StoryStep:
    """One step of the routine — becomes one scene.

    Args:
        text: What happens in this step; becomes the caption/narration. Must be
            non-empty and within the contract's caption limit. May name the child —
            the name is stripped at lowering.
        setting: Optional explicit setting (e.g. ``"a bathroom"``); inferred from the
            text when ``None``.
        props: Optional explicit prop labels; ``None`` infers them, an empty tuple
            means no props.
        expression: Optional explicit character expression; inferred when ``None``.
        pose: Optional explicit character pose; inferred when ``None``.
        sfx: Optional sound-effect cues for this step (none by default).

    Raises:
        ValueError: If ``text`` is blank or exceeds the caption limit.
    """

    text: str
    setting: str | None = None
    props: tuple[str, ...] | None = None
    expression: str | None = None
    pose: str | None = None
    sfx: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("step text must be non-empty")
        if len(self.text) > MAX_CAPTION_CHARS:
            raise ValueError(f"step text must be <= {MAX_CAPTION_CHARS} characters")


@dataclass(frozen=True)
class StoryTemplate:
    """A whole story as a title and ordered steps.

    Args:
        title: The story title (may name the child; stripped at lowering).
        steps: The routine's steps, in order. Must be non-empty and within
            :data:`MAX_TEMPLATE_STEPS`.
        fps: Frames per second for the render (8–30).
        locale: BCP-47-ish locale tag.

    Raises:
        ValueError: If ``title`` is blank, or ``steps`` is empty or too long.
    """

    title: str
    steps: tuple[StoryStep, ...]
    fps: int = DEFAULT_FPS
    locale: str = "en-US"

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("template title must be non-empty")
        if not self.steps:
            raise ValueError("template must have at least one step")
        if len(self.steps) > MAX_TEMPLATE_STEPS:
            raise ValueError(f"template must have at most {MAX_TEMPLATE_STEPS} steps")


def template_to_scene_script(
    template: StoryTemplate, mapping: NameMapping, *, story_id: str
) -> dict[str, Any]:
    """Lower a :class:`StoryTemplate` to a validated scene script.

    Each step becomes a scene; the title and every step's text are pseudonymized
    first, checked for a residual identifier (KC-2), and lowered with the step's
    explicit overrides (or inference) for setting / props / expression / pose.

    Args:
        template: The authored template.
        mapping: The child identifier→token mapping.
        story_id: Opaque id recorded on the script.

    Returns:
        A validated scene-script document (safe to store and render).

    Raises:
        IdentifierLeakError: If a child identifier survives pseudonymization.
        SceneScriptInvalidError: If the assembled script is not contract-valid.
    """
    title = pseudonymize(template.title, mapping)
    captions = [pseudonymize(step.text, mapping) for step in template.steps]
    guard_no_identifier([title, *captions], mapping)

    scenes = [
        build_scene_dict(
            index,
            caption,
            setting=step.setting,
            props=step.props,
            expression=step.expression,
            pose=step.pose,
            sfx=step.sfx,
        )
        for index, (step, caption) in enumerate(zip(template.steps, captions, strict=True), start=1)
    ]
    return assemble_scene_script(
        scenes=scenes,
        story_id=story_id,
        title=title,
        fps=template.fps,
        locale=template.locale,
    )


def load_template(path: str | Path) -> StoryTemplate:
    """Read and parse a :class:`StoryTemplate` from a JSON file.

    Args:
        path: The template JSON file.

    Returns:
        The parsed, validated template.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If the file is not valid JSON, or the template is malformed.
    """
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"template file is not valid JSON: {exc}") from exc
    return template_from_mapping(data)


def template_from_mapping(data: Any) -> StoryTemplate:
    """Build a :class:`StoryTemplate` from a decoded mapping.

    Args:
        data: The decoded template object.

    Returns:
        The parsed, validated template.

    Raises:
        ValueError: If a required field is missing or a value is invalid.
    """
    if not isinstance(data, Mapping):
        raise ValueError("template must be a JSON object")
    steps_raw = data.get("steps")
    if not isinstance(steps_raw, list):
        raise ValueError("template 'steps' must be a list")
    steps = tuple(_step(item, index) for index, item in enumerate(steps_raw))
    return StoryTemplate(
        title=_require(data, "title"),
        steps=steps,
        fps=int(data.get("fps", DEFAULT_FPS)),
        locale=str(data.get("locale", "en-US")),
    )


def _step(raw: Any, index: int) -> StoryStep:
    """Build one :class:`StoryStep` from a mapping."""
    if not isinstance(raw, Mapping):
        raise ValueError(f"step #{index} must be a JSON object")
    unknown = set(raw) - _STEP_FIELDS
    if unknown:
        raise ValueError(f"step #{index} has unknown field(s): {sorted(unknown)}")
    return StoryStep(
        text=_require(raw, "text"),
        setting=raw.get("setting"),
        props=_opt_tuple(raw.get("props")),
        expression=raw.get("expression"),
        pose=raw.get("pose"),
        sfx=tuple(raw.get("sfx") or ()),
    )


def _opt_tuple(value: Any) -> tuple[str, ...] | None:
    """Return a tuple for a supplied list, or ``None`` (infer) when absent."""
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError("'props' must be a list of strings")
    return tuple(str(item) for item in value)


def _require(data: Mapping[str, Any], key: str) -> Any:
    """Return ``data[key]`` or raise a clear error naming the missing field."""
    if key not in data:
        raise ValueError(f"template: missing required field {key!r}")
    return data[key]
