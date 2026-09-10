"""The scene-script art vocabulary registry is the single source of truth.

KC-13 / ADR-007 D1: one module owns the closed enums that decide what a child
can actually see. These tests pin the vocabulary at *exact parity* with the art
that exists today (six backgrounds, four expressions, two gestures) — growing it
is separate, later work — and prove no parallel copy of the enums exists.
"""

from __future__ import annotations

from kathai_chithiram.scene_script import vocabulary


def test_background_members_at_parity() -> None:
    assert {b.value for b in vocabulary.Background} == {
        "bathroom",
        "bedroom",
        "kitchen",
        "classroom",
        "outdoors",
        "calm",
    }


def test_expression_members_at_parity() -> None:
    assert {e.value for e in vocabulary.Expression} == {
        "smile",
        "sleepy",
        "calm",
        "neutral",
    }


def test_gesture_members_at_parity() -> None:
    assert {g.value for g in vocabulary.Gesture} == {"wave", "rest"}


def test_prop_members_at_parity() -> None:
    # The twelve props both reference renderers draw today (matplotlib's
    # _PROP_DRAW canonical set; Blender levelled up to match under KC-13).
    assert {p.value for p in vocabulary.Prop} == {
        "toothbrush",
        "toothpaste",
        "ball",
        "book",
        "cup",
        "block",
        "toy",
        "plate",
        "apple",
        "backpack",
        "spoon",
        "shoe",
    }


def test_scene_art_hints_reuses_registry_enums_no_parallel_copy() -> None:
    # ADR-007 D1: the renderer's lookup tables derive from the registry rather
    # than holding a parallel copy. Identity, not equality, is the check that a
    # second definition has not crept back in.
    from kathai_chithiram.rendering import scene_art_hints

    assert scene_art_hints.Background is vocabulary.Background
    assert scene_art_hints.Expression is vocabulary.Expression
    assert scene_art_hints.Gesture is vocabulary.Gesture
