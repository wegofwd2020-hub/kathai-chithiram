"""Tests for the command-line TTS narration voice.

Driven by a *stub* TTS command (a tiny script that writes a WAV) so the readback,
downmix, resample, and error paths are fully exercised without depending on any
specific engine (espeak-ng / piper) being installed.
"""

from __future__ import annotations

import struct
import sys
import wave
from pathlib import Path

import pytest
from tests.kathai_chithiram.scene_script.mock_scripts import valid_scene_script

from kathai_chithiram.rendering.narration import build_narration_track
from kathai_chithiram.rendering.pipeline import build_render_plan
from kathai_chithiram.rendering.voices import CliTtsSynthesizer, _read_wav_mono, _resample_linear

_STUB = """\
import sys, wave, struct, math
out, text = sys.argv[1], sys.argv[2]
rate, dur = {rate}, 0.5
n = int(dur * rate)
with wave.open(out, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes(b"".join(
        struct.pack("<h", int(0.5 * 32767 * math.sin(2 * math.pi * 150 * i / rate)))
        for i in range(n)))
"""


def _stub_voice(tmp_path: Path, *, rate: int = 22050) -> CliTtsSynthesizer:
    stub = tmp_path / "stub_tts.py"
    stub.write_text(_STUB.format(rate=rate), encoding="utf-8")
    return CliTtsSynthesizer([sys.executable, str(stub), "{out}", "{text}"])


# ── construction guards ───────────────────────────────────────────────────────
def test_empty_template_rejected():
    with pytest.raises(ValueError, match="must not be empty"):
        CliTtsSynthesizer([])


def test_template_without_out_token_rejected():
    with pytest.raises(ValueError, match=r"\{out\}"):
        CliTtsSynthesizer(["espeak-ng", "{text}"])


# ── running the (stub) engine ─────────────────────────────────────────────────
def test_stub_voice_returns_samples_in_range(tmp_path: Path):
    voice = _stub_voice(tmp_path)
    samples = voice.synthesize("Silas smiles.", sample_rate=22050, duration_s=1.0)
    assert len(samples) > 0
    assert all(-1.0 <= s <= 1.0 for s in samples)
    assert max(abs(s) for s in samples) > 0.1  # genuinely audible, not silence


def test_stub_voice_resamples_to_requested_rate(tmp_path: Path):
    # Stub emits 16 kHz; asking for 22.05 kHz must stretch the sample count.
    voice = _stub_voice(tmp_path, rate=16000)
    at_16k = len(voice.synthesize("hi", sample_rate=16000, duration_s=1.0))
    at_22k = len(voice.synthesize("hi", sample_rate=22050, duration_s=1.0))
    assert at_22k == pytest.approx(at_16k * 22050 / 16000, rel=0.01)


def test_missing_command_fails_clearly():
    voice = CliTtsSynthesizer(["kc-no-such-tts-binary", "-w", "{out}", "{text}"])
    with pytest.raises(RuntimeError, match="not found on PATH"):
        voice.synthesize("hi", sample_rate=22050, duration_s=1.0)


def test_failing_command_fails_clearly(tmp_path: Path):
    # A command that runs but writes no WAV (exits 0, no output) -> clear error.
    stub = tmp_path / "noop.py"
    stub.write_text("import sys\n", encoding="utf-8")
    voice = CliTtsSynthesizer([sys.executable, str(stub), "{out}", "{text}"])
    with pytest.raises(RuntimeError, match="produced no WAV"):
        voice.synthesize("hi", sample_rate=22050, duration_s=1.0)


def test_non_positive_sample_rate_rejected(tmp_path: Path):
    voice = _stub_voice(tmp_path)
    with pytest.raises(ValueError, match="sample_rate"):
        voice.synthesize("hi", sample_rate=0, duration_s=1.0)


def test_voice_drives_the_narration_track(tmp_path: Path):
    plan = build_render_plan(valid_scene_script())
    track = build_narration_track(plan, _stub_voice(tmp_path))
    assert not track.is_silent
    assert len(track.samples) == sum(round(s.duration_s * track.sample_rate) for s in plan.scenes)


# ── helpers: downmix + resample ───────────────────────────────────────────────
def test_read_wav_mono_downmixes_stereo():
    # Left = +full, right = -full; the average is ~0 per frame.
    import io

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<hh", 30000, -30000) for _ in range(10)))
    rate, mono = _read_wav_mono(buffer.getvalue())
    assert rate == 8000
    assert len(mono) == 10
    assert all(abs(s) < 0.01 for s in mono)


def test_resample_linear_endpoints_preserved():
    up = _resample_linear([0.0, 1.0], 1, 4)
    assert up[0] == pytest.approx(0.0)
    assert up[-1] == pytest.approx(1.0)
    assert len(up) == 8
