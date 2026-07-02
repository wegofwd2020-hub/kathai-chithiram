"""In-process narration audio, assembled from a scene plan (name stays local).

Narration text carries the child's DISPLAY NAME — reinserted at render time and
never stored or sent (KC-2) — and for the deterministic renderer child content
never leaves the process (ADR-026 D1). Speech synthesis therefore runs behind an
**in-process** :class:`NarrationSynthesizer` seam: samples in, samples out, no
network. This module turns a
:class:`~kathai_chithiram.rendering.pipeline.RenderPlan` into a single mono
:class:`NarrationTrack` timed to the video — each scene's narration placed in that
scene's window and scaled to its ``narration_volume`` — and measures the track's
true peak so the render-time audio guard checks the signal actually produced, not
a claimed number.

The default :class:`SilentNarrationSynthesizer` produces a correctly-timed silent
track (no bundled voice), so the timing, measurement, and WAV-serialization path
is real and tested; a concrete in-process voice (a local model) drops in behind
the same seam without touching callers. Everything here is stdlib-only (``wave`` +
``array``) so it stays in the core package, not the optional render extra.
"""

from __future__ import annotations

import io
import wave
from array import array
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from kathai_chithiram.rendering.safety import guard_audio_levels

if TYPE_CHECKING:
    from kathai_chithiram.rendering.pipeline import RenderPlan

__all__ = [
    "DEFAULT_SAMPLE_RATE",
    "NarrationSynthesizer",
    "NarrationTrack",
    "SilentNarrationSynthesizer",
    "VoiceCast",
    "build_narration_track",
    "guard_narration_track",
    "mono_wav_bytes",
]

#: Mono sample rate for narration tracks (Hz); 22.05 kHz is ample for speech.
DEFAULT_SAMPLE_RATE = 22050

_INT16_MAX = 32767


def _to_int16(sample: float) -> int:
    """Clamp ``sample`` to ``[-1, 1]`` and quantize to signed 16-bit PCM."""
    clamped = -1.0 if sample < -1.0 else 1.0 if sample > 1.0 else sample
    return int(round(clamped * _INT16_MAX))


def mono_wav_bytes(samples: Sequence[float], sample_rate: int) -> bytes:
    """Serialize mono float ``samples`` to a 16-bit PCM WAV (stdlib ``wave``).

    Shared by every in-process audio track (narration and the sfx bed) so the one
    quantization path — clamp to ``[-1, 1]``, quantize to signed 16-bit — is
    identical everywhere. No dependencies; the child's audio never leaves the
    process.

    Args:
        samples: Mono samples in ``[-1, 1]``, in play order.
        sample_rate: Samples per second (Hz); must be positive.

    Returns:
        The complete WAV file as bytes.

    Raises:
        ValueError: If ``sample_rate`` is not positive.
    """
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    pcm = array("h", (_to_int16(sample) for sample in samples))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


@runtime_checkable
class NarrationSynthesizer(Protocol):
    """An in-process text→samples voice (no network; the child's name stays local).

    A synthesizer turns one scene's narration into mono float samples in
    ``[-1, 1]`` at ``sample_rate``. It is given the scene's ``duration_s`` as the
    time budget; :func:`build_narration_track` fits the returned samples to that
    window (padding with silence or truncating), so a synthesizer need not produce
    exactly the budgeted number of samples.
    """

    def synthesize(self, text: str, *, sample_rate: int, duration_s: float) -> Sequence[float]:
        """Return mono samples in ``[-1, 1]`` for ``text`` (see the class docstring)."""
        ...


class SilentNarrationSynthesizer:
    """The default synthesizer: a correctly-timed silent track (no bundled voice).

    Produces silence of the requested duration, so the narration pipeline is fully
    exercised (timing, level measurement, WAV serialization) without shipping or
    invoking any speech model. A real in-process voice replaces it behind the same
    :class:`NarrationSynthesizer` seam.
    """

    def synthesize(self, text: str, *, sample_rate: int, duration_s: float) -> Sequence[float]:
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
class VoiceCast:
    """Narration voices keyed by character id, with a narrator fallback.

    A multi-voice narration draws each scene in the voice of that scene's foreground
    character (``PreparedScene.speaker_id``): a scene whose speaker has a mapped
    voice uses it, and any other scene uses the ``narrator``. This is the mechanism
    for per-character voices — a single-character story simply maps nothing and
    every scene uses the narrator.

    Args:
        narrator: The default voice for any character without a specific one.
        by_character: A mapping of character id → its voice.
    """

    narrator: NarrationSynthesizer
    by_character: Mapping[str, NarrationSynthesizer] = field(default_factory=dict)

    def voice_for(self, speaker_id: str) -> NarrationSynthesizer:
        """Return the voice for ``speaker_id`` (its own, else the narrator)."""
        return self.by_character.get(speaker_id, self.narrator)


