"""Tests for the wegofwd-video integration (ADR-026, kathai = second consumer).

Drives the ``deterministic-renderer`` path with the existing :class:`FakeRenderer`
and a real :class:`StoryArtifactStore` in a tmp dir — no AI vendor, no network.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from wegofwd_video.errors import VideoCapabilityError

from kathai_chithiram.storage.store import StoryArtifactStore
from kathai_chithiram.video import build_video_brief, generate_story_video
from kathai_chithiram.video.adapter import render_result_to_video_result

from tests.kathai_chithiram.rendering.fake_renderer import FakeRenderer
from tests.kathai_chithiram.scene_script.mock_scripts import valid_scene_script


def _long_script(n_scenes: int = 16, per_s: int = 8) -> dict:
    return {
        "scenes": [
            {"index": i + 1, "setting": "room", "narration": "CHILD waits.", "duration_s": per_s}
            for i in range(n_scenes)
        ]
    }


# ── build_video_brief ─────────────────────────────────────────────────────────
def test_brief_one_shot_per_scene_from_token_text():
    brief = build_video_brief(valid_scene_script())
    assert len(brief.shots) == 2
    assert brief.shots[0].scene_index == 1
    # token text flows through, NEVER a real name (privacy / KC-2)
    assert brief.shots[0].dialogue == "CHILD walks to the slide."
    assert "CHILD" in brief.shots[0].prompt
    assert brief.ingredients == ()  # deterministic renderer takes no reference images
    assert brief.global_style and brief.global_negative


# ── capability guard ──────────────────────────────────────────────────────────
def test_capability_guard_rejects_overlong_story():
    # 16 * 8s = 128s > deterministic-renderer max (120s) — rejected before render.
    renderer = FakeRenderer()
    store = _store_with_story(tmp=None)  # not reached; guard fires first
    with pytest.raises(VideoCapabilityError):
        generate_story_video(
            renderer=renderer, script=_long_script(), store=store, story_id="story1"
        )


# ── end-to-end (deterministic-renderer) ───────────────────────────────────────
def test_generate_story_video_renders_and_stamps_provenance(tmp_path):
    store = StoryArtifactStore(root=tmp_path)
    store.create_story(
        "story1", created_at=datetime(2026, 6, 30, tzinfo=timezone.utc), story_text="x"
    )
    renderer = FakeRenderer()

    out = generate_story_video(
        renderer=renderer, script=valid_scene_script(), store=store, story_id="story1", seed=7
    )

    # the media file was actually written under media/
    assert out.media_path.is_file()
    assert out.media_path.name == "story.mp4"
    assert out.result.provider_id == "deterministic-renderer"
    assert out.result.asset_uri == str(out.media_path)
    assert out.result.has_audio is False and out.result.c2pa_signed is False

    # provenance: shared stamp, honest, seed carried, model = renderer name
    p = out.provenance
    assert p["engine"] == "wegofwd-video"
    assert p["provider"] == "deterministic-renderer"
    assert p["model"] == "fake"
    assert p["model_verified"] is True
    assert p["seed"] == 7

    # provenance persisted as a non-sensitive cache artifact
    prov_file = store.story_dir("story1") / "cache" / "video_provenance.json"
    assert prov_file.is_file()
    assert json.loads(prov_file.read_text())["provider"] == "deterministic-renderer"


def test_adapter_rejects_missing_output(tmp_path):
    # output_path=None path: renderer produces no file → VideoResponseError surfaced.
    from wegofwd_video.errors import VideoResponseError

    renderer = FakeRenderer()
    result = renderer.render(valid_scene_script(), output_path=None)  # produces, no file
    with pytest.raises(VideoResponseError):
        render_result_to_video_result(result, model="fake")


def _store_with_story(tmp) -> StoryArtifactStore:
    # Helper for the capability test, which fails before touching storage.
    return StoryArtifactStore(root="/tmp/kc-unused")
