"""Tests for the pure scene-transition compositing plans (no rendering needed)."""

from __future__ import annotations

import pytest

from kathai_chithiram.rendering.transitions import (
    TRANSITION_SECONDS,
    BlendSource,
    composite_plan,
    transition_frames,
)


# ── transition_frames ───────────────────────────────────────────────────────────
def test_transition_frames_is_the_target_duration():
    # 0.5 s at 24 fps = 12 frames, and the scene is long enough to hold it.
    assert transition_frames(frame_count=96, fps=24) == round(TRANSITION_SECONDS * 24)


def test_transition_frames_capped_at_half_the_scene():
    # A 6-frame scene cannot spend 12 frames fading; capped so in+out never overlap.
    assert transition_frames(frame_count=6, fps=24) == 3


def test_transition_frames_zero_for_a_one_frame_scene():
    assert transition_frames(frame_count=1, fps=24) == 0


def test_transition_frames_rejects_bad_fps():
    with pytest.raises(ValueError, match="fps"):
        transition_frames(frame_count=10, fps=0)


# ── composite_plan: cut ─────────────────────────────────────────────────────────
def test_cut_keeps_every_frame():
    plan = composite_plan(10, fps=24, transition_in="cut", transition_out="cut")
    assert all(c.source is BlendSource.KEEP and c.weight == 1.0 for c in plan)


# ── composite_plan: fade ────────────────────────────────────────────────────────
def test_fade_in_ramps_up_from_black():
    plan = composite_plan(100, fps=24, transition_in="fade", transition_out="cut")
    span = transition_frames(100, 24)
    # First `span` frames ramp (i+1)/span against black; the rest are kept.
    for i in range(span):
        assert plan[i].source is BlendSource.BLACK
        assert plan[i].weight == pytest.approx((i + 1) / span)
    assert plan[span].source is BlendSource.KEEP
    assert plan[-1].source is BlendSource.KEEP


def test_fade_out_ramps_down_to_black():
    plan = composite_plan(100, fps=24, transition_in="cut", transition_out="fade")
    span = transition_frames(100, 24)
    # Last frame is mostly black (weight 1/span); it deepens inward to 1.0.
    assert plan[-1].source is BlendSource.BLACK
    assert plan[-1].weight == pytest.approx(1 / span)
    assert plan[-span].weight == pytest.approx(1.0)
    assert plan[-span - 1].source is BlendSource.KEEP


def test_fade_both_ends_leave_the_middle_untouched():
    plan = composite_plan(100, fps=24, transition_in="fade", transition_out="fade")
    span = transition_frames(100, 24)
    assert all(c.source is BlendSource.KEEP for c in plan[span:-span])


# ── composite_plan: dissolve ────────────────────────────────────────────────────
def test_dissolve_blends_with_neighbours():
    plan = composite_plan(100, fps=24, transition_in="dissolve", transition_out="dissolve")
    span = transition_frames(100, 24)
    assert plan[0].source is BlendSource.PREV  # incoming dissolves from the previous
    assert plan[-1].source is BlendSource.NEXT  # outgoing dissolves into the next
    assert all(c.source is BlendSource.KEEP for c in plan[span:-span])


# ── overlap safety ──────────────────────────────────────────────────────────────
def test_short_scene_in_and_out_do_not_overlap():
    # 8 frames, span capped to 4: in = [0,4), out = [4,8); every frame is a
    # transition but none is assigned by both ends.
    plan = composite_plan(8, fps=24, transition_in="fade", transition_out="fade")
    assert transition_frames(8, 24) == 4
    assert [c.source for c in plan[:4]] == [BlendSource.BLACK] * 4
    assert [c.source for c in plan[4:]] == [BlendSource.BLACK] * 4


# ── validation ──────────────────────────────────────────────────────────────────
def test_unknown_transition_rejected():
    with pytest.raises(ValueError, match="unknown transition"):
        composite_plan(10, fps=24, transition_in="wipe", transition_out="cut")
