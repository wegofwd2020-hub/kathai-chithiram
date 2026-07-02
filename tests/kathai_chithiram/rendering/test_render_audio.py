"""Tests for narration audio through the renderer: track → mux → mp4 with audio.

These exercise the real ffmpeg mux (render extra), so they import-skip when it is
unavailable. A deterministic mock voice stands in for a real TTS engine.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from tests.kathai_chithiram.rendering.fake_renderer import tiny_script

from kathai_chithiram.errors import RenderSafetyError
from kathai_chithiram.rendering.audio_mux import mux_wav_into_mp4
from kathai_chithiram.rendering.narration import NarrationTrack, build_narration_track
from kathai_chithiram.rendering.pipeline import build_render_plan


class _ConstantVoice:
    """A deterministic non-silent voice: every sample is ``amplitude``."""

    def __init__(self, amplitude: float = 0.5) -> None:
        self._amplitude = amplitude

    def synthesize(self, text: str, *, sample_rate: int, duration_s: float) -> Sequence[float]:
        return [self._amplitude] * round(duration_s * sample_rate)


class _ConstantSfx:
    """A deterministic non-silent cue source: every sample is ``amplitude``."""

    def __init__(self, amplitude: float = 0.4) -> None:
        self._amplitude = amplitude

    def synthesize(self, cue: str, *, sample_rate: int, duration_s: float) -> Sequence[float]:
        return [self._amplitude] * round(duration_s * sample_rate)


def _has_audio_stream(path: Path) -> bool:
    import imageio_ffmpeg

    probe = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True
    )
    return any("Audio:" in line for line in probe.stderr.splitlines())


def _tiny_video(path: Path) -> None:
    import imageio
    import numpy as np

    writer = imageio.get_writer(
        str(path), fps=8, codec="libx264", macro_block_size=1, ffmpeg_log_level="quiet"
    )
    try:
        for value in (40, 120, 60, 180):
            writer.append_data(np.full((24, 32, 3), value, dtype="uint8"))
    finally:
        writer.close()


# ── the mux utility ───────────────────────────────────────────────────────────
def test_mux_adds_an_audio_stream(tmp_path: Path):
    pytest.importorskip("imageio")
    pytest.importorskip("imageio_ffmpeg")
    video = tmp_path / "v.mp4"
    _tiny_video(video)
    assert not _has_audio_stream(video)

    plan = build_render_plan(tiny_script(fps=8, duration_s=2))
    track = build_narration_track(plan, _ConstantVoice(0.3))
    mux_wav_into_mp4(str(video), track.to_wav_bytes())

    assert _has_audio_stream(video)
    assert not (tmp_path / "v.muxed.mp4").exists()  # promoted, not left behind


def test_mux_failure_leaves_no_partial_output(tmp_path: Path):
    pytest.importorskip("imageio_ffmpeg")
    not_a_video = tmp_path / "x.mp4"
    not_a_video.write_bytes(b"this is not a video")
    with pytest.raises(RuntimeError, match="mux failed"):
        mux_wav_into_mp4(str(not_a_video), NarrationTrack(8000, [0.1] * 100, 0.1).to_wav_bytes())
    assert not (tmp_path / "x.muxed.mp4").exists()


# ── renderer integration (matplotlib) ─────────────────────────────────────────
def _matplotlib_renderer():
    pytest.importorskip("matplotlib")
    pytest.importorskip("imageio")
    pytest.importorskip("imageio_ffmpeg")
    from generate_animation import MatplotlibStickFigureRenderer

    return MatplotlibStickFigureRenderer()


def test_render_with_voice_muxes_audio(tmp_path: Path):
    renderer = _matplotlib_renderer()
    out = tmp_path / "o.mp4"
    result = renderer.render(
        tiny_script(fps=8, duration_s=2), output_path=str(out), narration=_ConstantVoice(0.5)
    )
    assert result.has_audio is True
    assert _has_audio_stream(out)
    # narration_volume in the report is the MEASURED peak (0.5 * 0.7 volume).
    assert result.safety_report.narration_volume == pytest.approx(0.5 * 0.7, abs=1e-3)


def test_render_without_voice_is_silent(tmp_path: Path):
    renderer = _matplotlib_renderer()
    out = tmp_path / "o.mp4"
    result = renderer.render(tiny_script(fps=8, duration_s=2), output_path=str(out))
    assert result.has_audio is False
    assert not _has_audio_stream(out)


def test_over_loud_voice_trips_guard_and_leaves_no_output(tmp_path: Path):
    renderer = _matplotlib_renderer()
    script = tiny_script(fps=8, duration_s=2)
    script["scenes"][0]["audio"]["narration_volume"] = 0.95  # * full-scale = 0.95 > 0.8 cap
    out = tmp_path / "o.mp4"
    with pytest.raises(RenderSafetyError, match="narration"):
        renderer.render(script, output_path=str(out), narration=_ConstantVoice(1.0))
    assert not out.exists()
    assert not (tmp_path / "o.draft.mp4").exists()


def test_guard_only_render_measures_audio_without_a_file(tmp_path: Path):
    renderer = _matplotlib_renderer()
    result = renderer.render(
        tiny_script(fps=8, duration_s=2), output_path=None, narration=_ConstantVoice(0.5)
    )
    assert result.output_path is None
    assert result.has_audio is True
    assert result.safety_report.narration_volume == pytest.approx(0.5 * 0.7, abs=1e-3)


# ── sfx integration (matplotlib) ──────────────────────────────────────────────
def test_render_with_sfx_muxes_audio(tmp_path: Path):
    renderer = _matplotlib_renderer()
    script = tiny_script(fps=8, duration_s=2)
    script["scenes"][0]["audio"]["sfx"] = ["water_running"]
    out = tmp_path / "o.mp4"
    result = renderer.render(script, output_path=str(out), sfx=_ConstantSfx(0.4))

    assert result.has_audio is True
    assert _has_audio_stream(out)
    # sfx cues carry no author volume, so the measured peak is the source's own.
    assert tuple(result.safety_report.sfx_levels) == pytest.approx((0.4,))


def test_render_with_narration_and_sfx_mixes_both(tmp_path: Path):
    renderer = _matplotlib_renderer()
    script = tiny_script(fps=8, duration_s=2)
    script["scenes"][0]["audio"]["sfx"] = ["bird"]
    out = tmp_path / "o.mp4"
    result = renderer.render(
        script, output_path=str(out), narration=_ConstantVoice(0.5), sfx=_ConstantSfx(0.3)
    )

    assert result.has_audio is True
    assert _has_audio_stream(out)
    assert result.safety_report.narration_volume == pytest.approx(0.5 * 0.7, abs=1e-3)
    assert tuple(result.safety_report.sfx_levels) == pytest.approx((0.3,))


def test_over_loud_sfx_trips_guard_and_leaves_no_output(tmp_path: Path):
    renderer = _matplotlib_renderer()
    script = tiny_script(fps=8, duration_s=2)
    script["scenes"][0]["audio"]["sfx"] = ["boom"]
    out = tmp_path / "o.mp4"
    with pytest.raises(RenderSafetyError, match="sfx"):
        renderer.render(script, output_path=str(out), sfx=_ConstantSfx(0.9))  # 0.9 > 0.5 cap
    assert not out.exists()
    assert not (tmp_path / "o.draft.mp4").exists()
