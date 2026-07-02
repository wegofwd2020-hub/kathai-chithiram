"""Pick content-driven art cues for a scene from its setting + caption (pure).

The reference renderer's original art was hand-authored per scene *index* for the
one demo story, so an arbitrary story rendered either as the demo's frames (wrong)
or a plain caption card (dull). This module derives a small, structured **art hint**
— a background, a facial expression, and a gesture — from the scene's ``setting``
and ``caption`` text, so any story gets a calm, roughly-appropriate scene.

It is deliberately keyword-based and stdlib-only: it computes cues, not pixels, so
it is tested with mock data and shared, while the drawing stays in the render
extra. The mapping is intentionally gentle and conservative — unknown content
falls back to a calm, neutral scene rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "Background",
    "Expression",
    "Gesture",
    "SceneArtHint",
    "art_hint_for",
]


class Background(str, Enum):
    """The backdrop a scene is drawn against."""

    BATHROOM = "bathroom"
    BEDROOM = "bedroom"
    KITCHEN = "kitchen"
    OUTDOORS = "outdoors"
    CALM = "calm"  # the neutral fallback: a soft, quiet backdrop


class Expression(str, Enum):
    """The figure's facial expression."""

    SMILE = "smile"
    SLEEPY = "sleepy"
    CALM = "calm"  # neutral-gentle default


class Gesture(str, Enum):
    """The figure's arm gesture."""

    WAVE = "wave"
    REST = "rest"  # relaxed arms (default)


@dataclass(frozen=True)
class SceneArtHint:
    """The composed art cues for one scene.

    Args:
        background: The backdrop to draw.
        expression: The figure's expression.
        gesture: The figure's gesture.
    """

    background: Background
    expression: Expression
    gesture: Gesture


# Ordered (keyword, value) tables — first match wins, so more specific cues can
# precede general ones. Matched case-insensitively as substrings of setting+caption.
_BACKGROUND_KEYWORDS: tuple[tuple[str, Background], ...] = (
    ("bath", Background.BATHROOM),
    ("sink", Background.BATHROOM),
    ("toilet", Background.BATHROOM),
    ("bed", Background.BEDROOM),
    ("sleep", Background.BEDROOM),
    ("night", Background.BEDROOM),
    ("nap", Background.BEDROOM),
    ("pillow", Background.BEDROOM),
    ("kitchen", Background.KITCHEN),
    ("cook", Background.KITCHEN),
    ("meal", Background.KITCHEN),
    ("breakfast", Background.KITCHEN),
    ("dinner", Background.KITCHEN),
    ("park", Background.OUTDOORS),
    ("garden", Background.OUTDOORS),
    ("outside", Background.OUTDOORS),
    ("outdoor", Background.OUTDOORS),
    ("playground", Background.OUTDOORS),
    ("tree", Background.OUTDOORS),
    ("beach", Background.OUTDOORS),
    ("yard", Background.OUTDOORS),
)

# Stems (matched as substrings) so inflections are caught: "smil" → smile/smiled/
# smiling, "happ" → happy/happily. Bare "rest" is avoided (it hides in
# "interested"/"forest"); sleepiness is keyed on unambiguous words.
_SLEEPY_KEYWORDS = ("sleep", "asleep", "nap", "tired", "yawn", "bedtime", "drowsy")
_SMILE_KEYWORDS = (
    "smil", "happ", "proud", "glad", "bright", "fun", "joy", "laugh",
    "excit", "cheer", "brave", "safe", "love", "giggle",
)
_WAVE_KEYWORDS = ("wave", "hello", "hiya", "goodbye", "greet")


def art_hint_for(setting: str, caption: str) -> SceneArtHint:
    """Return the :class:`SceneArtHint` for a scene's ``setting`` and ``caption``.

    Args:
        setting: The scene's setting string.
        caption: The scene's caption text (display name already reinserted; only
            keywords are read, never stored).

    Returns:
        A :class:`SceneArtHint`. Unrecognized content yields a calm, neutral scene.
    """
    text = f"{setting} {caption}".lower()
    return SceneArtHint(
        background=_first_match(text, _BACKGROUND_KEYWORDS, Background.CALM),
        expression=_expression(text),
        gesture=Gesture.WAVE if _contains_any(text, _WAVE_KEYWORDS) else Gesture.REST,
    )


def _expression(text: str) -> Expression:
    """Choose the figure's expression (sleepy > smile > calm)."""
    if _contains_any(text, _SLEEPY_KEYWORDS):
        return Expression.SLEEPY
    if _contains_any(text, _SMILE_KEYWORDS):
        return Expression.SMILE
    return Expression.CALM


def _first_match(
    text: str, table: tuple[tuple[str, Background], ...], default: Background
) -> Background:
    """Return the value of the first keyword found in ``text``, else ``default``."""
    for keyword, value in table:
        if keyword in text:
            return value
    return default


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    """Whether any of ``keywords`` occurs in ``text``."""
    return any(keyword in text for keyword in keywords)
