"""Render-time seizure-safety and audio guards.

Each guard is a pure function over a simple numeric description of the rendered
output, so it is fully testable with mock data and independent of any concrete
renderer. The guards enforce ``docs/CONTENT_SAFETY.md`` §2/§3/§5:

* **Frame rate** within the predictable-pacing band (8–30 fps).
* **Flashing** — no more than ``MAX_FLASH_HZ`` (3 Hz) luminance flashes, the
  seizure-safety ceiling.
* **High-contrast oscillation** — repeated near-black↔near-white swings are
  held to the same rate ceiling even when individual flashes are large.
* **Audio levels** — narration and sound effects stay under gentle-audio caps.

Luminance is given as a per-frame sequence in ``[0, 1]`` together with the fps,
which is all that is needed to derive flash *rate* and swing *amplitude*.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from kathai_chithiram.errors import RenderSafetyError
from kathai_chithiram.scene_script.schema import MAX_FLASH_HZ

__all__ = [
    "MAX_NARRATION_VOLUME",
    "MAX_SFX_VOLUME",
    "RenderSafetyReport",
    "guard_audio_levels",
    "guard_flashes",
    "guard_frame_rate",
    "guard_render",
]

# Frame-rate band (mirrors the scene-script contract; predictable pacing).
_MIN_FPS = 8
_MAX_FPS = 30

# A luminance change of at least this much (on a 0–1 scale) counts as a flash
# transition; two opposing transitions make one flash cycle.
_FLASH_DELTA = 0.1

# A swing of at least this amplitude is "high-contrast" (e.g. a near-black↔
# near-white alternation). A run of this many consecutive alternating
# high-contrast swings is a strobe burst and is rejected regardless of the
# clip-averaged flash rate (a short burst in a long clip averages out, but is
# still dangerous).
_HIGH_CONTRAST_DELTA = 0.8
_HIGH_CONTRAST_MIN_RUN = 3

#: Gentle-audio caps on a 0–1 scale (CONTENT_SAFETY.md §2: even, quiet audio).
MAX_NARRATION_VOLUME = 0.8
MAX_SFX_VOLUME = 0.5


@dataclass(frozen=True)
class RenderSafetyReport:
    """A renderer's self-description, fed to :func:`guard_render`.

    Args:
        fps: Frames per second of the rendered output.
        luminances: Per-frame mean luminance in ``[0, 1]`` (frame order).
        narration_volume: Peak narration level in ``[0, 1]``.
        sfx_levels: Peak level of each sound effect in ``[0, 1]``.
    """

    fps: int
    luminances: Sequence[float]
    narration_volume: float
    sfx_levels: Sequence[float] = field(default_factory=tuple)


def guard_frame_rate(fps: int) -> None:
    """Reject a frame rate outside the predictable-pacing band.

    Args:
        fps: Frames per second.

    Raises:
        RenderSafetyError: If ``fps`` is outside ``[8, 30]``.
    """
    if fps < _MIN_FPS or fps > _MAX_FPS:
        raise RenderSafetyError(
            "render.frame_rate",
            f"fps {fps} outside allowed [{_MIN_FPS}, {_MAX_FPS}]",
        )


def guard_flashes(luminances: Sequence[float], fps: int) -> None:
    """Reject output that flashes too fast or contains a high-contrast strobe.

    Two distinct checks:

    * **Flash rate** — luminance swings ≥ ``_FLASH_DELTA`` averaged over the clip
      must not exceed ``MAX_FLASH_HZ``.
    * **High-contrast oscillation** — a run of ``_HIGH_CONTRAST_MIN_RUN``
      consecutive *alternating* swings ≥ ``_HIGH_CONTRAST_DELTA`` is a strobe
      burst and is rejected even when the clip-averaged rate looks fine.

    Args:
        luminances: Per-frame mean luminance in ``[0, 1]``.
        fps: Frames per second (must be positive).

    Raises:
        ValueError: If ``fps`` is not positive or a luminance is out of range.
        RenderSafetyError: If the flash rate or a high-contrast strobe burst is
            detected.
    """
    if fps <= 0:
        raise ValueError("fps must be positive to compute a flash rate")
    for value in luminances:
        if not 0.0 <= value <= 1.0:
            raise ValueError("luminance values must lie in [0, 1]")

    if len(luminances) < 2:
        return
    duration_s = len(luminances) / fps

    flash_hz = _flash_rate(luminances, _FLASH_DELTA, duration_s)
    if flash_hz > MAX_FLASH_HZ:
        raise RenderSafetyError(
            "render.flash_rate",
            f"flash rate {flash_hz:.2f} Hz exceeds {MAX_FLASH_HZ} Hz",
        )

    strobe_run = _max_alternating_run(luminances, _HIGH_CONTRAST_DELTA)
    if strobe_run >= _HIGH_CONTRAST_MIN_RUN:
        raise RenderSafetyError(
            "render.high_contrast_oscillation",
            f"high-contrast strobe burst of {strobe_run} swings "
            f"(limit {_HIGH_CONTRAST_MIN_RUN - 1})",
        )


def guard_audio_levels(narration_volume: float, sfx_levels: Sequence[float]) -> None:
    """Reject audio that exceeds the gentle-audio caps.

    Args:
        narration_volume: Peak narration level in ``[0, 1]``.
        sfx_levels: Peak level of each sound effect in ``[0, 1]``.

    Raises:
        RenderSafetyError: If narration or any sfx exceeds its cap.
    """
    if narration_volume > MAX_NARRATION_VOLUME:
        raise RenderSafetyError(
            "render.audio_narration",
            f"narration volume {narration_volume} exceeds cap {MAX_NARRATION_VOLUME}",
        )
    for index, level in enumerate(sfx_levels):
        if level > MAX_SFX_VOLUME:
            raise RenderSafetyError(
                "render.audio_sfx",
                f"sfx #{index} level {level} exceeds cap {MAX_SFX_VOLUME}",
            )


def guard_render(report: RenderSafetyReport) -> None:
    """Run every render-time guard over ``report``; return if all pass.

    Args:
        report: The renderer's self-description.

    Raises:
        RenderSafetyError: On the first guard that fails.
        ValueError: If inputs are malformed (e.g. non-positive fps).
    """
    guard_frame_rate(report.fps)
    guard_flashes(report.luminances, report.fps)
    guard_audio_levels(report.narration_volume, report.sfx_levels)


def _flash_rate(luminances: Sequence[float], delta: float, duration_s: float) -> float:
    """Return flashes per second for swings of at least ``delta``.

    A *transition* is a frame-to-frame luminance change of at least ``delta``;
    two opposing transitions make one flash cycle, so the rate is
    ``transitions / 2 / duration``.
    """
    transitions = 0
    for previous, current in zip(luminances, luminances[1:], strict=False):
        if abs(current - previous) >= delta:
            transitions += 1
    if duration_s <= 0:
        return 0.0
    return (transitions / 2) / duration_s


def _max_alternating_run(luminances: Sequence[float], amplitude: float) -> int:
    """Return the longest run of consecutive *alternating* swings ≥ ``amplitude``.

    A sub-threshold step breaks the run; two large swings in the same direction
    restart it (a strobe alternates dark↔light, it does not ramp one way).
    """
    best = 0
    run = 0
    previous_sign = 0
    for previous, current in zip(luminances, luminances[1:], strict=False):
        delta = current - previous
        if abs(delta) < amplitude:
            run = 0
            previous_sign = 0
            continue
        sign = 1 if delta > 0 else -1
        run = run + 1 if sign != previous_sign else 1
        previous_sign = sign
        best = max(best, run)
    return best
