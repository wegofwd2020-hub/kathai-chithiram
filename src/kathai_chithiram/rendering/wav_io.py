"""Shared, dependency-free reading of PCM WAV into mono float samples.

Both concrete in-process audio sources — the command-line TTS narration voice
(:mod:`kathai_chithiram.rendering.voices`) and the sound-bank sfx source
(:mod:`kathai_chithiram.rendering.sounds`) — take audio from an external WAV
(the TTS engine's output, or a sound file on disk) and need the same three
steps: decode 16-bit PCM, downmix to mono, and linearly resample to the track's
rate. This module is that one shared path, stdlib-only (``wave`` + ``array``), so
neither source carries its own copy.
"""

from __future__ import annotations

import io
import wave
from array import array

__all__ = ["read_wav_mono", "resample_linear"]

_INT16_SCALE = 32768.0


def read_wav_mono(data: bytes) -> tuple[int, list[float]]:
    """Read a PCM WAV into ``(sample_rate, mono float samples in [-1, 1])``.

    Stereo/multi-channel audio is downmixed to mono by averaging each frame.

    Args:
        data: The complete WAV file as bytes.

    Returns:
        The source sample rate (Hz) and the mono samples in ``[-1, 1]``.

    Raises:
        RuntimeError: If the WAV is not 16-bit PCM (the format the supported CLI
            TTS engines and typical sound files emit).
    """
    with wave.open(io.BytesIO(data)) as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    if width != 2:
        raise RuntimeError(f"WAV must be 16-bit PCM, got sample width {width}")
    pcm = array("h")
    pcm.frombytes(frames)
    if channels <= 1:
        return rate, [sample / _INT16_SCALE for sample in pcm]
    # Downmix interleaved channels to mono by averaging each frame.
    mono = [
        sum(pcm[base : base + channels]) / (channels * _INT16_SCALE)
        for base in range(0, len(pcm) - channels + 1, channels)
    ]
    return rate, mono


def resample_linear(samples: list[float], source_rate: int, target_rate: int) -> list[float]:
    """Linearly resample ``samples`` from ``source_rate`` to ``target_rate``.

    Adequate for speech and short sound effects; keeps the caller dependency-free.

    Args:
        samples: Mono samples at ``source_rate``.
        source_rate: The samples' current rate (Hz).
        target_rate: The rate to resample to (Hz).

    Returns:
        The resampled mono samples (unchanged when the rates already match).
    """
    if not samples or source_rate == target_rate:
        return samples
    target_count = round(len(samples) * target_rate / source_rate)
    if target_count <= 1:
        return samples[:target_count]
    ratio = (len(samples) - 1) / (target_count - 1)
    resampled: list[float] = []
    for index in range(target_count):
        position = index * ratio
        left = int(position)
        frac = position - left
        right = min(left + 1, len(samples) - 1)
        resampled.append(samples[left] * (1.0 - frac) + samples[right] * frac)
    return resampled
