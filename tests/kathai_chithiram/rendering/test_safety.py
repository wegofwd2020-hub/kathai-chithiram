"""Tests for render-time seizure-safety + audio guards (KC-4)."""

from __future__ import annotations

import pytest

from kathai_chithiram.errors import RenderSafetyError
from kathai_chithiram.rendering import (
    RenderSafetyReport,
    guard_audio_levels,
    guard_flashes,
    guard_frame_rate,
    guard_render,
)

# --- frame rate ------------------------------------------------------------


@pytest.mark.parametrize("fps", [8, 24, 30])
def test_frame_rate_in_band_passes(fps: int) -> None:
    assert guard_frame_rate(fps) is None


@pytest.mark.parametrize("fps", [7, 31, 60])
def test_frame_rate_out_of_band_rejected(fps: int) -> None:
    with pytest.raises(RenderSafetyError) as exc:
        guard_frame_rate(fps)
    assert exc.value.rule == "render.frame_rate"


# --- flashing --------------------------------------------------------------


def test_steady_luminance_passes() -> None:
    assert guard_flashes([0.5] * 24, fps=24) is None


def test_slow_fade_passes() -> None:
    # A gradual fade: per-frame delta ~0.04 (< flash threshold) -> not a flash.
    frames = [i / 24 for i in range(25)]
    assert guard_flashes(frames, fps=24) is None


def test_fast_flicker_rejected_by_rate() -> None:
    # Alternating 0.4/0.6 every frame (delta 0.2): ~11 Hz of flashing.
    frames = [0.4 if i % 2 else 0.6 for i in range(24)]
    with pytest.raises(RenderSafetyError) as exc:
        guard_flashes(frames, fps=24)
    assert exc.value.rule == "render.flash_rate"


def test_short_high_contrast_strobe_rejected_even_when_rate_low() -> None:
    # Mostly steady (low clip-averaged rate), but a 4-frame black/white strobe
    # burst in the middle — the high-contrast run check must catch it.
    frames = [0.5] * 20 + [0.0, 1.0, 0.0, 1.0] + [0.5] * 24
    with pytest.raises(RenderSafetyError) as exc:
        guard_flashes(frames, fps=24)
    assert exc.value.rule == "render.high_contrast_oscillation"


def test_single_large_fade_is_not_a_strobe() -> None:
    # One big light->dark transition (a scene change), not an oscillation.
    frames = [1.0] * 12 + [0.0] * 12
    assert guard_flashes(frames, fps=24) is None


def test_empty_or_single_frame_passes() -> None:
    assert guard_flashes([], fps=24) is None
    assert guard_flashes([0.5], fps=24) is None


def test_non_positive_fps_rejected() -> None:
    with pytest.raises(ValueError, match="fps must be positive"):
        guard_flashes([0.1, 0.9], fps=0)


def test_out_of_range_luminance_rejected() -> None:
    with pytest.raises(ValueError, match="luminance"):
        guard_flashes([0.0, 1.5], fps=24)


# --- audio -----------------------------------------------------------------


def test_gentle_audio_passes() -> None:
    assert guard_audio_levels(0.7, [0.2, 0.4]) is None


def test_loud_narration_rejected() -> None:
    with pytest.raises(RenderSafetyError) as exc:
        guard_audio_levels(0.95, [])
    assert exc.value.rule == "render.audio_narration"


def test_loud_sfx_rejected() -> None:
    with pytest.raises(RenderSafetyError) as exc:
        guard_audio_levels(0.5, [0.2, 0.9])
    assert exc.value.rule == "render.audio_sfx"


# --- combined --------------------------------------------------------------


def test_guard_render_passes_safe_report() -> None:
    report = RenderSafetyReport(
        fps=24,
        luminances=[0.5, 0.52, 0.5, 0.48],
        narration_volume=0.7,
        sfx_levels=[0.3],
    )
    assert guard_render(report) is None


def test_guard_render_surfaces_first_failure() -> None:
    report = RenderSafetyReport(
        fps=60,  # fails first
        luminances=[0.5, 0.5],
        narration_volume=0.7,
    )
    with pytest.raises(RenderSafetyError) as exc:
        guard_render(report)
    assert exc.value.rule == "render.frame_rate"
