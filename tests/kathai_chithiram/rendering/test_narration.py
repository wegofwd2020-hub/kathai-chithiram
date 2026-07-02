"""Tests for in-process narration-track assembly (name stays local).

Everything here is stdlib-only and driven by mock synthesizers, so the timing,
level-measurement, safety, and WAV-serialization paths are exercised without any
speech model or the render extra.
"""

from __future__ import annotations

import io
import wave
from collections.abc import Sequence

import pytest
from tests.kathai_chithiram.rendering.fake_renderer import tiny_script
from tests.kathai_chithiram.scene_script.mock_scripts import valid_scene_script

from kathai_chithiram.errors import RenderSafetyError
from kathai_chithiram.rendering.narration import (
    DEFAULT_SAMPLE_RATE,
    NarrationTrack,
    SilentNarrationSynthesizer,
    build_narration_track,
    guard_narration_track,
)
from kathai_chithiram.rendering.pipeline import build_render_plan


class _ConstantSynth:
    """A deterministic non-silent voice: every sample is ``amplitude``."""

    def __init__(self, amplitude: float) -> None:
        self._amplitude = amplitude

    def synthesize(self, text: str, *, sample_rate: int, duration_s: float) -> Sequence[float]:
        return [self._amplitude] * round(duration_s * sample_rate)


class _FixedLengthSynth:
    """Returns exactly ``count`` samples regardless of the scene's budget."""

    def __init__(self, amplitude: float, count: int) -> None:
        self._amplitude = amplitude
        self._count = count

    def synthesize(self, text: str, *, sample_rate: int, duration_s: float) -> Sequence[float]:
        return [self._amplitude] * self._count


def _expected_frames(plan) -> int:
    return sum(round(scene.duration_s * DEFAULT_SAMPLE_RATE) for scene in plan.scenes)


# ── the silent default ────────────────────────────────────────────────────────
def test_silent_default_is_silent_but_correctly_timed():
    plan = build_render_plan(valid_scene_script())
    track = build_narration_track(plan)  # SilentNarrationSynthesizer by default

    assert track.is_silent
    assert track.peak == 0.0
    assert track.sample_rate == DEFAULT_SAMPLE_RATE
    # Duration matches the video timeline (A/V stay in sync).
    assert len(track.samples) == _expected_frames(plan)
    assert track.duration_s == pytest.approx(sum(s.duration_s for s in plan.scenes), abs=0.01)


def test_to_wav_bytes_is_a_valid_mono_pcm_wav():
    plan = build_render_plan(valid_scene_script())
    track = build_narration_track(plan)

    with wave.open(io.BytesIO(track.to_wav_bytes())) as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == DEFAULT_SAMPLE_RATE
        assert wav.getnframes() == len(track.samples)


# ── a mock voice ──────────────────────────────────────────────────────────────
def test_peak_reflects_per_scene_volume_scaling():
    # valid_scene_script carries narration_volume 0.7; a 0.5-amplitude voice scaled
    # by 0.7 peaks at 0.35 — the measured peak, not a claimed number.
    plan = build_render_plan(valid_scene_script())
    track = build_narration_track(plan, _ConstantSynth(amplitude=0.5))

    assert not track.is_silent
    assert track.peak == pytest.approx(0.5 * 0.7, abs=1e-6)


def test_track_length_matches_video_timeline_for_a_voice():
    plan = build_render_plan(valid_scene_script())
    track = build_narration_track(plan, _ConstantSynth(amplitude=0.3))
    assert len(track.samples) == _expected_frames(plan)


def test_short_synth_output_is_padded_with_silence():
    # A voice that returns only 10 samples is padded to each scene's full budget,
    # so the track stays aligned to the video and ends on silence.
    plan = build_render_plan(valid_scene_script())
    track = build_narration_track(plan, _FixedLengthSynth(amplitude=0.4, count=10))

    assert len(track.samples) == _expected_frames(plan)
    assert track.samples[0] == pytest.approx(0.4 * 0.7, abs=1e-6)  # start: voiced
    assert track.samples[-1] == pytest.approx(0.0, abs=1e-9)  # tail: padded silence


# ── safety wiring ─────────────────────────────────────────────────────────────
def test_over_loud_track_trips_the_audio_guard():
    # narration_volume 0.95 * full-scale voice = 0.95 peak > the 0.8 gentle cap.
    script = tiny_script()
    script["scenes"][0]["audio"]["narration_volume"] = 0.95
    plan = build_render_plan(script)
    track = build_narration_track(plan, _ConstantSynth(amplitude=1.0))

    assert track.peak == pytest.approx(0.95, abs=1e-6)
    with pytest.raises(RenderSafetyError, match="narration"):
        guard_narration_track(track)


def test_gentle_track_passes_the_audio_guard():
    plan = build_render_plan(valid_scene_script())  # 0.7 volume
    track = build_narration_track(plan, _ConstantSynth(amplitude=0.6))
    guard_narration_track(track)  # 0.42 peak — under cap, no raise


def test_synth_returning_out_of_range_sample_is_rejected():
    plan = build_render_plan(valid_scene_script())
    with pytest.raises(ValueError, match=r"\[-1, 1\]"):
        build_narration_track(plan, _ConstantSynth(amplitude=1.5))


def test_non_positive_sample_rate_is_rejected():
    plan = build_render_plan(valid_scene_script())
    with pytest.raises(ValueError, match="sample_rate"):
        build_narration_track(plan, sample_rate=0)


# ── track value object ────────────────────────────────────────────────────────
def test_wav_quantizes_and_clamps():
    # A track built directly (bypassing the builder) still clamps on serialization.
    track = NarrationTrack(sample_rate=8000, samples=[0.0, 1.0, -1.0, 2.0, -2.0], peak=1.0)
    with wave.open(io.BytesIO(track.to_wav_bytes())) as wav:
        frames = wav.readframes(wav.getnframes())
    import array as _array

    pcm = _array.array("h")
    pcm.frombytes(frames)
    assert list(pcm) == [0, 32767, -32767, 32767, -32767]  # 2.0 and -2.0 clamped


def test_silent_synth_rejects_bad_args():
    synth = SilentNarrationSynthesizer()
    with pytest.raises(ValueError, match="sample_rate"):
        synth.synthesize("x", sample_rate=0, duration_s=1.0)
    with pytest.raises(ValueError, match="duration_s"):
        synth.synthesize("x", sample_rate=8000, duration_s=-1.0)
