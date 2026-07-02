"""Tests for in-process sfx-bed assembly and its pipeline wiring (stays local).

Everything here is stdlib-only and driven by mock synthesizers, so the timing,
placement, per-cue level measurement, mixing, safety, and WAV paths are exercised
without any sound bank or the render extra. The pipeline-wiring tests drive a
:class:`FakeRenderer` with ``output_path=None`` (guard-only), so no muxing/ffmpeg
is needed — the real mux is covered in ``test_render_audio.py``.
"""

from __future__ import annotations

import io
import wave
from collections.abc import Sequence

import pytest
from tests.kathai_chithiram.rendering.fake_renderer import FakeRenderer, tiny_script
from tests.kathai_chithiram.scene_script.mock_scripts import valid_scene_script

from kathai_chithiram.errors import RenderSafetyError
from kathai_chithiram.rendering.narration import DEFAULT_SAMPLE_RATE
from kathai_chithiram.rendering.pipeline import build_render_plan
from kathai_chithiram.rendering.sfx import (
    SfxBed,
    SilentSfxSynthesizer,
    build_sfx_bed,
    guard_sfx_bed,
)


class _ConstantSfx:
    """A deterministic non-silent cue source: every sample is ``amplitude``."""

    def __init__(self, amplitude: float) -> None:
        self._amplitude = amplitude

    def synthesize(self, cue: str, *, sample_rate: int, duration_s: float) -> Sequence[float]:
        return [self._amplitude] * round(duration_s * sample_rate)


class _FixedLengthSfx:
    """Returns exactly ``count`` samples regardless of the scene's budget."""

    def __init__(self, amplitude: float, count: int) -> None:
        self._amplitude = amplitude
        self._count = count

    def synthesize(self, cue: str, *, sample_rate: int, duration_s: float) -> Sequence[float]:
        return [self._amplitude] * self._count


def _expected_frames(plan) -> int:
    return sum(round(scene.duration_s * DEFAULT_SAMPLE_RATE) for scene in plan.scenes)


def _with_sfx(script: dict, per_scene_cues: Sequence[Sequence[str]]) -> dict:
    """Set each scene's ``audio.sfx`` cue list from ``per_scene_cues``."""
    for scene, cues in zip(script["scenes"], per_scene_cues, strict=True):
        scene["audio"]["sfx"] = list(cues)
    return script


# ── the silent default ────────────────────────────────────────────────────────
def test_silent_default_is_silent_but_correctly_timed():
    plan = build_render_plan(_with_sfx(valid_scene_script(), [["water"], ["bird"]]))
    bed = build_sfx_bed(plan)  # SilentSfxSynthesizer by default

    assert bed.is_silent
    assert bed.peak == 0.0
    assert bed.sample_rate == DEFAULT_SAMPLE_RATE
    # One measured peak per cue, all silent.
    assert bed.cue_peaks == (0.0, 0.0)
    # Duration matches the narration timeline (A/V and audio stay in sync).
    assert len(bed.samples) == _expected_frames(plan)
    assert bed.duration_s == pytest.approx(sum(s.duration_s for s in plan.scenes), abs=0.01)


def test_no_cues_yields_a_silent_bed_with_no_cue_peaks():
    plan = build_render_plan(valid_scene_script())  # every scene sfx=[]
    bed = build_sfx_bed(plan, _ConstantSfx(0.9))  # loud source, but nothing to play

    assert bed.cue_peaks == ()
    assert bed.is_silent
    assert len(bed.samples) == _expected_frames(plan)


def test_to_wav_bytes_is_a_valid_mono_pcm_wav():
    plan = build_render_plan(_with_sfx(valid_scene_script(), [["a"], ["b"]]))
    bed = build_sfx_bed(plan)

    with wave.open(io.BytesIO(bed.to_wav_bytes())) as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == DEFAULT_SAMPLE_RATE
        assert wav.getnframes() == len(bed.samples)


# ── placement, measurement, mixing ─────────────────────────────────────────────
def test_cue_plays_only_in_its_scenes_window():
    # A single cue on scene 2 leaves scene 1's window silent and fills scene 2's.
    plan = build_render_plan(_with_sfx(valid_scene_script(), [[], ["bird"]]))
    bed = build_sfx_bed(plan, _ConstantSfx(0.4))

    scene1_frames = round(plan.scenes[0].duration_s * DEFAULT_SAMPLE_RATE)
    assert bed.cue_peaks == pytest.approx((0.4,))
    assert bed.samples[0] == pytest.approx(0.0)  # scene 1: silent
    assert bed.samples[scene1_frames - 1] == pytest.approx(0.0)  # last of scene 1
    assert bed.samples[scene1_frames] == pytest.approx(0.4)  # first of scene 2
    assert bed.samples[-1] == pytest.approx(0.4)  # scene 2 filled to the end


