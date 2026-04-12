"""
generate_animation.py
Generates silas_shines_his_smile.mp4 — a stick-figure animation of the story.
Each scene holds for ~4 seconds (96 frames at 24fps).
"""

import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Arc, FancyArrowPatch
import imageio
import io

FPS = 24
SCENE_SECONDS = 4
FRAMES_PER_SCENE = FPS * SCENE_SECONDS
W, H = 960, 540          # output resolution
DPI = 96
FIG_W = W / DPI
FIG_H = H / DPI

# ── colour palette ────────────────────────────────────────────────────────────
BG       = "#F5F5F0"
DARK     = "#222222"
BLUE     = "#4A90D9"
LIGHT_BLUE = "#AED6F1"
WHITE    = "#FFFFFF"
GREY     = "#CCCCCC"
GREEN    = "#5DBB63"
YELLOW   = "#F5C518"
SKIN     = "#F4C08A"
TOOTHPASTE_BLUE = "#56B4D3"


# ── stick-figure helpers ──────────────────────────────────────────────────────

def draw_stick_figure(ax, cx, cy, scale=1.0,
                      arm_l_angle=-60, arm_r_angle=-120,
                      leg_l_angle=30, leg_r_angle=150,
                      head_tilt=0, smile=False, eyes_closed=False):
    """Draw a stick figure centred at (cx, cy) with given scale."""
    s = scale
    lw = 3 * s

    # torso
    ax.plot([cx, cx], [cy, cy + 0.30 * s], color=DARK, lw=lw, solid_capstyle='round')

    # head
    head_r = 0.10 * s
    head_cx = cx + math.sin(math.radians(head_tilt)) * 0.05 * s
    head_cy = cy + 0.30 * s + head_r + 0.01 * s
    circle = plt.Circle((head_cx, head_cy), head_r, color=SKIN, zorder=5)
    ax.add_patch(circle)
    circle_outline = plt.Circle((head_cx, head_cy), head_r, fill=False, color=DARK, lw=lw * 0.6, zorder=6)
    ax.add_patch(circle_outline)

    # hair (simple arc on top)
    hair = Arc((head_cx, head_cy), head_r * 2.1, head_r * 2.1,
               angle=0, theta1=10, theta2=170, color="#8B5E3C", lw=lw * 1.2, zorder=7)
    ax.add_patch(hair)

    # eyes
    eye_offset = head_r * 0.35
    eye_y = head_cy + head_r * 0.1
    if eyes_closed:
        ax.plot([head_cx - eye_offset - head_r * 0.12, head_cx - eye_offset + head_r * 0.12],
                [eye_y, eye_y], color=DARK, lw=lw * 0.5, zorder=8)
        ax.plot([head_cx + eye_offset - head_r * 0.12, head_cx + eye_offset + head_r * 0.12],
                [eye_y, eye_y], color=DARK, lw=lw * 0.5, zorder=8)
    else:
        for ex in [head_cx - eye_offset, head_cx + eye_offset]:
            ax.add_patch(plt.Circle((ex, eye_y), head_r * 0.12,
                                    color=DARK, zorder=8))

    # mouth
    mouth_y = head_cy - head_r * 0.35
    if smile:
        mouth_arc = Arc((head_cx, mouth_y), head_r * 0.55, head_r * 0.35,
                        angle=0, theta1=200, theta2=340, color=DARK, lw=lw * 0.6, zorder=8)
        ax.add_patch(mouth_arc)
    else:
        ax.plot([head_cx - head_r * 0.2, head_cx + head_r * 0.2],
                [mouth_y, mouth_y], color=DARK, lw=lw * 0.5, zorder=8)

    # shirt (blue rectangle over torso)
    shirt_h = 0.20 * s
    shirt_w = 0.14 * s
    shirt = patches.FancyBboxPatch(
        (cx - shirt_w / 2, cy + 0.06 * s), shirt_w, shirt_h,
        boxstyle="round,pad=0.005", color=BLUE, zorder=4)
    ax.add_patch(shirt)

    shoulder_y = cy + 0.26 * s

    # arms
    def arm_end(angle_deg):
        r = 0.22 * s
        a = math.radians(angle_deg)
        return cx + r * math.cos(a), shoulder_y + r * math.sin(a)

    lax, lay = arm_end(arm_l_angle)
    rax, ray = arm_end(arm_r_angle)
    ax.plot([cx, lax], [shoulder_y, lay], color=DARK, lw=lw, solid_capstyle='round', zorder=3)
    ax.plot([cx, rax], [shoulder_y, ray], color=DARK, lw=lw, solid_capstyle='round', zorder=3)

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
    ax.plot([cx, llx], [hip_y, lly], color=DARK, lw=lw, solid_capstyle='round', zorder=3)
    ax.plot([cx, rlx], [hip_y, rly], color=DARK, lw=lw, solid_capstyle='round', zorder=3)

    # feet (small horizontal lines)
    foot_len = 0.06 * s
    ax.plot([llx, llx - foot_len], [lly, lly], color=DARK, lw=lw * 0.8, solid_capstyle='round')
    ax.plot([rlx, rlx + foot_len], [rly, rly], color=DARK, lw=lw * 0.8, solid_capstyle='round')

    return head_cx, head_cy, head_r


