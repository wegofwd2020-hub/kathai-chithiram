"""Tests for the caption-sidecar builder (SubRip / WebVTT), stdlib-only."""

from __future__ import annotations

import pytest
from tests.kathai_chithiram.scene_script.mock_scripts import valid_scene_script

from kathai_chithiram.rendering.captions import Cue, build_captions, to_srt, to_vtt
from kathai_chithiram.rendering.pipeline import build_render_plan
from kathai_chithiram.rendering.silas_story import SILAS_SCENE_SCRIPT, silas_mapping


# ── build_captions ──────────────────────────────────────────────────────────────
def test_one_cue_per_scene_back_to_back():
    # valid_scene_script: scene 1 = 3 s, scene 2 = 4 s → cues [0,3] and [3,7].
    plan = build_render_plan(valid_scene_script())
    cues = build_captions(plan)

    assert [(c.index, c.start_s, c.end_s) for c in cues] == [(1, 0.0, 3.0), (2, 3.0, 7.0)]
    assert cues[0].text == plan.scenes[0].caption
    assert cues[1].text == plan.scenes[1].caption


def test_cues_carry_the_reinserted_display_name():
    plan = build_render_plan(SILAS_SCENE_SCRIPT, mapping=silas_mapping())
    cues = build_captions(plan)
    assert any("Silas" in c.text for c in cues)
    assert all("CHILD" not in c.text for c in cues)  # token never leaks into the sidecar


# ── to_srt ──────────────────────────────────────────────────────────────────────
def test_srt_format():
    srt = to_srt([Cue(1, 0.0, 3.5, "Hi"), Cue(2, 3.5, 7.0, "Bye")])
    assert srt == (
        "1\n00:00:00,000 --> 00:00:03,500\nHi\n\n"
        "2\n00:00:03,500 --> 00:00:07,000\nBye\n"
    )


def test_srt_hours_and_minutes():
    srt = to_srt([Cue(1, 3661.5, 3662.0, "x")])
    assert "01:01:01,500 --> 01:01:02,000" in srt


def test_srt_empty_is_empty_string():
    assert to_srt([]) == ""


# ── to_vtt ──────────────────────────────────────────────────────────────────────
def test_vtt_format_has_header_and_dot_millis():
    vtt = to_vtt([Cue(1, 0.0, 3.5, "Hi")])
    assert vtt == "WEBVTT\n\n00:00:00.000 --> 00:00:03.500\nHi\n"


def test_vtt_empty_is_header_only():
    assert to_vtt([]) == "WEBVTT\n"


# ── validation ──────────────────────────────────────────────────────────────────
def test_negative_timestamp_rejected():
    with pytest.raises(ValueError, match="negative"):
        to_srt([Cue(1, -1.0, 0.0, "x")])


# ── round-trip through a plan ────────────────────────────────────────────────────
def test_srt_and_vtt_built_from_the_same_plan_agree_on_text():
    plan = build_render_plan(valid_scene_script())
    cues = build_captions(plan)
    srt, vtt = to_srt(cues), to_vtt(cues)
    for cue in cues:
        assert cue.text in srt
        assert cue.text in vtt
