"""Test doubles + helpers for the rendering pipeline.

A :class:`FakeRenderer` exercises the shared :class:`SceneScriptRenderer`
contract path (validate, reinsert, version-gate, guard, promote) without any
heavy rendering dependency, so the pipeline can be tested deterministically.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from kathai_chithiram.rendering.pipeline import RenderPlan, SceneScriptRenderer
from kathai_chithiram.rendering.safety import RenderSafetyReport


def tiny_script(*, fps: int = 8, duration_s: int = 2) -> dict[str, Any]:
    """Return a minimal valid 1-scene script (synthetic, CHILD token)."""
    return {
        "schema_version": "1.0",
        "story_id": "tiny",
        "title": "CHILD Waves",
        "child_token": "CHILD",
        "locale": "en-US",
        "total_duration_s": duration_s,
        "fps": fps,
        "safety": {"max_flash_hz": 3, "max_scene_cuts_per_min": 20, "reviewed_by_human": False},
        "scenes": [
            {
                "index": 1,
                "duration_s": duration_s,
                "narration": "CHILD waves hello.",
                "caption": "CHILD waves hello.",
                "setting": "bedroom",
                "characters": [{"id": "child", "pose": "standing", "expression": "calm"}],
                "props": [],
                "transition_in": "fade",
                "transition_out": "fade",
                "audio": {"narration_volume": 0.7, "sfx": []},
            }
        ],
    }


class FakeRenderer(SceneScriptRenderer):
    """A renderer that fabricates a safety report instead of drawing.

    Args:
        luminances: Luminance signal to report (defaults to a calm constant).
        narration_volume: Narration level to report.
        write_draft: Whether to actually create the draft file when given a path
            (lets a test confirm an unsafe draft is cleaned up).
    """

    name = "fake"
    supported_majors = frozenset({1})

    def __init__(
        self,
        *,
        luminances: Sequence[float] | None = None,
        narration_volume: float = 0.0,
        write_draft: bool = True,
    ) -> None:
        self._luminances = luminances
        self._narration_volume = narration_volume
        self._write_draft = write_draft
        self.render_calls = 0

    def _render(self, plan: RenderPlan, *, draft_path: str | None) -> RenderSafetyReport:
        self.render_calls += 1
        if draft_path is not None and self._write_draft:
            with open(draft_path, "w", encoding="utf-8") as handle:
                handle.write("draft-bytes")
        luminances = (
            self._luminances if self._luminances is not None else [0.5] * max(plan.total_frames, 2)
        )
        return RenderSafetyReport(
            fps=plan.fps,
            luminances=luminances,
            narration_volume=self._narration_volume,
            sfx_levels=[],
        )


class UnsupportedMajorRenderer(FakeRenderer):
    """A renderer that supports only a non-existent MAJOR, to test version gating."""

    name = "fake-v2only"
    supported_majors = frozenset({2})
