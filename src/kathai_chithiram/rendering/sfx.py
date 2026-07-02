"""In-process sound effects, mixed into a bed timed to a scene plan (stays local).

A scene script may name **sound-effect cues** per scene (``audio.sfx`` — opaque
label strings like ``"water_running"``); the scene-script contract carries the
*cues*, not audio. This module turns those cues into a single mono
:class:`SfxBed` timed to the same clock as the narration track: each cue is
synthesized in-process, placed at its scene's start offset, fitted to the scene's
window, and mixed (overlapping cues sum, with the mix clamped to ``[-1, 1]``).

Like narration, synthesis runs behind an **in-process** :class:`SfxSynthesizer`
seam (samples in, samples out, no network), so anything a cue might reveal never
leaves the process (ADR-026 D1). Unlike narration, a cue carries **no author
volume** in the contract, so a cue plays at the synthesizer's native level: each
cue's *true measured peak* becomes its entry in the render-time
``sfx_levels`` and the shared audio guard rejects any cue over
:data:`~kathai_chithiram.rendering.safety.MAX_SFX_VOLUME` — the same
"measure the signal actually produced, then guard it" contract narration uses.

The default :class:`SilentSfxSynthesizer` maps every cue to silence (no bundled
sound assets), so the timing, measurement, mixing, and WAV path is real and
tested; a concrete in-process sound bank drops in behind the same seam without
touching callers. Everything here is stdlib-only, so it stays in the core package,
not the optional render extra.
"""

from __future__ import annotations

from array import array
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from kathai_chithiram.rendering.narration import DEFAULT_SAMPLE_RATE, mono_wav_bytes
from kathai_chithiram.rendering.safety import guard_audio_levels

if TYPE_CHECKING:
    from kathai_chithiram.rendering.pipeline import RenderPlan

__all__ = [
    "SfxBed",
    "SfxSynthesizer",
    "SilentSfxSynthesizer",
    "build_sfx_bed",
    "guard_sfx_bed",
]


@runtime_checkable
class SfxSynthesizer(Protocol):
    """An in-process cue→samples sound source (no network; stays local).

    A synthesizer turns one sound-effect cue into mono float samples in
    ``[-1, 1]`` at ``sample_rate``. It is given the scene's ``duration_s`` as the
    time budget; :func:`build_sfx_bed` fits the returned samples to that window
    (truncating anything longer), so a synthesizer need not fill the whole scene.
    A cue carries no author volume, so the synthesizer is responsible for a gentle
    level: a cue whose peak exceeds
    :data:`~kathai_chithiram.rendering.safety.MAX_SFX_VOLUME` is rejected by the
    render-time audio guard.
    """

    def synthesize(self, cue: str, *, sample_rate: int, duration_s: float) -> Sequence[float]:
        """Return mono samples in ``[-1, 1]`` for ``cue`` (see the class docstring)."""
        ...


class SilentSfxSynthesizer:
    """The default synthesizer: every cue maps to silence (no bundled sounds).

    Produces silence of the requested duration, so the sfx pipeline is fully
    exercised (timing, level measurement, mixing, WAV serialization) without
    shipping or invoking any sound bank. A real in-process sound source replaces
    it behind the same :class:`SfxSynthesizer` seam.
    """

    def synthesize(self, cue: str, *, sample_rate: int, duration_s: float) -> Sequence[float]:
        """Return ``round(duration_s * sample_rate)`` zero samples.

        Raises:
            ValueError: If ``sample_rate`` is not positive or ``duration_s`` is
                negative.
        """
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if duration_s < 0:
            raise ValueError("duration_s must be non-negative")
        return array("f", bytes(4 * _sample_count(duration_s, sample_rate)))


