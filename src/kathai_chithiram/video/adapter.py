"""Adapt kathai's :class:`SceneScriptRenderer` to a ``wegofwd_video`` render_fn.

The ``deterministic-renderer`` provider is constructed with a caller-supplied
``render_fn(VideoRequest) -> VideoResult`` (ADR-026 D4). kathai's renderer instead
consumes the native ``scene_script`` (with its validation, name-reinsertion, and
safety guards), so the render_fn closes over ``(script, mapping, output_path)`` and
ignores the request's brief — the brief is the portable description, the script is
what the renderer draws.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from wegofwd_video import VideoRequest, VideoResult
from wegofwd_video.errors import VideoResponseError

from kathai_chithiram.privacy.pseudonymize import NameMapping
from kathai_chithiram.rendering.narration import NarrationSynthesizer, VoiceCast
from kathai_chithiram.rendering.pipeline import RenderResult, SceneScriptRenderer
from kathai_chithiram.rendering.sfx import SfxSynthesizer

# The deterministic renderer is frame-based and not AI-generated, so it carries no
# C2PA/SynthID provenance signature. Audio is present only when an in-process
# narration voice is supplied (``has_audio`` reflects the actual output).
_RESOLUTION = "1080p"


def render_result_to_video_result(result: RenderResult, *, model: str) -> VideoResult:
    """Map a kathai :class:`RenderResult` onto a ``wegofwd_video.VideoResult``.

    The asset is a **local file** the renderer already wrote (``output_path``);
    kathai owns storage (ADR-026 D2), so the result carries the path as
    ``asset_uri`` rather than bytes.

    Raises:
        VideoResponseError: The renderer produced no output file.
    """
    if result.output_path is None:
        raise VideoResponseError("renderer produced no output file")
    duration_s = sum(scene.duration_s for scene in result.plan.scenes)
    return VideoResult(
        provider_id="deterministic-renderer",
        model=model,
        asset_uri=result.output_path,
        duration_s=duration_s,
        resolution=_RESOLUTION,
        has_audio=result.has_audio,
        c2pa_signed=False,
        raw=result.safety_report,
    )


def make_render_fn(
    renderer: SceneScriptRenderer,
    script: Mapping[str, Any],
    *,
    output_path: str,
    model: str,
    mapping: NameMapping | None = None,
    narration: NarrationSynthesizer | VoiceCast | None = None,
    sfx: SfxSynthesizer | None = None,
) -> Callable[[VideoRequest], VideoResult]:
    """Return a ``wegofwd_video`` render_fn that drives ``renderer``.

    ``mapping`` is what reinserts the child's real name at render time (KC-2); it
    is deliberately confined to the renderer and never reaches the brief.
    ``narration`` is an optional in-process voice and ``sfx`` an optional in-process
    sound source; both stay local to the renderer and never reach the brief.
    """

    def _render_fn(_request: VideoRequest) -> VideoResult:
        result = renderer.render(
            script,
            mapping=mapping,
            output_path=output_path,
            narration=narration,
            sfx=sfx,
        )
        return render_result_to_video_result(result, model=model)

    return _render_fn