@dataclass(frozen=True)
class NarrationTrack:
    """A mono narration track timed to a render plan.

    Args:
        sample_rate: Samples per second (Hz).
        samples: Mono samples in ``[-1, 1]``, in play order.
        peak: The track's peak absolute amplitude in ``[0, 1]`` (0.0 if silent).
    """

    sample_rate: int
    samples: Sequence[float]
    peak: float

    @property
    def duration_s(self) -> float:
        """Track duration in seconds (``len(samples) / sample_rate``)."""
        return len(self.samples) / self.sample_rate if self.sample_rate else 0.0

    @property
    def is_silent(self) -> bool:
        """Whether the track carries no signal (its peak amplitude is zero)."""
        return self.peak == 0.0

    def to_wav_bytes(self) -> bytes:
        """Serialize to a 16-bit mono PCM WAV (stdlib ``wave``; no dependencies).

        Samples are clamped to ``[-1, 1]`` and quantized to signed 16-bit PCM.

        Returns:
            The complete WAV file as bytes.
        """
        return mono_wav_bytes(self.samples, self.sample_rate)


def build_narration_track(
    plan: RenderPlan,
    voice: NarrationSynthesizer | VoiceCast | None = None,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> NarrationTrack:
    """Assemble a mono narration track for ``plan``, one scene at a time.

    Each scene's narration is synthesized in-process, fitted to that scene's
    duration window (padded with silence or truncated so audio and video stay in
    sync), scaled to the scene's ``narration_volume``, and concatenated in order.
    The track's peak amplitude is measured from the produced samples.

    Args:
        plan: The validated render plan; its scene durations define the timeline.
        voice: The narration voice. A single
            :class:`NarrationSynthesizer` narrates every scene; a :class:`VoiceCast`
            narrates each scene in its ``speaker_id``'s voice (per-character voices);
            ``None`` defaults to :class:`SilentNarrationSynthesizer`.
        sample_rate: Output sample rate in Hz.

    Returns:
        A :class:`NarrationTrack` whose duration matches the plan's total.

    Raises:
        ValueError: If ``sample_rate`` is not positive, or a synthesizer returns
            a sample outside ``[-1, 1]``.
    """
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    voice_for = _voice_selector(voice)

    samples = array("f")
    peak = 0.0
    for scene in plan.scenes:
        budget = _sample_count(scene.duration_s, sample_rate)
        raw = voice_for(scene.speaker_id).synthesize(
            scene.narration, sample_rate=sample_rate, duration_s=scene.duration_s
        )
        volume = scene.narration_volume
        raw_len = len(raw)
        for index in range(budget):
            value = raw[index] if index < raw_len else 0.0
            if not -1.0 <= value <= 1.0:
                raise ValueError("synthesizer returned a sample outside [-1, 1]")
            scaled = value * volume
            samples.append(scaled)
            magnitude = -scaled if scaled < 0 else scaled
            if magnitude > peak:
                peak = magnitude
    return NarrationTrack(sample_rate=sample_rate, samples=samples, peak=peak)


def guard_narration_track(track: NarrationTrack) -> None:
    """Reject a narration track whose level exceeds the gentle-audio cap.

    Reuses :func:`~kathai_chithiram.rendering.safety.guard_audio_levels` against the
    track's *measured* peak, so the render-time audio guarantee is checked on the
    signal actually produced (CONTENT_SAFETY.md §2), not a self-reported number.

    Args:
        track: The assembled narration track.

    Raises:
        RenderSafetyError: If the track's peak exceeds ``MAX_NARRATION_VOLUME``.
    """
    guard_audio_levels(track.peak, ())


def _voice_selector(
    voice: NarrationSynthesizer | VoiceCast | None,
) -> Callable[[str], NarrationSynthesizer]:
    """Return a ``speaker_id -> synthesizer`` selector for any voice form.

    A :class:`VoiceCast` selects per character; a single synthesizer is used for
    every scene; ``None`` yields a shared silent voice.
    """
    if isinstance(voice, VoiceCast):
        return voice.voice_for
    synth = voice if voice is not None else SilentNarrationSynthesizer()
    return lambda _speaker_id: synth


def _sample_count(duration_s: float, sample_rate: int) -> int:
    """Return the number of samples in ``duration_s`` seconds at ``sample_rate``."""
    return round(duration_s * sample_rate)
