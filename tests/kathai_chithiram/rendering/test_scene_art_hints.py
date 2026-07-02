"""Tests for the content-driven scene-art hint selector (pure, no rendering)."""

from __future__ import annotations

import pytest

from kathai_chithiram.rendering.scene_art_hints import (
    Background,
    Expression,
    Gesture,
    art_hint_for,
    resolve_figure_cues,
)


# ── background from setting/caption ──────────────────────────────────────────────
@pytest.mark.parametrize(
    ("setting", "expected"),
    [
        ("bathroom", Background.BATHROOM),
        ("the bedroom", Background.BEDROOM),
        ("kitchen", Background.KITCHEN),
        ("the classroom", Background.CLASSROOM),
        ("at school", Background.CLASSROOM),
        ("the park", Background.OUTDOORS),
        ("a calm, quiet place", Background.CALM),  # the offline generator's default setting
        ("somewhere unknown", Background.CALM),
    ],
)
def test_background_from_setting(setting: str, expected: Background):
    assert art_hint_for(setting, "the child is here").background is expected


def test_background_can_come_from_the_caption_not_just_setting():
    # A neutral setting but a caption that mentions the garden → outdoors.
    assert art_hint_for("", "She played in the garden.").background is Background.OUTDOORS


def test_matching_is_case_insensitive():
    assert art_hint_for("BATHROOM", "BRUSHING").background is Background.BATHROOM


# ── expression ──────────────────────────────────────────────────────────────────
def test_smile_from_positive_words():
    assert art_hint_for("room", "She felt proud and happy.").expression is Expression.SMILE


def test_sleepy_from_rest_words():
    hint = art_hint_for("bedroom", "He was tired and went to sleep.")
    assert hint.expression is Expression.SLEEPY


def test_calm_default_expression():
    assert art_hint_for("room", "She looked at the table.").expression is Expression.CALM


def test_sleepy_takes_priority_over_smile():
    # Contains both "happy" and "sleep": rest wins (a bedtime scene stays calm).
    assert art_hint_for("bedroom", "Happy and ready to sleep.").expression is Expression.SLEEPY


# ── gesture ─────────────────────────────────────────────────────────────────────
def test_wave_from_greeting_words():
    assert art_hint_for("park", "She waved hello to her friend.").gesture is Gesture.WAVE


def test_rest_gesture_by_default():
    assert art_hint_for("room", "She sat down quietly.").gesture is Gesture.REST


# ── resolve_figure_cues: script character fields win, caption is the fallback ─────
def test_script_expression_wins_over_caption():
    # Caption is neutral; the script's expression decides.
    expr, _ = resolve_figure_cues("standing", "sleepy", "She looked outside.")
    assert expr is Expression.SLEEPY


def test_worried_expression_maps_to_neutral():
    expr, _ = resolve_figure_cues("standing", "scared", "She stood still.")
    assert expr is Expression.NEUTRAL


def test_unknown_expression_falls_back_to_caption():
    # "mysterious" isn't a known expression word → the caption ("smiled") decides.
    expr, _ = resolve_figure_cues("standing", "mysterious", "She smiled warmly.")
    assert expr is Expression.SMILE


def test_pose_drives_the_wave_gesture():
    _, gesture = resolve_figure_cues("waving", "calm", "She stood by the door.")
    assert gesture is Gesture.WAVE


def test_gesture_falls_back_to_caption_when_pose_is_generic():
    _, gesture = resolve_figure_cues("standing", "calm", "She waved hello to him.")
    assert gesture is Gesture.WAVE


def test_calm_expression_and_standing_pose_are_the_quiet_default():
    expr, gesture = resolve_figure_cues("standing", "calm", "She read a book.")
    assert expr is Expression.CALM
    assert gesture is Gesture.REST
