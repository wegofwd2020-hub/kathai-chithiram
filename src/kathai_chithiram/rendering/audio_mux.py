"""Mux a narration track into a rendered mp4, in-process (local ffmpeg; no network).

The deterministic renderer draws silent frames; when a narration track is present,
this replaces the mp4 with a copy that carries the track as an AAC audio stream. It
shells out to the ffmpeg binary bundled by ``imageio-ffmpeg`` (the same one the
video encode uses) — a local process over local files — so the narration audio,
which carries the child's display name, never leaves the machine (ADR-026 D1).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

__all__ = ["mux_wav_into_mp4"]


def _ffmpeg_exe() -> str:
    """Return the path to the bundled ffmpeg binary.

    Raises:
        RuntimeError: If ``imageio-ffmpeg`` (the render extra) is not installed.
    """
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError(
            "muxing narration audio requires imageio-ffmpeg; install the render "
            "extra (pip install 'kathai-chithiram[render]')"
        ) from exc
    return str(imageio_ffmpeg.get_ffmpeg_exe())


def mux_wav_into_mp4(video_path: str, wav_bytes: bytes) -> None:
    """Replace ``video_path`` in place with a copy carrying ``wav_bytes`` as audio.

    The video stream is stream-copied (not re-encoded) and the audio is encoded to
    AAC; the output is truncated to the shorter of the two (``-shortest``) so a
    small timing mismatch never leaves a trailing silent tail. The muxed file is
    written next to ``video_path`` (same directory, hence same filesystem) and then
    atomically moved over it.

    Args:
        video_path: Path to the rendered mp4 to add audio to (replaced in place).
        wav_bytes: A mono PCM WAV, e.g. from
            :meth:`~kathai_chithiram.rendering.narration.NarrationTrack.to_wav_bytes`.

    Raises:
        RuntimeError: If ffmpeg is unavailable or the mux fails; no partial output
            is left behind in that case.
    """
    exe = _ffmpeg_exe()
    video = Path(video_path)
    muxed = video.with_name(f"{video.stem}.muxed{video.suffix}")
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "narration.wav"
        audio.write_bytes(wav_bytes)
        result = subprocess.run(
            [
                exe, "-y",
                "-i", str(video),
                "-i", str(audio),
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                str(muxed),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0 or not muxed.is_file():
        if muxed.exists():
            muxed.unlink()
        # ffmpeg's stderr describes codecs and temp paths only — no story content.
        raise RuntimeError(f"ffmpeg audio mux failed (exit {result.returncode})")
    os.replace(str(muxed), str(video))