def test_overlapping_cues_in_one_scene_mix_and_clamp():
    # Two cues at 0.5 in the same scene sum to 1.0; each cue's own peak is 0.5.
    plan = build_render_plan(_with_sfx(valid_scene_script(), [["a", "b"], []]))
    bed = build_sfx_bed(plan, _ConstantSfx(0.5))

    assert bed.cue_peaks == pytest.approx((0.5, 0.5))
    assert bed.samples[0] == pytest.approx(1.0)  # 0.5 + 0.5 mixed
    assert bed.peak == pytest.approx(1.0)


def test_mix_is_clamped_so_overlap_never_clips():
    # Two full-scale cues sum to 2.0 but the mixed bed is clamped to 1.0.
    plan = build_render_plan(_with_sfx(valid_scene_script(), [["a", "b"], []]))
    bed = build_sfx_bed(plan, _ConstantSfx(1.0))
    assert bed.peak == pytest.approx(1.0)
    assert max(bed.samples) == pytest.approx(1.0)


def test_cue_longer_than_scene_is_truncated_to_the_window():
    # A source returning far more than the budget is cut to the scene window, so
    # a later scene's window stays untouched.
    plan = build_render_plan(_with_sfx(valid_scene_script(), [["a"], []]))
    huge = _expected_frames(plan) * 2
    bed = build_sfx_bed(plan, _FixedLengthSfx(0.3, count=huge))

    scene1_frames = round(plan.scenes[0].duration_s * DEFAULT_SAMPLE_RATE)
    assert bed.samples[scene1_frames - 1] == pytest.approx(0.3)  # scene 1 filled
    assert bed.samples[scene1_frames] == pytest.approx(0.0)  # scene 2 untouched
    assert bed.cue_peaks == pytest.approx((0.3,))


# ── safety wiring ─────────────────────────────────────────────────────────────
def test_over_loud_cue_trips_the_audio_guard():
    plan = build_render_plan(_with_sfx(valid_scene_script(), [["boom"], []]))
    bed = build_sfx_bed(plan, _ConstantSfx(0.9))  # 0.9 > the 0.5 sfx cap

    assert bed.cue_peaks == pytest.approx((0.9,))
    with pytest.raises(RenderSafetyError, match="sfx"):
        guard_sfx_bed(bed)


def test_gentle_cue_passes_the_audio_guard():
    plan = build_render_plan(_with_sfx(valid_scene_script(), [["water"], ["bird"]]))
    bed = build_sfx_bed(plan, _ConstantSfx(0.4))  # under the 0.5 cap
    guard_sfx_bed(bed)  # no raise


def test_synth_returning_out_of_range_sample_is_rejected():
    plan = build_render_plan(_with_sfx(valid_scene_script(), [["a"], []]))
    with pytest.raises(ValueError, match=r"\[-1, 1\]"):
        build_sfx_bed(plan, _ConstantSfx(1.5))


def test_non_positive_sample_rate_is_rejected():
    plan = build_render_plan(valid_scene_script())
    with pytest.raises(ValueError, match="sample_rate"):
        build_sfx_bed(plan, sample_rate=0)


def test_silent_synth_rejects_bad_args():
    synth = SilentSfxSynthesizer()
    with pytest.raises(ValueError, match="sample_rate"):
        synth.synthesize("x", sample_rate=0, duration_s=1.0)
    with pytest.raises(ValueError, match="duration_s"):
        synth.synthesize("x", sample_rate=8000, duration_s=-1.0)


# ── bed value object ────────────────────────────────────────────────────────────
def test_wav_quantizes_and_clamps():
    bed = SfxBed(sample_rate=8000, samples=[0.0, 1.0, -1.0, 2.0, -2.0], cue_peaks=(1.0,), peak=1.0)
    with wave.open(io.BytesIO(bed.to_wav_bytes())) as wav:
        frames = wav.readframes(wav.getnframes())
    import array as _array

    pcm = _array.array("h")
    pcm.frombytes(frames)
    assert list(pcm) == [0, 32767, -32767, 32767, -32767]  # 2.0 and -2.0 clamped


# ── pipeline wiring (guard-only; no ffmpeg) ─────────────────────────────────────
def test_pipeline_folds_measured_sfx_levels_into_the_report():
    script = tiny_script()
    script["scenes"][0]["audio"]["sfx"] = ["water"]
    result = FakeRenderer().render(script, output_path=None, sfx=_ConstantSfx(0.4))

    assert result.has_audio is True
    # The renderer's placeholder sfx_levels ([]) is replaced by the measured peak.
    assert tuple(result.safety_report.sfx_levels) == pytest.approx((0.4,))


def test_pipeline_rejects_an_over_loud_sfx_cue():
    script = tiny_script()
    script["scenes"][0]["audio"]["sfx"] = ["boom"]
    with pytest.raises(RenderSafetyError, match="sfx"):
        FakeRenderer().render(script, output_path=None, sfx=_ConstantSfx(0.9))


def test_pipeline_silent_sfx_default_reports_no_audio():
    script = tiny_script()
    script["scenes"][0]["audio"]["sfx"] = ["water"]
    result = FakeRenderer().render(script, output_path=None, sfx=SilentSfxSynthesizer())
    assert result.has_audio is False  # cue present but the default source is silent
