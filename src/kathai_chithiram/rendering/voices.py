"""A local, in-process narration voice backed by a command-line TTS engine.

Many good offline text-to-speech engines are command-line tools that write a WAV
(``espeak-ng``, ``piper``, ``flite``, ``pico2wave``). :class:`CliTtsSynthesizer`
drives any of them behind the ``NarrationSynthesizer`` seam: it runs the
operator-configured command on the local machine, reads back the WAV, and returns
float samples for ``build_narration_track``.

Because it runs a **local subprocess over local files**, the narration text — which
carries the child's display name — never leaves the machine (ADR-026 D1 / KC-2).
The engine and any voice model are chosen and installed by the operator (a vetted,
calm voice is a framing decision, not an engineering default); this class ships no
model and downloads nothing. When the configured command is absent it fails with a
clear, gated error rather than silently degrading.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
import wave
from array import array
from collections.abc import Sequence
from pathlib import Path

__all__ = ["CliTtsSynthesizer"]

_INT16_SCALE = 32768.0


class CliTtsSynthesizer:
    """Synthesize narration by running a local command-line TTS that emits a WAV.

    Args:
        command_template: The command to run, as an argv list, with the tokens
            ``"{out}"`` (replaced by the output WAV path) and ``"{text}"`` (replaced
            by the scene's narration) substituted. For example, espeak-ng:
            ``["espeak-ng", "-w", "{out}", "{text}"]``.

    The engine's native sample rate need not match the requested one — the WAV is
    linearly resampled to the requested rate so the track stays in sync with the
    video. Stereo output is downmixed to mono.
    """

    def __init__(self, command_template: Sequence[str]) -> None:
        if not command_template:
            raise ValueError("command_template must not be empty")
        if not any("{out}" in token for token in command_template):
            raise ValueError("command_template must contain a '{out}' token")
        self._template = tuple(command_template)

    def synthesize(self, text: str, *, sample_rate: int, duration_s: float) -> Sequence[float]:
        """Run the configured TTS on ``text`` and return mono samples at ``sample_rate``.

        Args:
            text: The scene's narration (already name-reinserted at render time).
            sample_rate: The rate the returned samples must be at (Hz).
            duration_s: The scene's time budget (informational; the builder fits the
                result to it).

        Returns:
            Mono float samples in ``[-1, 1]`` at ``sample_rate``.

        Raises:
            ValueError: If ``sample_rate`` is not positive.
            RuntimeError: If the TTS command is not installed, or it fails, or it
                produces no readable WAV.
        """
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        executable = shutil.which(self._template[0])
        if executable is None:
            raise RuntimeError(
                f"narration voice command '{self._template[0]}' not found on PATH; "
                "install the TTS engine or pass a different synthesizer"
            )

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "narration.wav"
            argv = [
                executable if token == self._template[0] else token
                for token in self._template
            ]
            argv = [token.replace("{out}", str(out_path)).replace("{text}", text) for token in argv]
            result = subprocess.run(argv, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                raise RuntimeError(
                    f"narration voice '{self._template[0]}' failed (exit {result.returncode})"
                )
            if not out_path.is_file():
                raise RuntimeError(
                    f"narration voice '{self._template[0]}' produced no WAV output"
                )
            source_rate, samples = _read_wav_mono(out_path.read_bytes())

        if source_rate != sample_rate:
            samples = _resample_linear(samples, source_rate, sample_rate)
        return samples


def _read_wav_mono(data: bytes) -> tuple[int, list[float]]:
    """Read a PCM WAV into (sample_rate, mono float samples in [-1, 1]).

    Raises:
        RuntimeError: If the WAV is not 16-bit PCM (the format CLI TTS engines emit).
    """
    with wave.open(io.BytesIO(data)) as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    if width != 2:
        raise RuntimeError(f"narration WAV must be 16-bit PCM, got sample width {width}")
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


def _resample_linear(samples: list[float], source_rate: int, target_rate: int) -> list[float]:
    """Linearly resample ``samples`` from ``source_rate`` to ``target_rate``.

    Adequate for narration at speech rates; keeps the module dependency-free.
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
