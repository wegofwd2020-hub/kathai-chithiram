"""Describe a scene script as a ``wegofwd_video.VideoBrief``.

The brief is the **portable, shared** description of the video (the cross-product
vocabulary used for the registry capability check and provenance). For the
``deterministic-renderer`` path it is *descriptive only* — kathai's renderer
consumes the native ``scene_script`` directly. (For an AI provider like Veo the
brief would be the actual generation input.)

PRIVACY: the brief is built from the script's **token** text (e.g. ``CHILD``),
never a real name. The child's display name is reinserted only at render time by
the renderer (KC-2); it never reaches this brief or anything derived from it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from wegofwd_video import Shot, VideoBrief

# kathai social-story house style — calm, captioned, gentle. Deliberately
# conservative; mirrors the constraints in generation/system_prompt.py.
_STYLE = "warm 2D storybook, soft flat color, rounded shapes, calm"
_NEGATIVE = "no flashing, no fast cuts, no on-screen text, no scary imagery, no photorealism"
_AUDIO = "gentle narrator, slow pace, soft room tone, no music"


def build_video_brief(script: Mapping[str, Any]) -> VideoBrief:
    """Project a scene script onto a :class:`wegofwd_video.VideoBrief`.

    One shot per scene, in order: the scene's ``narration`` (token text) is the
    spoken line and seeds a neutral visual ``prompt`` from the ``setting``. No
    reference images — the deterministic renderer accepts none.

    Args:
        script: A scene-script document (the same shape the renderer consumes).

    Returns:
        A brief whose shots mirror the script's scenes, built from token text.
    """
    scenes: Sequence[Mapping[str, Any]] = script["scenes"]
    shots = tuple(
        Shot(
            scene_index=int(scene["index"]),
            prompt=f"{scene['setting']}: {scene['narration']}",
            shot_type="medium",
            camera_move="static",
            dialogue=scene["narration"],
            duration_s=float(scene["duration_s"]),
        )
        for scene in scenes
    )
    return VideoBrief(
        global_style=_STYLE,
        global_negative=_NEGATIVE,
        audio_direction=_AUDIO,
        ingredients=(),
        shots=shots,
    )