def draw_mirror(ax, x, y, w=0.18, h=0.28):
    frame = patches.FancyBboxPatch((x - w / 2, y), w, h,
                                   boxstyle="round,pad=0.01",
                                   edgecolor=GREY, facecolor=LIGHT_BLUE,
                                   lw=3, alpha=0.6, zorder=2)
    ax.add_patch(frame)


def draw_sink(ax, x, y, w=0.45, h=0.12):
    sink = patches.FancyBboxPatch((x - w / 2, y), w, h,
                                  boxstyle="round,pad=0.015",
                                  edgecolor=GREY, facecolor=WHITE, lw=2, zorder=2)
    ax.add_patch(sink)
    # faucet
    faucet_x = x
    ax.plot([faucet_x, faucet_x], [y + h, y + h + 0.07], color=GREY, lw=4)
    ax.plot([faucet_x - 0.04, faucet_x + 0.04], [y + h + 0.07, y + h + 0.07], color=GREY, lw=4)


def draw_toothbrush(ax, x, y, angle_deg=45, scale=1.0):
    s = scale
    length = 0.18 * s
    a = math.radians(angle_deg)
    ex = x + length * math.cos(a)
    ey = y + length * math.sin(a)
    ax.plot([x, ex], [y, ey], color=BLUE, lw=5 * s, solid_capstyle='round', zorder=6)
    # bristles at the tip
    for i in range(5):
        offset = (i - 2) * 0.008 * s
        bx = ex + 0.025 * s * math.cos(a) + offset * math.cos(a + math.pi / 2)
        by = ey + 0.025 * s * math.sin(a) + offset * math.sin(a + math.pi / 2)
        ax.plot([ex + offset * math.cos(a + math.pi / 2),
                 bx],
                [ey + offset * math.sin(a + math.pi / 2),
                 by],
                color=WHITE, lw=1.5, zorder=7)


def draw_toothpaste(ax, x, y, scale=1.0):
    s = scale
    tube = patches.FancyBboxPatch((x - 0.03 * s, y), 0.06 * s, 0.16 * s,
                                  boxstyle="round,pad=0.005",
                                  facecolor=GREEN, edgecolor=DARK, lw=1.5, zorder=6)
    ax.add_patch(tube)
    # stripe
    ax.add_patch(patches.FancyBboxPatch((x - 0.03 * s, y + 0.06 * s), 0.06 * s, 0.02 * s,
                                        boxstyle="square,pad=0",
                                        facecolor=WHITE, edgecolor="none", zorder=7))


def draw_sparkles(ax, cx, cy, n=4, r=0.12, t=0.0):
    """Draw animated sparkle stars around (cx, cy)."""
    for i in range(n):
        angle = 2 * math.pi * i / n + t
        sx = cx + r * math.cos(angle)
        sy = cy + r * math.sin(angle)
        ax.plot(sx, sy, '*', color=YELLOW, markersize=14, zorder=10)


def text_box(ax, text, x=0.5, y=0.08, fontsize=16):
    ax.text(x, y, text, transform=ax.transAxes,
            fontsize=fontsize, ha='center', va='bottom',
            wrap=True,
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                      edgecolor=GREY, alpha=0.9),
            color=DARK, family='DejaVu Sans')


