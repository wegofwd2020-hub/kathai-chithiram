"""The closed art vocabulary a scene script may draw on (ADR-007 D1).

This module is the **single source of truth** for the fixed set of things the
animation can actually depict: the backdrop, the figure's face, and the figure's
gesture. The scene-script schema derives its ``enum`` lists from these members,
and the renderers' lookup tables are keyed by them — so "what a story may ask
for" and "what a child can see" cannot drift apart.

The vocabulary is deliberately small and closed. It is pinned here at exact
parity with the art that exists today (six backgrounds, four expressions, two
gestures); growing it is a separate art task, gated by the renderer conformance
suite (ADR-007 D3), never a silent addition.

The enums are ``str``-valued so a member compares and serializes as its wire
string, matching how ``setting`` / ``expression`` / ``pose`` appear in a script.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "Background",
    "Expression",
    "Gesture",
]


class Background(str, Enum):
    """The backdrop a scene is drawn against."""

    BATHROOM = "bathroom"
    BEDROOM = "bedroom"
    KITCHEN = "kitchen"
    CLASSROOM = "classroom"
    OUTDOORS = "outdoors"
    CALM = "calm"  # the neutral fallback: a soft, quiet backdrop


class Expression(str, Enum):
    """The figure's facial expression."""

    SMILE = "smile"
    SLEEPY = "sleepy"
    CALM = "calm"  # gentle default (a soft smile)
    NEUTRAL = "neutral"  # no smile, eyes open (e.g. worried / sad / scared)


class Gesture(str, Enum):
    """The figure's arm gesture."""

    WAVE = "wave"
    REST = "rest"  # relaxed arms (default)
