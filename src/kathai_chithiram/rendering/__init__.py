"""Render-time technical safety guards.

The scene-script validator (KC-3) checks the *script*; these guards check the
*rendered output and its render configuration* — the third enforcement point in
``docs/CONTENT_SAFETY.md`` §5: frame-rate, flashing / high-contrast oscillation
(seizure safety, §2/§3), and audio levels. A renderer runs these before any
output reaches a child; output that trips a guard is not delivered.
"""

from __future__ import annotations

from kathai_chithiram.rendering.audio_mux import mux_wav_into_mp4
from kathai_chithiram.rendering.captions import Cue, build_captions, to_srt, to_vtt
from kathai_chithiram.rendering.narration import (
    DEFAULT_SAMPLE_RATE,
    NarrationSynthesizer,
    NarrationTrack,
    SilentNarrationSynthesizer,
    build_narration_track,
    guard_narration_track,
    mono_wav_bytes,
)
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
from kathai_chithiram.rendering.sfx import (
    SfxBed,
    SfxSynthesizer,
    SilentSfxSynthesizer,
    build_sfx_bed,
    guard_sfx_bed,
)
from kathai_chithiram.rendering.sounds import DEFAULT_SFX_GAIN, SoundBankSfxSynthesizer
from kathai_chithiram.rendering.transitions import (
    TRANSITION_SECONDS,
    BlendSource,
    FrameComposite,
    composite_plan,
    transition_frames,
)
from kathai_chithiram.rendering.voices import CliTtsSynthesizer

__all__ = [
    "DEFAULT_SAMPLE_RATE",
    "DEFAULT_SFX_GAIN",
    "MAX_NARRATION_VOLUME",
    "MAX_SFX_VOLUME",
    "CliTtsSynthesizer",
    "NarrationSynthesizer",
    "NarrationTrack",
    "PreparedScene",
    "RenderPlan",
    "RenderResult",
    "RenderSafetyReport",
    "SceneScriptRenderer",
    "SfxBed",
    "SfxSynthesizer",
    "SilentNarrationSynthesizer",
    "SilentSfxSynthesizer",
    "SoundBankSfxSynthesizer",
    "TRANSITION_SECONDS",
    "BlendSource",
    "Cue",
    "FrameComposite",
    "build_captions",
    "build_narration_track",
    "build_render_plan",
    "build_sfx_bed",
    "composite_plan",
    "to_srt",
    "to_vtt",
    "guard_audio_levels",
    "guard_flashes",
    "guard_frame_rate",
    "guard_narration_track",
    "guard_render",
    "guard_sfx_bed",
    "mono_wav_bytes",
    "mux_wav_into_mp4",
    "transition_frames",
]
