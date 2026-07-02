"""Render a story's video through the shared ``wegofwd-video`` seam.

Orchestrates the ``deterministic-renderer`` path end to end: build the brief from
the scene script, capability-check it, render via kathai's
:class:`SceneScriptRenderer` (wrapped as the provider's render_fn), and stamp the
shared provenance record. Everything runs **in-process** — no vendor, no network —
so the no-training / zero-retention dispatch gates that guard kathai's LLM path
(:mod:`kathai_chithiram.wegofwd_llm.gateway`) do not apply here: child content
never leaves the process (ADR-026 D1).

The rendered media is persisted **through the store** (``add_media``), so it is
sealed with the store's cipher and encrypted at rest (KC-5) exactly like every
other artifact — the renderer's raw output only ever lives in a private temp file.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from wegofwd_video import (
    VideoRequest,
    VideoResult,
    assert_brief_within_capabilities,
    build_provider,
    provenance,
)

from kathai_chithiram.privacy.pseudonymize import NameMapping
from kathai_chithiram.rendering.narration import NarrationSynthesizer
from kathai_chithiram.rendering.pipeline import SceneScriptRenderer
from kathai_chithiram.storage.protocol import StoryStore
from kathai_chithiram.video.adapter import make_render_fn
from kathai_chithiram.video.brief import build_video_brief

_PROVIDER_ID = "deterministic-renderer"
_RESOLUTION = "1080p"
_ASPECT_RATIO = "16:9"
_MEDIA_FILENAME = "story.mp4"
_PROVENANCE_FILE = "video_provenance.json"


@dataclass(frozen=True)
class StoryVideoResult:
    """The outcome of generating a story's video through the seam.

    Args:
        result: The ``wegofwd_video.VideoResult`` (``asset_uri`` = the media path).
        provenance: The shared stamp (provider, model, seed, contract versions).
        media_path: Where the rendered animation was written.
    """

    result: VideoResult
    provenance: dict[str, Any]
    media_path: Path


def generate_story_video(
    *,
    renderer: SceneScriptRenderer,
    script: Mapping[str, Any],
    store: StoryStore,
    story_id: str,
    mapping: NameMapping | None = None,
    narration: NarrationSynthesizer | None = None,
    seed: int | None = None,
    model: str | None = None,
    filename: str = _MEDIA_FILENAME,
) -> StoryVideoResult:
    """Render ``script`` for ``story_id`` and return the result + provenance.

    ``model`` defaults to the renderer's name (recorded in provenance so a stored
    video traces back to which renderer produced it). ``mapping`` reinserts the
    child's real name at render time only; it never reaches the brief or the
    persisted provenance.

    Args:
        renderer: The kathai renderer to drive.
        script: The scene-script document.
        store: The artifact store the story lives in.
        story_id: Opaque story id (the media + provenance land under it).
        mapping: Optional name mapping for render-time name reinsertion.
        narration: Optional in-process voice; when given, its narration track is
            muxed into the media (in-process, so the child's name stays local).
        seed: Optional reproducibility seed, recorded in provenance.
        model: Override the recorded model id (defaults to ``renderer.name``).
        filename: Output media file name under ``media/``.

    Returns:
        A :class:`StoryVideoResult`.

    Raises:
        wegofwd_video.VideoCapabilityError: The brief exceeds the renderer's limits.
        SceneScriptInvalidError: The script fails contract/safety validation.
        RenderSafetyError: The produced output trips a render-time guard.
        StoryNotFoundError: ``story_id`` is not in the store.
    """
    model_id = model or renderer.name
    brief = build_video_brief(script)
    duration_s = sum(shot.duration_s for shot in brief.shots)
    assert_brief_within_capabilities(
        _PROVIDER_ID,
        resolution=_RESOLUTION,
        aspect=_ASPECT_RATIO,
        duration_s=duration_s,
        ingredients=len(brief.ingredients),
    )

    # Render to a private temp file first, then persist the bytes *through the
    # store* (``add_media``) so the video is encrypted at rest (KC-5) and readable
    # via ``read_media``. Writing the renderer's output straight into ``media/``
    # would bypass the store cipher — leaving child content in plaintext on disk
    # and unreadable once a cipher is configured. The ``.mp4`` suffix is kept so
    # the encoder still infers the container from the extension.
    with tempfile.TemporaryDirectory() as tmp:
        render_target = str(Path(tmp) / filename)
        render_fn = make_render_fn(
            renderer,
            script,
            output_path=render_target,
            model=model_id,
            mapping=mapping,
            narration=narration,
        )
        provider = build_provider(_PROVIDER_ID, render_fn=render_fn, model=model_id)
        result = provider.generate(
            VideoRequest(
                brief=brief,
                resolution=_RESOLUTION,
                aspect_ratio=_ASPECT_RATIO,
                target_duration_s=duration_s,
                seed=seed,
            )
        )
        media_bytes = Path(render_target).read_bytes()

    media_path = store.add_media(story_id, filename, media_bytes)
    # The renderer wrote to the temp path; the durable artifact is the sealed
    # store file, so the result must advertise the stored location, not the temp.
    result = replace(result, asset_uri=str(media_path))

    prov = provenance(_PROVIDER_ID, model_id, seed=seed)
    # Provenance is non-sensitive (provider/model/seed/versions — no story text or
    # name), so it is safe to persist as a derived cache artifact alongside the media.
    store.add_cache(story_id, _PROVENANCE_FILE, json.dumps(prov, indent=2).encode("utf-8"))
    return StoryVideoResult(result=result, provenance=prov, media_path=media_path)
