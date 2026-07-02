"""Matplotlib stick-figure renderer (reference renderer v1).

Consumes the scene-script contract through
:class:`kathai_chithiram.rendering.SceneScriptRenderer`: the script is validated,
the child's display name is reinserted at render time, captions/timing come from
the plan, and the render-time safety guards run before any file is delivered.

Run as a script to render the bundled "Silas Shines His Smile" demo
(requires ``imageio-ffmpeg``)::

    PYTHONPATH=src python generate_animation.py
"""

from __future__ import annotations

import io
import math
from collections.abc import Callable

import matplotlib
import numpy as np

matplotlib.use("Agg")

import matplotlib.patches as patches  # noqa: E402  (must follow matplotlib.use)
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Arc  # noqa: E402
from PIL import Image  # noqa: E402

from kathai_chithiram.rendering.pipeline import (  # noqa: E402
    RenderPlan,
    SceneScriptRenderer,
)
from kathai_chithiram.rendering.safety import RenderSafetyReport  # noqa: E402
from kathai_chithiram.rendering.transitions import (  # noqa: E402
    BlendSource,
    composite_plan,
)

FPS = 24
W, H = 960, 540  # output resolution
DPI = 96
FIG_W = W / DPI
FIG_H = H / DPI

# ── colour palette ──────────────────────────────────────────────────────────
BG = "#F5F5F0"
DARK = "#222222"
BLUE = "#4A90D9"
LIGHT_BLUE = "#AED6F1"
WHITE = "#FFFFFF"
GREY = "#CCCCCC"
GREEN = "#5DBB63"
YELLOW = "#F5C518"
SKIN = "#F4C08A"
TOOTHPASTE_BLUE = "#56B4D3"


# ── stick-figure helpers ──────────────────────────────────────────────────────


