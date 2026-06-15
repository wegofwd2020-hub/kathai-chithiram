"""Render-time technical safety guards.

The scene-script validator (KC-3) checks the *script*; these guards check the
*rendered output and its render configuration* — the third enforcement point in
``docs/CONTENT_SAFETY.md`` §5: frame-rate, flashing / high-contrast oscillation
(seizure safety, §2/§3), and audio levels. A renderer runs these before any
output reaches a child; output that trips a guard is not delivered.
"""

from __future__ import annotations

from kathai_chithiram.rendering.pipeline import (
    PreparedScene,
    RenderPlan,
    RenderResult,
    SceneScriptRenderer,
    build_render_plan,
)
from kathai_chithiram.rendering.safety import (
    MAX_NARRATION_VOLUME,
    MAX_SFX_VOLUME,
    RenderSafetyReport,
    guard_audio_levels,
    guard_flashes,
    guard_frame_rate,
    guard_render,
)

__all__ = [
    "MAX_NARRATION_VOLUME",
    "MAX_SFX_VOLUME",
    "PreparedScene",
    "RenderPlan",
    "RenderResult",
    "RenderSafetyReport",
    "SceneScriptRenderer",
    "build_render_plan",
    "guard_audio_levels",
    "guard_flashes",
    "guard_frame_rate",
    "guard_render",
]
