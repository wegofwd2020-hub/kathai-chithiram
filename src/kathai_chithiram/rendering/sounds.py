"""A local, in-process sfx source backed by a directory of sound files.

A scene's sound-effect cues are opaque labels (``"water_running"``,
``"bird"``); :class:`SoundBankSfxSynthesizer` resolves each label to a WAV file
in an operator-provided directory (``<dir>/<cue>.wav``), reads it back, downmixes
to mono, resamples to the track's rate, and scales it to a gentle level. It runs
entirely over **local files** — no network, nothing leaves the machine (ADR-026
D1) — and ships **no sounds**: the sound bank is curated and installed by the
operator (which effects are calm and appropriate is a framing decision, not an
engineering default), exactly as the narration voice engine is.

A cue with no matching file — or an unsafe label that would escape the directory —
maps to **silence** rather than an error, so an incomplete bank degrades one cue
to quiet instead of failing the whole render. Because a cue carries no author
volume, the source applies its own gentle :data:`DEFAULT_SFX_GAIN`; the render-time
audio guard still measures the true peak and rejects anything over the sfx cap, so
raising the gain past the cap fails closed rather than playing too loud.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from kathai_chithiram.rendering.wav_io import read_wav_mono, resample_linear

__all__ = ["DEFAULT_SFX_GAIN", "SoundBankSfxSynthesizer"]

#: Default level a bank sound is scaled to (peak headroom under the sfx safety cap
#: of 0.5, so a full-scale source file stays gentle by construction).
DEFAULT_SFX_GAIN = 0.4


class SoundBankSfxSynthesizer:
    """Synthesize sfx by loading ``<directory>/<cue>.wav`` and scaling it gently.

    Args:
        directory: The sound-bank directory holding one ``<cue>.wav`` per cue.
        gain: The level each loaded sound is scaled by, in ``(0, 1]`` (defaults to
            :data:`DEFAULT_SFX_GAIN`). A gentle gain keeps effects calm; the
            render-time guard still rejects any cue whose measured peak exceeds the
            sfx cap.

    Raises:
        ValueError: If ``directory`` is not an existing directory, or ``gain`` is
            not in ``(0, 1]``.
    """

    def __init__(
        self, directory: str | os.PathLike[str], *, gain: float = DEFAULT_SFX_GAIN
    ) -> None:
        path = Path(directory)
        if not path.is_dir():
            raise ValueError(f"sfx sound bank '{directory}' is not a directory")
        if not 0.0 < gain <= 1.0:
            raise ValueError("gain must be in (0, 1]")
        self._dir = path
        self._gain = gain

    def synthesize(self, cue: str, *, sample_rate: int, duration_s: float) -> Sequence[float]:
        """Load ``cue``'s sound and return gentle mono samples at ``sample_rate``.

        Args:
            cue: The scene's sound-effect cue label.
            sample_rate: The rate the returned samples must be at (Hz).
            duration_s: The scene's time budget (informational; the builder fits the
                result to it and truncates anything longer).

        Returns:
            Mono float samples in ``[-1, 1]`` at ``sample_rate``, or an empty
            sequence (silence) when the cue has no safe, existing sound file.

        Raises:
            ValueError: If ``sample_rate`` is not positive.
            RuntimeError: If a matching file exists but is not a readable 16-bit
                PCM WAV.
        """
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        path = self._resolve(cue)
        if path is None:
            return []
        source_rate, samples = read_wav_mono(path.read_bytes())
        if source_rate != sample_rate:
            samples = resample_linear(samples, source_rate, sample_rate)
        return [_clamp(sample * self._gain) for sample in samples]

    def _resolve(self, cue: str) -> Path | None:
        """Return the cue's sound file, or ``None`` if unsafe or absent.

        A cue must be a bare file stem: labels containing a path separator, ``..``,
        or that resolve outside the bank are rejected (mapped to silence) so a cue
        can never read a file outside the operator's directory.
        """
        if not cue or cue in (".", "..") or "/" in cue or "\\" in cue or os.sep in cue:
            return None
        candidate = self._dir / f"{cue}.wav"
        try:
            resolved = candidate.resolve()
        except OSError:
            return None
        if self._dir.resolve() not in resolved.parents:
            return None
        return candidate if candidate.is_file() else None


def _clamp(value: float) -> float:
    """Clamp a sample to ``[-1, 1]``."""
    return -1.0 if value < -1.0 else 1.0 if value > 1.0 else value