def draw_stick_figure(
    ax,
    cx,
    cy,
    scale=1.0,
    arm_l_angle=-60,
    arm_r_angle=-120,
    head_tilt=0,
    smile=False,
    eyes_closed=False,
):
    """Draw a stick figure centred at (cx, cy) with the given scale."""
    s = scale
    lw = 3 * s

    # torso
    ax.plot([cx, cx], [cy, cy + 0.30 * s], color=DARK, lw=lw, solid_capstyle="round")

    # head
    head_r = 0.10 * s
    head_cx = cx + math.sin(math.radians(head_tilt)) * 0.05 * s
    head_cy = cy + 0.30 * s + head_r + 0.01 * s
    ax.add_patch(plt.Circle((head_cx, head_cy), head_r, color=SKIN, zorder=5))
    ax.add_patch(
        plt.Circle((head_cx, head_cy), head_r, fill=False, color=DARK, lw=lw * 0.6, zorder=6)
    )

    # hair (simple arc on top)
    ax.add_patch(
        Arc(
            (head_cx, head_cy),
            head_r * 2.1,
            head_r * 2.1,
            angle=0,
            theta1=10,
            theta2=170,
            color="#8B5E3C",
            lw=lw * 1.2,
            zorder=7,
        )
    )

    # eyes
    eye_offset = head_r * 0.35
    eye_y = head_cy + head_r * 0.1
    if eyes_closed:
        ax.plot(
            [head_cx - eye_offset - head_r * 0.12, head_cx - eye_offset + head_r * 0.12],
            [eye_y, eye_y],
            color=DARK,
            lw=lw * 0.5,
            zorder=8,
        )
        ax.plot(
            [head_cx + eye_offset - head_r * 0.12, head_cx + eye_offset + head_r * 0.12],
            [eye_y, eye_y],
            color=DARK,
            lw=lw * 0.5,
            zorder=8,
        )
    else:
        for ex in [head_cx - eye_offset, head_cx + eye_offset]:
            ax.add_patch(plt.Circle((ex, eye_y), head_r * 0.12, color=DARK, zorder=8))

    # mouth
    mouth_y = head_cy - head_r * 0.35
    if smile:
        ax.add_patch(
            Arc(
                (head_cx, mouth_y),
                head_r * 0.55,
                head_r * 0.35,
                angle=0,
                theta1=200,
                theta2=340,
                color=DARK,
                lw=lw * 0.6,
                zorder=8,
            )
        )
    else:
        ax.plot(
            [head_cx - head_r * 0.2, head_cx + head_r * 0.2],
            [mouth_y, mouth_y],
            color=DARK,
            lw=lw * 0.5,
            zorder=8,
        )

    # shirt (blue rounded rectangle over torso)
    shirt_h = 0.20 * s
    shirt_w = 0.14 * s
    ax.add_patch(
        patches.FancyBboxPatch(
            (cx - shirt_w / 2, cy + 0.06 * s),
            shirt_w,
            shirt_h,
            boxstyle="round,pad=0.005",
            color=BLUE,
            zorder=4,
        )
    )

    shoulder_y = cy + 0.26 * s

    def arm_end(angle_deg):
        r = 0.22 * s
        a = math.radians(angle_deg)
        return cx + r * math.cos(a), shoulder_y + r * math.sin(a)

    lax, lay = arm_end(arm_l_angle)
    rax, ray = arm_end(arm_r_angle)
    ax.plot([cx, lax], [shoulder_y, lay], color=DARK, lw=lw, solid_capstyle="round", zorder=3)
    ax.plot([cx, rax], [shoulder_y, ray], color=DARK, lw=lw, solid_capstyle="round", zorder=3)

    # hands
    for hx, hy in [(lax, lay), (rax, ray)]:
        ax.add_patch(plt.Circle((hx, hy), 0.025 * s, color=SKIN, zorder=4))

    # legs
    hip_y = cy + 0.05 * s

    def leg_end(angle_deg):
        r = 0.28 * s
        a = math.radians(angle_deg)
        return cx + r * math.cos(a), hip_y + r * math.sin(a)

    llx, lly = leg_end(-(90 + 20))
    rlx, rly = leg_end(-(90 - 20))
    ax.plot([cx, llx], [hip_y, lly], color=DARK, lw=lw, solid_capstyle="round", zorder=3)
    ax.plot([cx, rlx], [hip_y, rly], color=DARK, lw=lw, solid_capstyle="round", zorder=3)

    # feet (small horizontal lines)
    foot_len = 0.06 * s
    ax.plot([llx, llx - foot_len], [lly, lly], color=DARK, lw=lw * 0.8, solid_capstyle="round")
    ax.plot([rlx, rlx + foot_len], [rly, rly], color=DARK, lw=lw * 0.8, solid_capstyle="round")


def draw_mirror(ax, x, y, w=0.18, h=0.28):
    """Draw a wall mirror."""
    ax.add_patch(
        patches.FancyBboxPatch(
            (x - w / 2, y),
            w,
            h,
            boxstyle="round,pad=0.01",
            edgecolor=GREY,
            facecolor=LIGHT_BLUE,
            lw=3,
            alpha=0.6,
            zorder=2,
        )
    )


def draw_sink(ax, x, y, w=0.45, h=0.12):
    """Draw a sink with a faucet."""
    ax.add_patch(
        patches.FancyBboxPatch(
            (x - w / 2, y),
            w,
            h,
            boxstyle="round,pad=0.015",
            edgecolor=GREY,
            facecolor=WHITE,
            lw=2,
            zorder=2,
        )
    )
    ax.plot([x, x], [y + h, y + h + 0.07], color=GREY, lw=4)
    ax.plot([x - 0.04, x + 0.04], [y + h + 0.07, y + h + 0.07], color=GREY, lw=4)


def draw_toothbrush(ax, x, y, angle_deg=45, scale=1.0):
    """Draw a toothbrush at the given angle."""
    s = scale
    length = 0.18 * s
    a = math.radians(angle_deg)
    ex = x + length * math.cos(a)
    ey = y + length * math.sin(a)
    ax.plot([x, ex], [y, ey], color=BLUE, lw=5 * s, solid_capstyle="round", zorder=6)
    for i in range(5):
        offset = (i - 2) * 0.008 * s
        ax.plot(
            [ex + offset * math.cos(a + math.pi / 2), ex + 0.025 * s * math.cos(a)
             + offset * math.cos(a + math.pi / 2)],
            [ey + offset * math.sin(a + math.pi / 2), ey + 0.025 * s * math.sin(a)
             + offset * math.sin(a + math.pi / 2)],
            color=WHITE,
            lw=1.5,
            zorder=7,
        )


