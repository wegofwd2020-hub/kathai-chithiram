"""Tests for the wegofwd-video integration (ADR-026, kathai = second consumer).

Drives the ``deterministic-renderer`` path with the existing :class:`FakeRenderer`
and a real :class:`StoryArtifactStore` in a tmp dir — no AI vendor, no network.
The seam persists media *through the store*, so at-rest encryption (KC-5) is
exercised here too: a story rendered under a cipher must be sealed on disk and
still decode back through ``read_media``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from tests.kathai_chithiram.rendering.fake_renderer import FakeRenderer
from tests.kathai_chithiram.scene_script.mock_scripts import valid_scene_script
from wegofwd_video.errors import VideoCapabilityError

from kathai_chithiram.storage.crypto import AesGcmCipher, generate_data_key
from kathai_chithiram.storage.store import StoryArtifactStore
from kathai_chithiram.video import build_video_brief, generate_story_video
from kathai_chithiram.video.adapter import render_result_to_video_result


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


# ── at-rest encryption through the seam (KC-5 regression) ─────────────────────
def test_seam_stores_media_encrypted_at_rest_and_read_media_round_trips(tmp_path):
    # Regression: the seam must persist media THROUGH the store so it is sealed
    # with the store cipher (KC-5) — not written raw into media/. A raw write
    # would leave child content in plaintext on disk and, worse, be undecryptable
    # by read_media once a cipher is configured.
    store = StoryArtifactStore(root=tmp_path, cipher=AesGcmCipher(generate_data_key()))
    store.create_story(
        "story1", created_at=datetime(2026, 7, 2, tzinfo=timezone.utc), story_text="x"
    )

    out = generate_story_video(
        renderer=FakeRenderer(), script=valid_scene_script(), store=store, story_id="story1"
    )

    media_file = tmp_path / "story1" / "media" / "story.mp4"
    assert media_file.is_file()
    # Sealed on disk: the renderer's raw output ("draft-bytes") is NOT in the clear.
    assert b"draft-bytes" not in media_file.read_bytes()
    # …but the store decrypts it back to exactly what the renderer produced.
    assert store.read_media("story1", "story.mp4") == b"draft-bytes"
    # The result advertises the stored artifact, never the throwaway temp path.
    assert out.result.asset_uri == str(media_file)


def test_seam_with_real_matplotlib_renderer_produces_decodable_mp4(tmp_path):
    # Full production path: real pixels + at-rest encryption. The seam has only
    # ever been driven by FakeRenderer, so this is its first real-renderer test —
    # it would catch a regression in the adapter, capability check, or draft→
    # promote flow that FakeRenderer cannot exercise.
    pytest.importorskip("matplotlib")
    pytest.importorskip("imageio")
    pytest.importorskip("imageio_ffmpeg")
    from generate_animation import MatplotlibStickFigureRenderer
    from tests.kathai_chithiram.rendering.fake_renderer import tiny_script

    store = StoryArtifactStore(root=tmp_path, cipher=AesGcmCipher(generate_data_key()))
    store.create_story(
        "story1", created_at=datetime(2026, 7, 2, tzinfo=timezone.utc), story_text="x"
    )

    out = generate_story_video(
        renderer=MatplotlibStickFigureRenderer(),
        script=tiny_script(fps=8, duration_s=2),
        store=store,
        story_id="story1",
        seed=3,
    )

    data = store.read_media("story1", "story.mp4")
    assert b"ftyp" in data[:16]  # a real MP4 container header, decrypted back out
    assert len(data) > 1000  # genuine encoded frames, not a stub
    assert out.provenance["model"] == "matplotlib-stick-v1"


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
