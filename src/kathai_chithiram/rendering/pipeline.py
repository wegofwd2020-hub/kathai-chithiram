"""The contract-consumption layer every renderer goes through.

A renderer never trusts a raw scene script. It subclasses
:class:`SceneScriptRenderer`, whose :meth:`SceneScriptRenderer.render` enforces,
in order:

1. **Validate** the script against the contract + safety rules (KC-3) — invalid
   scripts are rejected before any frame is drawn.
2. **Reinsert** the child's real name from the token, at render time only (KC-2):
   captions/narration/title in the :class:`RenderPlan` carry the display name,
   never the stored token, and the script itself is never mutated.
3. **Version-gate** on the MAJOR versions the renderer declares it supports
   (contract §4).
4. **Produce** frames (renderer-specific) into a *draft* artifact.
5. **Guard** the produced output with the render-time safety checks (KC-4).
6. **Promote** the draft to the final path only if the guard passes — unsafe
   output is never delivered.

The subclass implements just the drawing (``_render``); all the contract and
safety enforcement lives here and is shared.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from kathai_chithiram.errors import UnsupportedSchemaVersionError
from kathai_chithiram.privacy.pseudonymize import NameMapping, reinsert
from kathai_chithiram.rendering.safety import RenderSafetyReport, guard_render
from kathai_chithiram.scene_script.validation import validate_scene_script

__all__ = [
    "PreparedScene",
    "RenderPlan",
    "RenderResult",
    "SceneScriptRenderer",
    "build_render_plan",
]


@dataclass(frozen=True)
class PreparedScene:
    """One scene, normalized for rendering with the display name reinserted.

    Args:
        index: 1-based scene index from the script.
        frame_count: Number of frames this scene occupies (``duration_s * fps``).
        duration_s: Scene duration in seconds.
        caption: Caption text with the child's display name reinserted.
        narration: Narration text with the display name reinserted.
        setting: The scene setting (e.g. ``"bathroom"``).
        transition_in: Incoming transition (``cut`` / ``fade`` / ``dissolve``).
        transition_out: Outgoing transition.
    """

    index: int
    frame_count: int
    duration_s: float
    caption: str
    narration: str
    setting: str
    transition_in: str
    transition_out: str


@dataclass(frozen=True)
class RenderPlan:
    """A validated, render-ready view of a scene script.

    Args:
        title: Story title with the display name reinserted.
        fps: Frames per second for the whole animation.
        total_frames: Sum of every scene's ``frame_count``.
        scenes: The prepared scenes, in order.
    """

    title: str
    fps: int
    total_frames: int
    scenes: tuple[PreparedScene, ...]


@dataclass(frozen=True)
class RenderResult:
    """The outcome of a successful, safety-checked render.

    Args:
        plan: The plan that was rendered.
        safety_report: The report the render-time guards passed.
        output_path: Where the final artifact was written, or ``None`` if the
            render was produced without emitting a file.
    """

    plan: RenderPlan
    safety_report: RenderSafetyReport
    output_path: str | None


def build_render_plan(
    script: Mapping[str, Any], *, mapping: NameMapping | None = None
) -> RenderPlan:
    """Validate ``script`` and return a render-ready :class:`RenderPlan`.

    Args:
        script: The scene-script document.
        mapping: Optional name mapping; when given, the child's display name is
            reinserted into the title, captions, and narration (render-time
            substitution). When ``None`` the token text is kept as-is.

    Returns:
        A :class:`RenderPlan` with per-scene frame counts and name-reinserted
        text.

    Raises:
        SceneScriptInvalidError: If the script fails contract/safety validation.
    """
    validate_scene_script(script)

    def restore(text: str) -> str:
        return reinsert(text, mapping) if mapping is not None else text

    fps = int(script["fps"])
    scenes = tuple(
        PreparedScene(
            index=int(raw["index"]),
            frame_count=round(float(raw["duration_s"]) * fps),
            duration_s=float(raw["duration_s"]),
            caption=restore(raw["caption"]),
            narration=restore(raw["narration"]),
            setting=raw["setting"],
            transition_in=raw["transition_in"],
            transition_out=raw["transition_out"],
        )
        for raw in script["scenes"]
    )
    return RenderPlan(
        title=restore(script["title"]),
        fps=fps,
        total_frames=sum(scene.frame_count for scene in scenes),
        scenes=scenes,
    )


class SceneScriptRenderer(ABC):
    """Base for renderers that consume the scene-script contract.

    Subclasses set :attr:`name` and :attr:`supported_majors` and implement
    :meth:`_render`. They get validation, name reinsertion, version gating,
    safety guarding, and safe draft→final promotion for free.
    """

    name: ClassVar[str] = "renderer"
    supported_majors: ClassVar[frozenset[int]] = frozenset({1})

    def render(
        self,
        script: Mapping[str, Any],
        *,
        mapping: NameMapping | None = None,
        output_path: str | None = None,
    ) -> RenderResult:
        """Render ``script`` safely; return a :class:`RenderResult`.

        Args:
            script: The scene-script document to render.
            mapping: Optional name mapping for render-time name reinsertion.
            output_path: Where to write the final artifact. If ``None``, frames
                are produced and guarded but no file is emitted (useful for
                tests and safety analysis).

        Returns:
            The :class:`RenderResult` for a guard-passing render.

        Raises:
            SceneScriptInvalidError: If the script is invalid.
            UnsupportedSchemaVersionError: If this renderer can't render the
                script's MAJOR version.
            RenderSafetyError: If the produced output trips a render-time guard;
                no final artifact is left behind in that case.
        """
        plan = build_render_plan(script, mapping=mapping)
        self._require_supported(script)

        if output_path is None:
            report = self._render(plan, draft_path=None)
            guard_render(report)
            return RenderResult(plan=plan, safety_report=report, output_path=None)

        # Keep the original suffix on the draft (``out.draft.mp4``, not
        # ``out.mp4.draft``): writers like imageio-ffmpeg pick the container from
        # the file extension, so a clobbered suffix breaks the actual encode.
        out = Path(output_path)
        draft_path = str(out.with_name(f"{out.stem}.draft{out.suffix}"))
        try:
            report = self._render(plan, draft_path=draft_path)
            guard_render(report)
        except BaseException:
            # Never leave an unsafe or partial draft behind.
            if os.path.exists(draft_path):
                os.remove(draft_path)
            raise

        os.replace(draft_path, output_path)
        return RenderResult(plan=plan, safety_report=report, output_path=output_path)

    def _require_supported(self, script: Mapping[str, Any]) -> None:
        """Reject a script whose schema MAJOR this renderer does not support."""
        major = int(str(script["schema_version"]).split(".", 1)[0])
        if major not in self.supported_majors:
            raise UnsupportedSchemaVersionError(
                self.name, major, sorted(self.supported_majors)
            )

    @abstractmethod
    def _render(self, plan: RenderPlan, *, draft_path: str | None) -> RenderSafetyReport:
        """Draw ``plan`` and return a safety report describing the output.

        Implementations stream frames to ``draft_path`` when it is not ``None``
        (the base promotes it to the final path only after the safety guard
        passes), and must return a :class:`RenderSafetyReport` measured from the
        output they produced.

        Args:
            plan: The validated, name-reinserted render plan.
            draft_path: Where to write the draft artifact, or ``None`` to
                produce without emitting a file.

        Returns:
            A :class:`RenderSafetyReport` for the produced output.
        """
        raise NotImplementedError