def draw_toothpaste(ax, x, y, scale=1.0):
    """Draw a toothpaste tube."""
    s = scale
    ax.add_patch(
        patches.FancyBboxPatch(
            (x - 0.03 * s, y),
            0.06 * s,
            0.16 * s,
            boxstyle="round,pad=0.005",
            facecolor=GREEN,
            edgecolor=DARK,
            lw=1.5,
            zorder=6,
        )
    )
    ax.add_patch(
        patches.FancyBboxPatch(
            (x - 0.03 * s, y + 0.06 * s),
            0.06 * s,
            0.02 * s,
            boxstyle="square,pad=0",
            facecolor=WHITE,
            edgecolor="none",
            zorder=7,
        )
    )


def draw_sparkles(ax, cx, cy, n=4, r=0.12, t=0.0):
    """Draw animated sparkle stars around (cx, cy)."""
    for i in range(n):
        angle = 2 * math.pi * i / n + t
        ax.plot(cx + r * math.cos(angle), cy + r * math.sin(angle), "*",
                color=YELLOW, markersize=14, zorder=10)


def text_box(ax, text, x=0.5, y=0.08, fontsize=16):
    """Draw the caption card at the bottom of the frame."""
    ax.text(
        x,
        y,
        text,
        transform=ax.transAxes,
        fontsize=fontsize,
        ha="center",
        va="bottom",
        wrap=True,
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "white", "edgecolor": GREY, "alpha": 0.9},
        color=DARK,
        family="DejaVu Sans",
    )