def new_fig():
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect('equal')
    ax.axis('off')
    return fig, ax


def fig_to_rgb(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=DPI, bbox_inches='tight',
                pad_inches=0, facecolor=fig.get_facecolor())
    buf.seek(0)
    from PIL import Image
    img = Image.open(buf).convert('RGB').resize((W, H))
    return np.array(img)


# ── scene builders ─────────────────────────────────────────────────────────────

def scene_title(frame_idx):
    fig, ax = new_fig()
    # background gradient effect
    for i in range(20):
        alpha = 0.03
        rect = patches.Rectangle((0, i / 20), 1, 1 / 20,
                                  color=LIGHT_BLUE, alpha=alpha * (i / 20), zorder=0)
        ax.add_patch(rect)

    ax.text(0.5, 0.62, "Silas Shines His Smile",
            transform=ax.transAxes, fontsize=30, ha='center', va='center',
            fontweight='bold', color=DARK, family='DejaVu Sans')
    ax.text(0.5, 0.50, "By Sivakumar Mambakkam",
            transform=ax.transAxes, fontsize=16, ha='center', va='center',
            color='#555555', family='DejaVu Sans', style='italic')

    # simple toothbrush icon under title
    draw_toothbrush(ax, 0.42, 0.30, angle_deg=30, scale=1.5)
    draw_sparkles(ax, 0.58, 0.38, n=3, r=0.07, t=frame_idx * 0.08)

    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_mirror(frame_idx):
    """Scene 1 — Silas at the mirror, takes a deep breath."""
    fig, ax = new_fig()
    # bathroom wall tiles
    for row in range(6):
        for col in range(10):
            tile = patches.FancyBboxPatch((col * 0.1 + 0.005, row * 0.17 + 0.005),
                                          0.09, 0.16,
                                          boxstyle="round,pad=0.003",
                                          facecolor='#E8E8E8', edgecolor=GREY,
                                          lw=0.8, alpha=0.4, zorder=0)
            ax.add_patch(tile)

    draw_mirror(ax, 0.55, 0.40, w=0.22, h=0.35)
    draw_sink(ax, 0.50, 0.25)

    # reflection in mirror (smaller figure)
    draw_stick_figure(ax, 0.55, 0.40, scale=0.6, smile=True)

    # main figure
    draw_stick_figure(ax, 0.42, 0.22, scale=0.9,
                      arm_l_angle=-70, arm_r_angle=-110)

    # breath indicator — small circles emanating
    for i in range(3):
        offset = i * 0.025 + (frame_idx % 8) * 0.003
        circle = plt.Circle((0.38, 0.58 + offset), 0.008 + i * 0.004,
                             fill=False, color=LIGHT_BLUE, lw=1.2, alpha=0.7 - i * 0.2)
        ax.add_patch(circle)

    text_box(ax, "Silas stands at the sink and takes\na deep breath to centre himself.")
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_grab_brush(frame_idx):
    """Scene 2 — Grasps toothbrush with full-hand grip."""
    fig, ax = new_fig()
    for row in range(6):
        for col in range(10):
            tile = patches.FancyBboxPatch((col * 0.1 + 0.005, row * 0.17 + 0.005),
                                          0.09, 0.16,
                                          boxstyle="round,pad=0.003",
                                          facecolor='#E8E8E8', edgecolor=GREY,
                                          lw=0.8, alpha=0.4, zorder=0)
            ax.add_patch(tile)

    draw_sink(ax, 0.50, 0.25)
    draw_toothbrush(ax, 0.70, 0.30, angle_deg=80, scale=1.0)
    draw_toothpaste(ax, 0.78, 0.30, scale=0.9)

    draw_stick_figure(ax, 0.42, 0.22, scale=0.9,
                      arm_l_angle=-30, arm_r_angle=-130,
                      smile=True)

    # label: full-hand grip
    ax.annotate("Full-hand grip", xy=(0.70, 0.33), xytext=(0.55, 0.60),
                fontsize=11, color=BLUE,
                arrowprops=dict(arrowstyle='->', color=BLUE, lw=1.5),
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    text_box(ax, "He uses a full-hand grip to hold\nthe toothbrush securely.")
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_apply_paste(frame_idx):
    """Scene 3 — Rest brush on sink, apply pea-sized paste."""
    fig, ax = new_fig()
    for row in range(6):
        for col in range(10):
            tile = patches.FancyBboxPatch((col * 0.1 + 0.005, row * 0.17 + 0.005),
                                          0.09, 0.16,
                                          boxstyle="round,pad=0.003",
                                          facecolor='#E8E8E8', edgecolor=GREY,
                                          lw=0.8, alpha=0.4, zorder=0)
            ax.add_patch(tile)

    draw_sink(ax, 0.55, 0.28)
    # brush resting on sink edge
    draw_toothbrush(ax, 0.48, 0.37, angle_deg=10, scale=1.0)
    # paste drop on brush
    paste_dot = plt.Circle((0.66, 0.375), 0.018, color=TOOTHPASTE_BLUE, zorder=8)
    ax.add_patch(paste_dot)

    # toothpaste tube being squeezed
    draw_toothpaste(ax, 0.74, 0.38, scale=0.8)
    # squeeze arrow
    ax.annotate("", xy=(0.68, 0.38), xytext=(0.73, 0.44),
                arrowprops=dict(arrowstyle='->', color=GREEN, lw=2.0))

    draw_stick_figure(ax, 0.38, 0.22, scale=0.9,
                      arm_l_angle=-20, arm_r_angle=-140)

    ax.text(0.66, 0.42, "pea-sized!", fontsize=10, color=TOOTHPASTE_BLUE,
            ha='center', style='italic')

    text_box(ax, "He rests the brush on the sink and\nsqueezes a pea-sized amount of paste.")
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_wet_brush(frame_idx):
    """Scene 4 — Wet brush under cool water, count 1-2-3."""
    fig, ax = new_fig()
    for row in range(6):
        for col in range(10):
            tile = patches.FancyBboxPatch((col * 0.1 + 0.005, row * 0.17 + 0.005),
                                          0.09, 0.16,
                                          boxstyle="round,pad=0.003",
                                          facecolor='#E8E8E8', edgecolor=GREY,
                                          lw=0.8, alpha=0.4, zorder=0)
            ax.add_patch(tile)

    draw_sink(ax, 0.55, 0.25)
    # water stream
    for drop in range(6):
        dy = drop * 0.04 + (frame_idx % 6) * 0.008
        ax.plot([0.555, 0.555 + drop * 0.001], [0.32 + dy, 0.32 + dy + 0.03],
                color=LIGHT_BLUE, lw=2, alpha=0.8)

    draw_toothbrush(ax, 0.52, 0.29, angle_deg=20, scale=1.0)

    # count indicator
    count = (frame_idx // 32) + 1
    count = min(count, 3)
    ax.text(0.75, 0.55, f"{count}", fontsize=50, color=BLUE,
            fontweight='bold', ha='center', va='center', alpha=0.8)
    ax.text(0.75, 0.45, "seconds", fontsize=14, color=BLUE, ha='center')

    draw_stick_figure(ax, 0.38, 0.22, scale=0.9,
                      arm_l_angle=-30, arm_r_angle=-100)

    text_box(ax, "He holds the brush under cool water\nfor three seconds — one, two, three.")
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_brush_front(frame_idx):
    """Scene 5 — Brush front teeth in small circles, count to 10."""
    fig, ax = new_fig()
    draw_stick_figure(ax, 0.50, 0.18, scale=1.1,
                      arm_l_angle=-50, arm_r_angle=-130,
                      smile=False)

    # brush at mouth
    oscillate = math.sin(frame_idx * 0.5) * 0.015
    draw_toothbrush(ax, 0.62 + oscillate, 0.50, angle_deg=175, scale=0.9)

    # circular motion arrows
    for i in range(6):
        angle = frame_idx * 0.15 + i * (2 * math.pi / 6)
        cx_c, cy_c = 0.50 + 0.04 * math.cos(angle), 0.53
        ax.plot(cx_c, cy_c, 'o', color=BLUE, markersize=3, alpha=0.5)

    # count
    count = min((frame_idx // 10) + 1, 10)
    ax.text(0.20, 0.65, f"{count}/10", fontsize=28, color=BLUE,
            fontweight='bold', ha='center')

    text_box(ax, "Small circles on the front teeth — he counts slowly to 10.")
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_brush_sides(frame_idx):
    """Scene 6 — Outer surfaces of back teeth, count to 5 per side."""
    fig, ax = new_fig()
    draw_stick_figure(ax, 0.50, 0.18, scale=1.1,
                      arm_l_angle=-50, arm_r_angle=-130)

    # brush sliding left-right
    side = (frame_idx // 24) % 2
    brush_x = 0.42 if side == 0 else 0.58
    draw_toothbrush(ax, brush_x, 0.50, angle_deg=175, scale=0.9)

    # left / right labels
    left_col  = BLUE if side == 0 else GREY
    right_col = BLUE if side == 1 else GREY
    ax.text(0.28, 0.65, "LEFT", fontsize=20, color=left_col, fontweight='bold', ha='center')
    ax.text(0.72, 0.65, "RIGHT", fontsize=20, color=right_col, fontweight='bold', ha='center')

    count = min((frame_idx % 24) // 5 + 1, 5)
    ax.text(0.50, 0.78, f"{count}/5", fontsize=28, color=BLUE,
            fontweight='bold', ha='center')

    text_box(ax, "Side teeth — left side, count to 5. Right side, count to 5.")
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_brush_inside(frame_idx):
    """Scene 7 — Inside surfaces, brush tilted vertically."""
    fig, ax = new_fig()
    draw_stick_figure(ax, 0.50, 0.18, scale=1.1,
                      arm_l_angle=-80, arm_r_angle=-100)

    # brush tilted vertically
    oscillate = math.sin(frame_idx * 0.4) * 0.02
    draw_toothbrush(ax, 0.50, 0.45 + oscillate, angle_deg=95, scale=0.9)

    # up-down arrows
    ax.annotate("", xy=(0.50, 0.62), xytext=(0.50, 0.55),
                arrowprops=dict(arrowstyle='->', color=GREEN, lw=2.5))
    ax.annotate("", xy=(0.50, 0.55), xytext=(0.50, 0.62),
                arrowprops=dict(arrowstyle='->', color=GREEN, lw=2.5))

    ax.text(0.72, 0.60, "Up & Down\nStrokes", fontsize=14, color=GREEN,
            ha='center', va='center')

    text_box(ax, "He tilts the brush vertically for the\ninside surfaces — short up-and-down strokes.")
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_brush_molars(frame_idx):
    """Scene 8 — Chewing surfaces, back-and-forth like a train."""
    fig, ax = new_fig()
    draw_stick_figure(ax, 0.50, 0.18, scale=1.1,
                      arm_l_angle=-50, arm_r_angle=-130)

    # brush horizontal, moving back and forth
    x_offset = math.sin(frame_idx * 0.35) * 0.08
    draw_toothbrush(ax, 0.50 + x_offset, 0.50, angle_deg=180, scale=0.9)

    # train track illustration
    ax.plot([0.25, 0.75], [0.46, 0.46], color=DARK, lw=2, linestyle='--', alpha=0.4)
    ax.plot([0.25, 0.75], [0.44, 0.44], color=DARK, lw=2, linestyle='--', alpha=0.4)
    for tie_x in np.linspace(0.27, 0.73, 10):
        ax.plot([tie_x, tie_x], [0.43, 0.47], color=DARK, lw=3, alpha=0.3)

    ax.text(0.50, 0.38, "Like a train on a track!", fontsize=13,
            color='#8B5E3C', ha='center', style='italic')

    # quadrant labels
    quadrants = ["Bottom L", "Bottom R", "Top L", "Top R"]
    done = min((frame_idx // 24), 3)
    for i, q in enumerate(quadrants):
        color = GREEN if i < done else (BLUE if i == done else GREY)
        ax.text(0.18 + (i % 2) * 0.28, 0.75 - (i // 2) * 0.10,
                ("✓ " if i < done else "") + q,
                fontsize=12, color=color, ha='center')

    text_box(ax, "Back-and-forth on the molars — like a train on a track.")
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_rinse_smile(frame_idx):
    """Scene 9 — Rinse, return brush, look in mirror, bright smile."""
    fig, ax = new_fig()
    for row in range(6):
        for col in range(10):
            tile = patches.FancyBboxPatch((col * 0.1 + 0.005, row * 0.17 + 0.005),
                                          0.09, 0.16,
                                          boxstyle="round,pad=0.003",
                                          facecolor='#E8E8E8', edgecolor=GREY,
                                          lw=0.8, alpha=0.4, zorder=0)
            ax.add_patch(tile)

    draw_mirror(ax, 0.62, 0.38, w=0.22, h=0.38)
    draw_sink(ax, 0.55, 0.25)

    # water droplets (rinsing)
    if frame_idx < 48:
        for drop in range(5):
            dy = (drop * 0.05 + frame_idx * 0.01) % 0.20
            ax.add_patch(plt.Circle((0.55, 0.32 + dy), 0.006,
                                    color=LIGHT_BLUE, alpha=0.7))

    # figure with smile
    draw_stick_figure(ax, 0.40, 0.22, scale=0.95,
                      arm_l_angle=-60, arm_r_angle=-120,
                      smile=True)

    # reflection in mirror — smiling
    draw_stick_figure(ax, 0.62, 0.38, scale=0.55, smile=True)

    # sparkles around mirror
    draw_sparkles(ax, 0.62, 0.60, n=5, r=0.12, t=frame_idx * 0.1)

    text_box(ax, "He rinses the brush, looks in the mirror\nand sees his bright smile!")
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


def scene_accomplishment(frame_idx):
    """Scene 10 — Pride, accomplishment, ready to start the day."""
    fig, ax = new_fig()

    # sunburst background
    for i in range(16):
        angle = 2 * math.pi * i / 16 + frame_idx * 0.02
        ax.plot([0.50, 0.50 + 0.6 * math.cos(angle)],
                [0.50, 0.50 + 0.6 * math.sin(angle)],
                color=YELLOW, lw=4, alpha=0.15, zorder=0)

    # big smile figure, arms raised in triumph
    draw_stick_figure(ax, 0.50, 0.20, scale=1.15,
                      arm_l_angle=45, arm_r_angle=135,
                      smile=True)

    # sparkles all around
    draw_sparkles(ax, 0.50, 0.68, n=6, r=0.18, t=frame_idx * 0.12)

    ax.text(0.50, 0.88, "Ready to start the day!",
            transform=ax.transAxes, fontsize=22, ha='center', va='top',
            fontweight='bold', color=DARK,
            bbox=dict(boxstyle='round,pad=0.4', facecolor=YELLOW, alpha=0.7))

    text_box(ax,
             "Teeth clean, mind calm — Silas feels proud\nand ready to shine his smile all day!",
             y=0.04, fontsize=15)
    img = fig_to_rgb(fig)
    plt.close(fig)
    return img


# ── scene registry ────────────────────────────────────────────────────────────

SCENES = [
    ("Title",           scene_title),
    ("At the mirror",   scene_mirror),
    ("Grab brush",      scene_grab_brush),
    ("Apply paste",     scene_apply_paste),
    ("Wet the brush",   scene_wet_brush),
    ("Brush front",     scene_brush_front),
    ("Brush sides",     scene_brush_sides),
    ("Brush inside",    scene_brush_inside),
    ("Brush molars",    scene_brush_molars),
    ("Rinse & smile",   scene_rinse_smile),
    ("Accomplishment",  scene_accomplishment),
]


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import imageio.v3 as iio
    from imageio_ffmpeg import get_ffmpeg_exe

    output_path = "silas_shines_his_smile.mp4"
    total = len(SCENES) * FRAMES_PER_SCENE
    print(f"Generating {len(SCENES)} scenes × {FRAMES_PER_SCENE} frames = {total} frames "
          f"at {FPS}fps → ~{total//FPS}s video")

    writer = imageio.get_writer(
        output_path,
        fps=FPS,
        format='ffmpeg',
        codec='libx264',
        quality=8,
        ffmpeg_log_level='quiet',
    )

    for scene_idx, (scene_name, scene_fn) in enumerate(SCENES):
        print(f"  Scene {scene_idx + 1}/{len(SCENES)}: {scene_name}")
        for f in range(FRAMES_PER_SCENE):
            frame = scene_fn(f)
            writer.append_data(frame)

    writer.close()
    print(f"\nDone! Saved to: {output_path}")