@dataclass(frozen=True)
class SfxBed:
    """A mono sound-effects bed timed to a render plan.

    Args:
        sample_rate: Samples per second (Hz).
        samples: Mono samples in ``[-1, 1]``, in play order (the mixed, clamped
            bed spanning the whole plan; silent where no cue plays).
        cue_peaks: The true peak amplitude in ``[0, 1]`` of each individual cue,
            in scene-then-cue order — the ``sfx_levels`` the render-time audio
            guard checks. Measured *before* mixing, so one cue's level is not
            masked by another that overlaps it.
        peak: The mixed bed's own peak absolute amplitude in ``[0, 1]``.
    """

    sample_rate: int
    samples: Sequence[float]
    cue_peaks: tuple[float, ...]
    peak: float

    @property
    def duration_s(self) -> float:
        """Bed duration in seconds (``len(samples) / sample_rate``)."""
        return len(self.samples) / self.sample_rate if self.sample_rate else 0.0

    @property
    def is_silent(self) -> bool:
        """Whether the bed carries no signal (its peak amplitude is zero)."""
        return self.peak == 0.0

    def to_wav_bytes(self) -> bytes:
        """Serialize the mixed bed to a 16-bit mono PCM WAV (shared serializer)."""
        return mono_wav_bytes(self.samples, self.sample_rate)


def build_sfx_bed(
    plan: RenderPlan,
    synthesizer: SfxSynthesizer | None = None,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> SfxBed:
    """Assemble a mono sfx bed for ``plan``, placing each scene's cues in its window.

    The bed shares the narration track's clock: its total length is the sum of the
    scenes' sample budgets (no title-card offset), so the bed and a narration track
    built from the same plan are sample-aligned and mix without resampling. Each
    scene's cues are synthesized in-process, truncated to the scene window, and
    summed into the bed; the mix is clamped to ``[-1, 1]`` so overlapping cues never
    clip. Each cue's *pre-mix* peak is recorded as its ``sfx_levels`` entry.

    Args:
        plan: The validated render plan; its scene durations define the timeline.
        synthesizer: The in-process sound source; defaults to
            :class:`SilentSfxSynthesizer` (a silent, correctly-timed bed).
        sample_rate: Output sample rate in Hz.

    Returns:
        An :class:`SfxBed` whose duration matches the plan's narration timeline.

    Raises:
        ValueError: If ``sample_rate`` is not positive, or the synthesizer returns
            a sample outside ``[-1, 1]``.
    """
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    synth = synthesizer if synthesizer is not None else SilentSfxSynthesizer()

    total = sum(_sample_count(scene.duration_s, sample_rate) for scene in plan.scenes)
    samples = array("f", bytes(4 * total))
    cue_peaks: list[float] = []

    offset = 0
    for scene in plan.scenes:
        budget = _sample_count(scene.duration_s, sample_rate)
        for cue in scene.sfx:
            raw = synth.synthesize(cue, sample_rate=sample_rate, duration_s=scene.duration_s)
            cue_peak = 0.0
            for index in range(min(len(raw), budget)):
                value = raw[index]
                if not -1.0 <= value <= 1.0:
                    raise ValueError("synthesizer returned a sample outside [-1, 1]")
                magnitude = -value if value < 0 else value
                if magnitude > cue_peak:
                    cue_peak = magnitude
                samples[offset + index] = _clamp(samples[offset + index] + value)
            cue_peaks.append(cue_peak)
        offset += budget

    peak = 0.0
    for value in samples:
        magnitude = -value if value < 0 else value
        if magnitude > peak:
            peak = magnitude
    return SfxBed(
        sample_rate=sample_rate, samples=samples, cue_peaks=tuple(cue_peaks), peak=peak
    )


def guard_sfx_bed(bed: SfxBed) -> None:
    """Reject an sfx bed whose any cue exceeds the gentle-audio cap.

    Reuses :func:`~kathai_chithiram.rendering.safety.guard_audio_levels` against the
    bed's *measured* per-cue peaks (with no narration component), so the render-time
    audio guarantee is checked on the signal actually produced (CONTENT_SAFETY.md
    §2), not a self-reported number.

    Args:
        bed: The assembled sfx bed.

    Raises:
        RenderSafetyError: If any cue's peak exceeds ``MAX_SFX_VOLUME``.
    """
    guard_audio_levels(0.0, bed.cue_peaks)


def _clamp(value: float) -> float:
    """Clamp a mixed sample to ``[-1, 1]`` so summed cues never clip."""
    return -1.0 if value < -1.0 else 1.0 if value > 1.0 else value


def _sample_count(duration_s: float, sample_rate: int) -> int:
    """Return the number of samples in ``duration_s`` seconds at ``sample_rate``."""
    return round(duration_s * sample_rate)