def new_fig():
    """Create a blank figure/axes pair sized to the output resolution."""
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def fig_to_rgb(fig):
    """Rasterize a figure to an (H, W, 3) uint8 RGB array."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight", pad_inches=0,
                facecolor=fig.get_facecolor())
    buf.seek(0)
    img = Image.open(buf).convert("RGB").resize((W, H))
    return np.array(img)


def _tiled_wall(ax):
    """Draw the faint bathroom wall tiling shared by several scenes."""
    for row in range(6):
        for col in range(10):
            ax.add_patch(
                patches.FancyBboxPatch(
                    (col * 0.1 + 0.005, row * 0.17 + 0.005),
                    0.09,
                    0.16,
                    boxstyle="round,pad=0.003",
                    facecolor="#E8E8E8",
                    edgecolor=GREY,
                    lw=0.8,
                    alpha=0.4,
                    zorder=0,
                )
            )


# ── scene builders (caption supplied by the render plan) ─────────────────────


def scene_title(frame_idx, title):
    """Title card; the story title comes from the plan."""
    fig, ax = new_fig()
    for i in range(20):
        ax.add_patch(
            patches.Rectangle((0, i / 20), 1, 1 / 20, color=LIGHT_BLUE,
                              alpha=0.03 * (i / 20), zorder=0)
        )
    ax.text(0.5, 0.62, title, transform=ax.transAxes, fontsize=30, ha="center",
            va="center", fontweight="bold", color=DARK, family="DejaVu Sans")
    draw_toothbrush(ax, 0.42, 0.30, angle_deg=30, scale=1.5)
    draw_sparkles(ax, 0.58, 0.38, n=3, r=0.07, t=frame_idx * 0.08)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_mirror(frame_idx, caption):
    """Scene 1 — at the mirror, takes a deep breath."""
    fig, ax = new_fig()
    _tiled_wall(ax)
    draw_mirror(ax, 0.55, 0.40, w=0.22, h=0.35)
    draw_sink(ax, 0.50, 0.25)
    draw_stick_figure(ax, 0.55, 0.40, scale=0.6, smile=True)
    draw_stick_figure(ax, 0.42, 0.22, scale=0.9, arm_l_angle=-70, arm_r_angle=-110)
    for i in range(3):
        offset = i * 0.025 + (frame_idx % 8) * 0.003
        ax.add_patch(
            plt.Circle((0.38, 0.58 + offset), 0.008 + i * 0.004, fill=False,
                       color=LIGHT_BLUE, lw=1.2, alpha=0.7 - i * 0.2)
        )
    text_box(ax, caption)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_grab_brush(frame_idx, caption):
    """Scene 2 — grasps toothbrush with a full-hand grip."""
    fig, ax = new_fig()
    _tiled_wall(ax)
    draw_sink(ax, 0.50, 0.25)
    draw_toothbrush(ax, 0.70, 0.30, angle_deg=80, scale=1.0)
    draw_toothpaste(ax, 0.78, 0.30, scale=0.9)
    draw_stick_figure(ax, 0.42, 0.22, scale=0.9, arm_l_angle=-30, arm_r_angle=-130, smile=True)
    ax.annotate("Full-hand grip", xy=(0.70, 0.33), xytext=(0.55, 0.60), fontsize=11,
                color=BLUE, arrowprops={"arrowstyle": "->", "color": BLUE, "lw": 1.5},
                bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8})
    text_box(ax, caption)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_apply_paste(frame_idx, caption):
    """Scene 3 — rest brush on sink, apply pea-sized paste."""
    fig, ax = new_fig()
    _tiled_wall(ax)
    draw_sink(ax, 0.55, 0.28)
    draw_toothbrush(ax, 0.48, 0.37, angle_deg=10, scale=1.0)
    ax.add_patch(plt.Circle((0.66, 0.375), 0.018, color=TOOTHPASTE_BLUE, zorder=8))
    draw_toothpaste(ax, 0.74, 0.38, scale=0.8)
    ax.annotate("", xy=(0.68, 0.38), xytext=(0.73, 0.44),
                arrowprops={"arrowstyle": "->", "color": GREEN, "lw": 2.0})
    draw_stick_figure(ax, 0.38, 0.22, scale=0.9, arm_l_angle=-20, arm_r_angle=-140)
    ax.text(0.66, 0.42, "pea-sized!", fontsize=10, color=TOOTHPASTE_BLUE, ha="center",
            style="italic")
    text_box(ax, caption)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_wet_brush(frame_idx, caption):
    """Scene 4 — wet brush under cool water, count one-two-three."""
    fig, ax = new_fig()
    _tiled_wall(ax)
    draw_sink(ax, 0.55, 0.25)
    for drop in range(6):
        dy = drop * 0.04 + (frame_idx % 6) * 0.008
        ax.plot([0.555, 0.555 + drop * 0.001], [0.32 + dy, 0.32 + dy + 0.03],
                color=LIGHT_BLUE, lw=2, alpha=0.8)
    draw_toothbrush(ax, 0.52, 0.29, angle_deg=20, scale=1.0)
    count = min((frame_idx // 32) + 1, 3)
    ax.text(0.75, 0.55, f"{count}", fontsize=50, color=BLUE, fontweight="bold",
            ha="center", va="center", alpha=0.8)
    ax.text(0.75, 0.45, "seconds", fontsize=14, color=BLUE, ha="center")
    draw_stick_figure(ax, 0.38, 0.22, scale=0.9, arm_l_angle=-30, arm_r_angle=-100)
    text_box(ax, caption)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_brush_front(frame_idx, caption):
    """Scene 5 — brush front teeth in small circles, count to ten."""
    fig, ax = new_fig()
    draw_stick_figure(ax, 0.50, 0.18, scale=1.1, arm_l_angle=-50, arm_r_angle=-130)
    oscillate = math.sin(frame_idx * 0.5) * 0.015
    draw_toothbrush(ax, 0.62 + oscillate, 0.50, angle_deg=175, scale=0.9)
    for i in range(6):
        angle = frame_idx * 0.15 + i * (2 * math.pi / 6)
        ax.plot(0.50 + 0.04 * math.cos(angle), 0.53, "o", color=BLUE, markersize=3, alpha=0.5)
    count = min((frame_idx // 10) + 1, 10)
    ax.text(0.20, 0.65, f"{count}/10", fontsize=28, color=BLUE, fontweight="bold", ha="center")
    text_box(ax, caption)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_brush_sides(frame_idx, caption):
    """Scene 6 — outer surfaces of the back teeth, count to five per side."""
    fig, ax = new_fig()
    draw_stick_figure(ax, 0.50, 0.18, scale=1.1, arm_l_angle=-50, arm_r_angle=-130)
    side = (frame_idx // 24) % 2
    draw_toothbrush(ax, 0.42 if side == 0 else 0.58, 0.50, angle_deg=175, scale=0.9)
    ax.text(0.28, 0.65, "LEFT", fontsize=20, color=BLUE if side == 0 else GREY,
            fontweight="bold", ha="center")
    ax.text(0.72, 0.65, "RIGHT", fontsize=20, color=BLUE if side == 1 else GREY,
            fontweight="bold", ha="center")
    count = min((frame_idx % 24) // 5 + 1, 5)
    ax.text(0.50, 0.78, f"{count}/5", fontsize=28, color=BLUE, fontweight="bold", ha="center")
    text_box(ax, caption)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_brush_inside(frame_idx, caption):
    """Scene 7 — inside surfaces, brush tilted vertically."""
    fig, ax = new_fig()
    draw_stick_figure(ax, 0.50, 0.18, scale=1.1, arm_l_angle=-80, arm_r_angle=-100)
    oscillate = math.sin(frame_idx * 0.4) * 0.02
    draw_toothbrush(ax, 0.50, 0.45 + oscillate, angle_deg=95, scale=0.9)
    ax.annotate("", xy=(0.50, 0.62), xytext=(0.50, 0.55),
                arrowprops={"arrowstyle": "->", "color": GREEN, "lw": 2.5})
    ax.annotate("", xy=(0.50, 0.55), xytext=(0.50, 0.62),
                arrowprops={"arrowstyle": "->", "color": GREEN, "lw": 2.5})
    ax.text(0.72, 0.60, "Up & Down\nStrokes", fontsize=14, color=GREEN, ha="center", va="center")
    text_box(ax, caption)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_brush_molars(frame_idx, caption):
    """Scene 8 — chewing surfaces, back-and-forth like a train."""
    fig, ax = new_fig()
    draw_stick_figure(ax, 0.50, 0.18, scale=1.1, arm_l_angle=-50, arm_r_angle=-130)
    x_offset = math.sin(frame_idx * 0.35) * 0.08
    draw_toothbrush(ax, 0.50 + x_offset, 0.50, angle_deg=180, scale=0.9)
    ax.plot([0.25, 0.75], [0.46, 0.46], color=DARK, lw=2, linestyle="--", alpha=0.4)
    ax.plot([0.25, 0.75], [0.44, 0.44], color=DARK, lw=2, linestyle="--", alpha=0.4)
    for tie_x in np.linspace(0.27, 0.73, 10):
        ax.plot([tie_x, tie_x], [0.43, 0.47], color=DARK, lw=3, alpha=0.3)
    ax.text(0.50, 0.38, "Like a train on a track!", fontsize=13, color="#8B5E3C",
            ha="center", style="italic")
    done = min(frame_idx // 24, 3)
    for i, q in enumerate(["Bottom L", "Bottom R", "Top L", "Top R"]):
        color = GREEN if i < done else (BLUE if i == done else GREY)
        ax.text(0.18 + (i % 2) * 0.28, 0.75 - (i // 2) * 0.10,
                ("✓ " if i < done else "") + q, fontsize=12, color=color, ha="center")
    text_box(ax, caption)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_rinse_smile(frame_idx, caption):
    """Scene 9 — rinse, look in the mirror, a bright smile."""
    fig, ax = new_fig()
    _tiled_wall(ax)
    draw_mirror(ax, 0.62, 0.38, w=0.22, h=0.38)
    draw_sink(ax, 0.55, 0.25)
    if frame_idx < 48:
        for drop in range(5):
            dy = (drop * 0.05 + frame_idx * 0.01) % 0.20
            ax.add_patch(plt.Circle((0.55, 0.32 + dy), 0.006, color=LIGHT_BLUE, alpha=0.7))
    draw_stick_figure(ax, 0.40, 0.22, scale=0.95, arm_l_angle=-60, arm_r_angle=-120, smile=True)
    draw_stick_figure(ax, 0.62, 0.38, scale=0.55, smile=True)
    draw_sparkles(ax, 0.62, 0.60, n=5, r=0.12, t=frame_idx * 0.1)
    text_box(ax, caption)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_accomplishment(frame_idx, caption):
    """Scene 10 — pride and accomplishment, ready to start the day."""
    fig, ax = new_fig()
    for i in range(16):
        angle = 2 * math.pi * i / 16 + frame_idx * 0.02
        ax.plot([0.50, 0.50 + 0.6 * math.cos(angle)], [0.50, 0.50 + 0.6 * math.sin(angle)],
                color=YELLOW, lw=4, alpha=0.15, zorder=0)
    draw_stick_figure(ax, 0.50, 0.20, scale=1.15, arm_l_angle=45, arm_r_angle=135, smile=True)
    draw_sparkles(ax, 0.50, 0.68, n=6, r=0.18, t=frame_idx * 0.12)
    ax.text(0.50, 0.88, "Ready to start the day!", transform=ax.transAxes, fontsize=22,
            ha="center", va="top", fontweight="bold", color=DARK,
            bbox={"boxstyle": "round,pad=0.4", "facecolor": YELLOW, "alpha": 0.7})
    text_box(ax, caption, y=0.04, fontsize=15)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_generic(frame_idx, caption):
    """Fallback for any scene index without bespoke art: figure + caption."""
    fig, ax = new_fig()
    draw_stick_figure(ax, 0.50, 0.30, scale=1.0, smile=True)
    text_box(ax, caption)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


# Bespoke art for the 10 narrated scenes of the demo, keyed by 1-based index.
SCENE_ART: dict[int, Callable[[int, str], np.ndarray]] = {
    1: scene_mirror,
    2: scene_grab_brush,
    3: scene_apply_paste,
    4: scene_wet_brush,
    5: scene_brush_front,
    6: scene_brush_sides,
    7: scene_brush_inside,
    8: scene_brush_molars,
    9: scene_rinse_smile,
    10: scene_accomplishment,
}


def _blend(frame: np.ndarray, other: np.ndarray, weight: float) -> np.ndarray:
    """Alpha-composite ``frame`` over ``other``: ``frame*weight + other*(1-weight)``.

    Returns a fresh ``uint8`` RGB frame; ``weight`` is the scene content's share in
    ``[0, 1]`` (the transition compositing plan's per-frame weight).
    """
    mixed = frame.astype(np.float32) * weight + other.astype(np.float32) * (1.0 - weight)
    return mixed.round().clip(0, 255).astype(np.uint8)


class MatplotlibStickFigureRenderer(SceneScriptRenderer):
    """Reference v1 renderer: silent stick-figure animation via matplotlib."""

    name = "matplotlib-stick-v1"
    supported_majors = frozenset({1})

    def _render(self, plan: RenderPlan, *, draft_path: str | None) -> RenderSafetyReport:
        """Render every scene's frames, optionally to an mp4, returning a report.

        Args:
            plan: The validated, name-reinserted render plan.
            draft_path: Where to stream the draft mp4, or ``None`` to render
                without writing a file (frames are still produced for the
                safety guard).

        Returns:
            A :class:`RenderSafetyReport` measured from the produced frames.
            Narration volume is 0.0 — this renderer produces silent video.

        Raises:
            RuntimeError: If an mp4 path is requested but ``imageio`` (with the
                ffmpeg plugin) is unavailable.
        """
        frames = self._composited_frames(plan)
        writer = self._open_writer(draft_path, plan.fps)
        luminances: list[float] = []
        try:
            for frame in frames:
                luminances.append(float(frame.mean()) / 255.0)
                if writer is not None:
                    writer.append_data(frame)
        finally:
            if writer is not None:
                writer.close()

        return RenderSafetyReport(
            fps=plan.fps,
            luminances=luminances,
            narration_volume=0.0,
            sfx_levels=[],
        )

    def _segments(self, plan: RenderPlan) -> list[list[np.ndarray]]:
        """Render each unit to its own frame list: a 1-s title card, then scenes.

        Kept as separate segments (rather than one flat stream) so scene
        transitions can blend across the boundaries between them.
        """
        title = [scene_title(f, plan.title) for f in range(plan.fps)]
        scenes = [
            [SCENE_ART.get(scene.index, scene_generic)(f, scene.caption)
             for f in range(scene.frame_count)]
            for scene in plan.scenes
        ]
        return [title, *scenes]

    def _composited_frames(self, plan: RenderPlan) -> list[np.ndarray]:
        """Apply each scene's declared transitions, then flatten to a frame list.

        The title card carries no transition; segment ``i + 1`` is ``plan.scenes[i]``.
        A fade blends toward black; a dissolve blends toward the neighbouring
        scene's *original* boundary frame (snapshotted before compositing so an
        A→B dissolve and B→A dissolve do not feed on each other's output). Frame
        counts are unchanged, so the audio timeline and safety report stay in sync.
        """
        segments = self._segments(plan)
        # Snapshot the pre-transition boundary frames each segment exposes.
        first_of = [seg[0] for seg in segments]
        last_of = [seg[-1] for seg in segments]

        for si, scene in enumerate(plan.scenes, start=1):
            seg = segments[si]
            comp_plan = composite_plan(
                len(seg), plan.fps, scene.transition_in, scene.transition_out
            )
            prev_boundary = last_of[si - 1]
            next_boundary = first_of[si + 1] if si + 1 < len(segments) else None
            for i, comp in enumerate(comp_plan):
                if comp.source is BlendSource.KEEP:
                    continue
                other = self._blend_target(comp.source, seg[i], prev_boundary, next_boundary)
                seg[i] = _blend(seg[i], other, comp.weight)

        return [frame for seg in segments for frame in seg]

    @staticmethod
    def _blend_target(
        source: BlendSource,
        frame: np.ndarray,
        prev_boundary: np.ndarray,
        next_boundary: np.ndarray | None,
    ) -> np.ndarray:
        """Resolve what a frame blends with: black, or a neighbour boundary frame.

        A dissolve with no neighbour on that side (the first scene's ``prev`` after
        the title always exists; the last scene's ``next``) falls back to black.
        """
        if source is BlendSource.PREV:
            return prev_boundary
        if source is BlendSource.NEXT and next_boundary is not None:
            return next_boundary
        return np.zeros_like(frame)  # BLACK, or a dissolve past the last scene

    @staticmethod
    def _open_writer(draft_path: str | None, fps: int):
        """Open an imageio mp4 writer, or return ``None`` when not writing."""
        if draft_path is None:
            return None
        try:
            import imageio
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise RuntimeError(
                "writing mp4 requires the 'imageio'/'imageio-ffmpeg' packages"
            ) from exc
        return imageio.get_writer(
            draft_path,
            fps=fps,
            format="ffmpeg",
            codec="libx264",
            quality=8,
            ffmpeg_log_level="quiet",
        )


def main() -> None:
    """Render the bundled demo to ``silas_shines_his_smile.mp4``."""
    from kathai_chithiram.rendering.silas_story import (
        SILAS_SCENE_SCRIPT,
        silas_mapping,
    )

    output_path = "silas_shines_his_smile.mp4"
    result = MatplotlibStickFigureRenderer().render(
        SILAS_SCENE_SCRIPT, mapping=silas_mapping(), output_path=output_path
    )
    print(f"Done! {result.plan.total_frames} frames → {output_path}")


if __name__ == "__main__":
    main()
