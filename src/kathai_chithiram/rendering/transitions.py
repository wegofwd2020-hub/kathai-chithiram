"""Pure scene-transition compositing plans (no rendering dependency).

The scene-script contract lets each scene declare a ``transition_in`` and
``transition_out`` (``cut`` / ``fade`` / ``dissolve``, contract §3). This module
turns those declarations into a per-frame **compositing plan** a frame renderer
applies: for each frame of a scene it says how much of the scene's own content to
show and what to blend the remainder with — black (a fade) or the neighbouring
scene's boundary frame (a dissolve).

The logic is deliberately renderer-agnostic and stdlib-only (it computes weights,
not pixels), so it is tested with mock data and shared by any frame-based renderer.
A renderer composites ``out = self_frame * weight + other_frame * (1 - weight)``.

Transitions never change a scene's frame count — a fade/dissolve happens *within*
the scene's existing frames — so the audio timeline and the render-time safety
report (which are frame-count-derived) stay exactly in sync. Transitions are
gentle luminance ramps by construction: they do not introduce fast flashing or
high-contrast oscillation, so they pass the seizure-safety guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "TRANSITION_SECONDS",
    "BlendSource",
    "FrameComposite",
    "composite_plan",
    "transition_frames",
]

#: Target duration of a fade/dissolve, in seconds. Kept short and calm; capped to
#: half the scene so an incoming and outgoing transition never overlap.
TRANSITION_SECONDS = 0.5


class BlendSource(str, Enum):
    """What a frame's non-content portion is blended with.

    ``KEEP`` — show the scene's own content only (no blend). ``BLACK`` — a fade
    (blend toward black). ``PREV`` / ``NEXT`` — a dissolve (blend with the previous
    / next scene's boundary frame).
    """

    KEEP = "keep"
    BLACK = "black"
    PREV = "prev"
    NEXT = "next"


@dataclass(frozen=True)
class FrameComposite:
    """How one frame is composited.

    Args:
        weight: The scene content's weight in ``[0, 1]`` (``1.0`` = content only).
        source: What the remaining ``1 - weight`` is blended with
            (:class:`BlendSource`). ``KEEP`` implies ``weight == 1.0``.
    """

    weight: float
    source: BlendSource


def transition_frames(frame_count: int, fps: int) -> int:
    """Return the number of frames one transition spans for this scene.

    ``TRANSITION_SECONDS`` worth of frames, but never more than half the scene (so
    an incoming and outgoing transition cannot overlap), and ``0`` for a scene too
    short to hold one.

    Args:
        frame_count: The scene's frame count.
        fps: Frames per second (must be positive).

    Raises:
        ValueError: If ``fps`` is not positive.
    """
    if fps <= 0:
        raise ValueError("fps must be positive")
    span = round(TRANSITION_SECONDS * fps)
    return max(0, min(span, frame_count // 2))


def composite_plan(
    frame_count: int, fps: int, transition_in: str, transition_out: str
) -> tuple[FrameComposite, ...]:
    """Return the per-frame compositing plan for one scene.

    The incoming transition ramps the scene's first :func:`transition_frames`
    frames up from black (``fade``) or the previous scene (``dissolve``); the
    outgoing transition ramps its last frames down to black / the next scene.
    ``cut`` frames (and every frame in between) are kept as-is.

    Args:
        frame_count: The scene's frame count.
        fps: Frames per second.
        transition_in: One of ``cut`` / ``fade`` / ``dissolve``.
        transition_out: One of ``cut`` / ``fade`` / ``dissolve``.

    Returns:
        A tuple of :class:`FrameComposite`, one per frame, in play order.

    Raises:
        ValueError: If ``fps`` is not positive, or a transition is not one of the
            allowed kinds.
    """
    plan = [FrameComposite(1.0, BlendSource.KEEP) for _ in range(frame_count)]
    span = transition_frames(frame_count, fps)
    if span == 0:
        return tuple(plan)

    in_source = _incoming_source(transition_in)
    if in_source is not None:
        for i in range(span):
            plan[i] = FrameComposite((i + 1) / span, in_source)

    out_source = _outgoing_source(transition_out)
    if out_source is not None:
        for m in range(span):
            plan[frame_count - 1 - m] = FrameComposite((m + 1) / span, out_source)

    return tuple(plan)


def _incoming_source(kind: str) -> BlendSource | None:
    """Map a ``transition_in`` to its blend source (``None`` = a hard cut)."""
    return _INCOMING.get(_valid(kind))


def _outgoing_source(kind: str) -> BlendSource | None:
    """Map a ``transition_out`` to its blend source (``None`` = a hard cut)."""
    return _OUTGOING.get(_valid(kind))


_ALLOWED = frozenset({"cut", "fade", "dissolve"})
_INCOMING = {"fade": BlendSource.BLACK, "dissolve": BlendSource.PREV}
_OUTGOING = {"fade": BlendSource.BLACK, "dissolve": BlendSource.NEXT}


def _valid(kind: str) -> str:
    """Return ``kind`` if it is an allowed transition, else raise."""
    if kind not in _ALLOWED:
        raise ValueError(f"unknown transition '{kind}'; expected one of {sorted(_ALLOWED)}")
    return kind
