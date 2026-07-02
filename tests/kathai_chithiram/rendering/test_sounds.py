"""Tests for the local sound-bank sfx source.

Driven by tiny WAV files written into a temp directory, so the load, downmix,
resample, gentle-gain, safety, and cue-resolution paths are exercised without
shipping any sound assets.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest
from tests.kathai_chithiram.rendering.fake_renderer import tiny_script

from kathai_chithiram.rendering.pipeline import build_render_plan
from kathai_chithiram.rendering.sfx import build_sfx_bed
from kathai_chithiram.rendering.sounds import DEFAULT_SFX_GAIN, SoundBankSfxSynthesizer


def _write_wav(path: Path, *, rate: int = 22050, seconds: float = 0.5, amp: float = 0.9) -> None:
    """Write a mono 16-bit PCM sine WAV (a stand-in for a real sound file)."""
    count = int(rate * seconds)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(
            b"".join(
                struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * 220 * i / rate)))
                for i in range(count)
            )
        )


def _bank(tmp_path: Path, cues: dict[str, dict]) -> Path:
    """Create a sound-bank dir with a ``<cue>.wav`` per entry (kwargs → _write_wav)."""
    bank = tmp_path / "sounds"
    bank.mkdir()
    for cue, kwargs in cues.items():
        _write_wav(bank / f"{cue}.wav", **kwargs)
    return bank


# ── construction guards ─────────────────────────────────────────────────────────
def test_missing_directory_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="not a directory"):
        SoundBankSfxSynthesizer(tmp_path / "nope")


def test_bad_gain_rejected(tmp_path: Path):
    bank = _bank(tmp_path, {})
    with pytest.raises(ValueError, match="gain"):
        SoundBankSfxSynthesizer(bank, gain=0.0)
    with pytest.raises(ValueError, match="gain"):
        SoundBankSfxSynthesizer(bank, gain=1.5)


# ── loading a cue ─────────────────────────────────────────────────────────────
def test_loads_a_cue_and_scales_it_gently(tmp_path: Path):
    bank = _bank(tmp_path, {"water": {"amp": 0.9}})
    source = SoundBankSfxSynthesizer(bank)
    samples = source.synthesize("water", sample_rate=22050, duration_s=1.0)

    assert len(samples) > 0
    assert all(-1.0 <= s <= 1.0 for s in samples)
    peak = max(abs(s) for s in samples)
    assert 0.0 < peak <= DEFAULT_SFX_GAIN + 1e-6  # scaled under the gentle gain
    assert peak == pytest.approx(0.9 * DEFAULT_SFX_GAIN, abs=1e-2)


def test_resamples_to_requested_rate(tmp_path: Path):
    bank = _bank(tmp_path, {"bird": {"rate": 8000}})
    source = SoundBankSfxSynthesizer(bank)
    at_8k = len(source.synthesize("bird", sample_rate=8000, duration_s=1.0))
    at_22k = len(source.synthesize("bird", sample_rate=22050, duration_s=1.0))
    assert at_22k == pytest.approx(at_8k * 22050 / 8000, rel=0.01)


def test_custom_gain_scales_accordingly(tmp_path: Path):
    bank = _bank(tmp_path, {"water": {"amp": 1.0}})
    source = SoundBankSfxSynthesizer(bank, gain=0.25)
    samples = source.synthesize("water", sample_rate=22050, duration_s=1.0)
    assert max(abs(s) for s in samples) == pytest.approx(0.25, abs=1e-2)


# ── silence for absent / unsafe cues ───────────────────────────────────────────
def test_missing_cue_is_silence(tmp_path: Path):
    bank = _bank(tmp_path, {"water": {}})
    source = SoundBankSfxSynthesizer(bank)
    assert list(source.synthesize("thunder", sample_rate=22050, duration_s=1.0)) == []


@pytest.mark.parametrize("cue", ["../escape", "a/b", "..", "", "a\\b"])
def test_unsafe_cue_is_silence_not_traversal(tmp_path: Path, cue: str):
    # A file exists one level up; an unsafe cue must never reach it.
    (tmp_path / "escape.wav").write_bytes(b"not-a-wav")
    bank = _bank(tmp_path, {"water": {}})
    source = SoundBankSfxSynthesizer(bank)
    assert list(source.synthesize(cue, sample_rate=22050, duration_s=1.0)) == []


# ── error surfaces ─────────────────────────────────────────────────────────────
def test_non_positive_sample_rate_rejected(tmp_path: Path):
    bank = _bank(tmp_path, {"water": {}})
    source = SoundBankSfxSynthesizer(bank)
    with pytest.raises(ValueError, match="sample_rate"):
        source.synthesize("water", sample_rate=0, duration_s=1.0)


def test_non_pcm_wav_file_fails_clearly(tmp_path: Path):
    bank = tmp_path / "sounds"
    bank.mkdir()
    (bank / "broken.wav").write_bytes(b"RIFFnope not a real wav")
    source = SoundBankSfxSynthesizer(bank)
    with pytest.raises(wave.Error):  # a malformed WAV surfaces, not silent corruption
        source.synthesize("broken", sample_rate=22050, duration_s=1.0)


# ── end to end through the bed ─────────────────────────────────────────────────
def test_drives_the_sfx_bed(tmp_path: Path):
    bank = _bank(tmp_path, {"water": {"amp": 0.9}})
    script = tiny_script(duration_s=2)
    script["scenes"][0]["audio"]["sfx"] = ["water"]
    plan = build_render_plan(script)

    bed = build_sfx_bed(plan, SoundBankSfxSynthesizer(bank))
    assert not bed.is_silent
    assert bed.cue_peaks[0] == pytest.approx(0.9 * DEFAULT_SFX_GAIN, abs=1e-2)
    assert bed.cue_peaks[0] <= 0.5  # under the sfx safety cap, so the render passes
