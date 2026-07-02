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
from typing import TypeVar

_T = TypeVar("_T")

__all__ = [
    "Background",
    "Expression",
    "Gesture",
    "SceneArtHint",
    "art_hint_for",
    "resolve_figure_cues",
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
    CALM = "calm"  # gentle default (a soft smile)
    NEUTRAL = "neutral"  # no smile, eyes open (e.g. worried / sad / scared)


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


# The scene script's ``characters[].expression`` / ``pose`` words, mapped to the
# figure cues. Matched per token so "very happy" still resolves. An unrecognized
# word falls back to the caption-derived hint, so a generic value never overrides
# what the caption clearly says.
_EXPRESSION_WORDS: dict[str, Expression] = {
    "smile": Expression.SMILE, "smiling": Expression.SMILE, "happy": Expression.SMILE,
    "proud": Expression.SMILE, "glad": Expression.SMILE, "excited": Expression.SMILE,
    "cheerful": Expression.SMILE, "joyful": Expression.SMILE, "delighted": Expression.SMILE,
    "sleepy": Expression.SLEEPY, "tired": Expression.SLEEPY, "sleeping": Expression.SLEEPY,
    "asleep": Expression.SLEEPY, "drowsy": Expression.SLEEPY,
    "calm": Expression.CALM, "relaxed": Expression.CALM, "content": Expression.CALM,
    "focused": Expression.CALM, "gentle": Expression.CALM, "peaceful": Expression.CALM,
    "neutral": Expression.NEUTRAL, "sad": Expression.NEUTRAL, "scared": Expression.NEUTRAL,
    "worried": Expression.NEUTRAL, "upset": Expression.NEUTRAL, "nervous": Expression.NEUTRAL,
    "afraid": Expression.NEUTRAL, "anxious": Expression.NEUTRAL, "serious": Expression.NEUTRAL,
}
_POSE_GESTURES: dict[str, Gesture] = {
    "wave": Gesture.WAVE, "waves": Gesture.WAVE, "waving": Gesture.WAVE, "greeting": Gesture.WAVE,
}


def resolve_figure_cues(pose: str, expression: str, caption: str) -> tuple[Expression, Gesture]:
    """Resolve the figure's expression + gesture, script-first then caption.

    The scene script's ``characters[].expression`` / ``pose`` win when they name a
    recognized cue; otherwise the caption's keywords decide, so a generic authored
    value ("standing", an unknown mood) never suppresses a clear caption.

    Args:
        pose: The character's ``pose`` string from the script.
        expression: The character's ``expression`` string from the script.
        caption: The scene caption (used as the fallback signal).

    Returns:
        The chosen :class:`Expression` and :class:`Gesture`.
    """
    text = caption.lower()
    expr = _match_token(expression, _EXPRESSION_WORDS) or _expression(text)
    gesture = _match_token(pose, _POSE_GESTURES)
    if gesture is None:
        gesture = Gesture.WAVE if _contains_any(text, _WAVE_KEYWORDS) else Gesture.REST
    return expr, gesture


def _match_token(value: str, table: dict[str, _T]) -> _T | None:
    """Return the mapping for the first token of ``value`` found in ``table``."""
    for token in value.lower().split():
        if token in table:
            return table[token]
    return None
