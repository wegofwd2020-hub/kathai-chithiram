"""Build caption sidecars (SubRip ``.srt`` / WebVTT ``.vtt``) from a render plan.

The rendered animation already burns each scene's caption into the frame, but a
**sidecar** caption file is a separate accessibility artifact: it lets an external
player, screen reader, or assistive tool surface the same text, restyle it, or
read it aloud. This module derives the cues purely from a
:class:`~kathai_chithiram.rendering.pipeline.RenderPlan` — one cue per scene, on
the **scene timeline** (cue *i* spans scene *i*'s window, starting at t=0), which
is the same clock the narration track uses, so a sidecar and the narration stay in
sync.

The plan's captions already have the child's display name reinserted (KC-2), so a
sidecar built from a name-mapped plan carries the real name exactly like the
playable video does — it is therefore as sensitive as the video and belongs only
wherever the decrypted video is written, never in the stored scene script or logs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kathai_chithiram.rendering.pipeline import RenderPlan

__all__ = ["Cue", "build_captions", "to_srt", "to_vtt"]


@dataclass(frozen=True)
class Cue:
    """One caption cue on the scene timeline.

    Args:
        index: 1-based cue number (matches the scene index).
        start_s: Cue start time in seconds from the beginning of the scenes.
        end_s: Cue end time in seconds.
        text: The caption text (display name already reinserted).
    """

    index: int
    start_s: float
    end_s: float
    text: str


def build_captions(plan: RenderPlan) -> list[Cue]:
    """Return one :class:`Cue` per scene, back-to-back on the scene timeline.

    Args:
        plan: The validated render plan; scene durations define the cue windows and
            each scene's ``caption`` is the cue text.

    Returns:
        The cues in play order (empty if the plan has no scenes).
    """
    cues: list[Cue] = []
    start = 0.0
    for index, scene in enumerate(plan.scenes, start=1):
        end = start + scene.duration_s
        cues.append(Cue(index=index, start_s=start, end_s=end, text=scene.caption))
        start = end
    return cues


def to_srt(cues: Sequence[Cue]) -> str:
    """Serialize ``cues`` to a SubRip (``.srt``) document.

    Args:
        cues: The caption cues, in play order.

    Returns:
        The ``.srt`` text (trailing newline; empty string for no cues).
    """
    if not cues:
        return ""
    blocks = [
        f"{cue.index}\n{_timestamp(cue.start_s, ',')} --> {_timestamp(cue.end_s, ',')}\n{cue.text}"
        for cue in cues
    ]
    return "\n\n".join(blocks) + "\n"


def to_vtt(cues: Sequence[Cue]) -> str:
    """Serialize ``cues`` to a WebVTT (``.vtt``) document.

    Args:
        cues: The caption cues, in play order.

    Returns:
        The ``.vtt`` text, always led by the ``WEBVTT`` header.
    """
    header = "WEBVTT\n"
    if not cues:
        return header
    blocks = [
        f"{_timestamp(cue.start_s, '.')} --> {_timestamp(cue.end_s, '.')}\n{cue.text}"
        for cue in cues
    ]
    return header + "\n" + "\n\n".join(blocks) + "\n"


def _timestamp(seconds: float, millis_sep: str) -> str:
    """Format ``seconds`` as ``HH:MM:SS<sep>mmm`` (``,`` for SRT, ``.`` for VTT).

    Raises:
        ValueError: If ``seconds`` is negative.
    """
    if seconds < 0:
        raise ValueError("caption timestamp cannot be negative")
    total_ms = round(seconds * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{millis_sep}{millis:03d}"
