"""Video generation via the shared ``wegofwd-video`` seam (ADR-026).

kathai is the **second consumer** of ``wegofwd-video``. Unlike pramana (which uses
the AI ``veo`` provider), kathai uses the ``deterministic-renderer`` provider: its
own matplotlib/blender :class:`~kathai_chithiram.rendering.pipeline.
SceneScriptRenderer` is wrapped as the caller-supplied render callable. The whole
pipeline runs **in-process with no external vendor** — the reason a *library*, not
a shared service, is the only fit for child content (ADR-026 D1).

What kathai gains from the seam: the shared provider **registry**, the
**capability** pre-check, and the cross-product **provenance** vocabulary — while
keeping its renderer, its scene-script contract, and its privacy guarantees. The
child's real name is reinserted only at render time (KC-2); it never reaches the
brief, the provenance stamp, or any stored JSON.
"""

from __future__ import annotations

from kathai_chithiram.video.adapter import make_render_fn, render_result_to_video_result
from kathai_chithiram.video.brief import build_video_brief
from kathai_chithiram.video.generate import StoryVideoResult, generate_story_video

__all__ = [
    "StoryVideoResult",
    "build_video_brief",
    "generate_story_video",
    "make_render_fn",
    "render_result_to_video_result",
]
