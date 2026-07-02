"""Blender Grease-Pencil renderer (reference renderer v2).

Consumes the scene-script contract through
:class:`kathai_chithiram.rendering.SceneScriptRenderer`: the script is validated,
the child's display name is reinserted at render time, and captions / timing /
title come from the plan.

Like the matplotlib reference renderer, art is **content-driven**: the
hand-authored demo ("…Shines His Smile") keeps its bespoke per-scene builders, and
every other story is drawn from an art hint (setting → backdrop, caption →
props/figure expression/gesture) shared with the matplotlib path
(:mod:`kathai_chithiram.rendering.scene_art_hints`). Scene **transitions** render
too: each scene's declared fade/dissolve is drawn as a keyframed black-overlay
opacity from the shared :func:`~kathai_chithiram.rendering.transitions.composite_plan`
(dissolve is a soft fade-through-black for now; a true crossfade is a follow-up).
The render-time safety report is structural (calm by construction — fixed palette,
no audio, gentle fades).

``bpy`` is only available inside Blender, so it is imported lazily; this module
imports fine anywhere, but actually rendering requires Blender::

    blender --background --python blender_animation.py
"""

from __future__ import annotations

import math
from typing import Any

from kathai_chithiram.rendering.pipeline import RenderPlan, SceneScriptRenderer
from kathai_chithiram.rendering.safety import RenderSafetyReport
from kathai_chithiram.rendering.scene_art_hints import (
    Background,
    Expression,
    Gesture,
    art_hint_for,
    resolve_figure_cues,
)
from kathai_chithiram.rendering.transitions import BlendSource, composite_plan

#: Lazily-bound Blender module; ``None`` until :func:`_load_bpy` runs.
bpy: Any = None

#: Nominal per-scene frame budget used for internal sub-timing of animations.
SCENE_FRAMES = 96
RESOLUTION = (1280, 720)


def _load_bpy() -> Any:
    """Import and cache ``bpy``; raise a clear error when not inside Blender.

    Returns:
        The ``bpy`` module.

    Raises:
        RuntimeError: If ``bpy`` cannot be imported (i.e. not running in
            Blender).
    """
    global bpy
    if bpy is None:
        try:
            import bpy as _bpy
        except ImportError as exc:
            raise RuntimeError(
                "the Blender renderer requires Blender's 'bpy'; run via "
                "'blender --background --python blender_animation.py'"
            ) from exc
        bpy = _bpy
    return bpy


# ── palette ──────────────────────────────────────────────────────────────────


def rgb(r: int, g: int, b: int, a: float = 1.0) -> tuple[float, float, float, float]:
    """Return a 0–1 RGBA tuple from 0–255 components."""
    return (r / 255, g / 255, b / 255, a)


COL_BG = rgb(245, 245, 240)
COL_DARK = rgb(30, 30, 30)
COL_BLUE = rgb(74, 144, 217)
COL_LBLUE = rgb(174, 214, 241)
COL_GREEN = rgb(93, 187, 99)
COL_YELLOW = rgb(245, 197, 24)
COL_SKIN = rgb(244, 192, 138)
COL_HAIR = rgb(139, 94, 60)
COL_SHIRT = rgb(74, 144, 217)
COL_WHITE = rgb(255, 255, 255)
COL_GREY = rgb(180, 180, 180)
COL_PASTE = rgb(86, 180, 211)
COL_BROWN = rgb(139, 94, 60)
COL_RED = rgb(217, 83, 79)
COL_BOARD = rgb(62, 107, 87)


# ── scene / render setup ───────────────────────────────────────────────────────


def setup_render(fps: int, output_path: str) -> None:
    """Configure the Blender scene's render settings, camera, and lighting."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = RESOLUTION[0]
    scene.render.resolution_y = RESOLUTION[1]
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.filepath = output_path

    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs[0].default_value = (*COL_BG[:3], 1)

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 10.0
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    cam_obj.location = (0, -10, 0)
    cam_obj.rotation_euler = (math.radians(90), 0, 0)

    light_data = bpy.data.lights.new("Light", type="SUN")
    light_data.energy = 3
    light_obj = bpy.data.objects.new("Light", light_data)
    scene.collection.objects.link(light_obj)
    light_obj.location = (5, -5, 10)


# ── Grease-Pencil helpers ──────────────────────────────────────────────────────


def new_gp(name: str):
    """Create and link a new Grease Pencil object; return (obj, data)."""
    gp_data = bpy.data.grease_pencils.new(name)
    gp_obj = bpy.data.objects.new(name, gp_data)
    bpy.context.scene.collection.objects.link(gp_obj)
    gp_obj.location = (0, 0, 0)
    return gp_obj, gp_data


def gp_material(name, color, use_fill=False, fill_color=None):
    """Create a Grease Pencil material."""
    mat = bpy.data.materials.new(name)
    bpy.data.materials.create_gpencil_data(mat)
    mat.grease_pencil.color = color
    mat.grease_pencil.show_stroke = True
    if use_fill and fill_color:
        mat.grease_pencil.show_fill = True
        mat.grease_pencil.fill_color = fill_color
    return mat


def add_stroke(layer, frame_number, points_2d, pressure=1.0, line_width=50, mat_index=0):
    """Add a stroke to a GP layer at the given frame (z = 0 plane)."""
    frame = None
    for f in layer.frames:
        if f.frame_number == frame_number:
            frame = f
            break
    if frame is None:
        frame = layer.frames.new(frame_number)

    stroke = frame.strokes.new()
    stroke.material_index = mat_index
    stroke.line_width = line_width
    stroke.points.add(len(points_2d))
    for i, (x, y) in enumerate(points_2d):
        stroke.points[i].co = (x, 0, y)
        stroke.points[i].pressure = pressure
        stroke.points[i].strength = 1.0
    return stroke


def circle_points(cx, cy, r, n=32):
    """Return points tracing a circle."""
    return [
        (cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n + 1)
    ]


def arc_points(cx, cy, r, a1_deg, a2_deg, n=16):
    """Return points tracing an arc between two angles."""
    pts = []
    for i in range(n + 1):
        a = math.radians(a1_deg + (a2_deg - a1_deg) * i / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


class FigureBuilder:
    """Builds a complete stick figure as a single GP object on one frame."""

    def __init__(self, name, cx, cy, scale=1.0, smile=False):
        self.gp_obj, self.gp_data = new_gp(name)
        s = scale

        self.gp_data.materials.append(gp_material(f"{name}_dark", COL_DARK))
        self.gp_data.materials.append(
            gp_material(f"{name}_skin", COL_DARK, use_fill=True, fill_color=COL_SKIN)
        )
        self.gp_data.materials.append(
            gp_material(f"{name}_shirt", COL_DARK, use_fill=True, fill_color=COL_SHIRT)
        )
        self.gp_data.materials.append(gp_material(f"{name}_hair", COL_HAIR))

        layer = self.gp_data.layers.new("fig", set_active=True)
        f = 1

        head_r = 0.5 * s
        head_cx, head_cy = cx, cy + 2.4 * s
        add_stroke(layer, f, circle_points(head_cx, head_cy, head_r), line_width=40, mat_index=1)
        add_stroke(layer, f, arc_points(head_cx, head_cy, head_r * 1.05, 20, 160, n=20),
                   line_width=60, mat_index=3)
        for ex in [head_cx - 0.18 * s, head_cx + 0.18 * s]:
            add_stroke(layer, f, circle_points(ex, head_cy + 0.08 * s, 0.07 * s, n=12),
                       line_width=60, mat_index=0)
        if smile:
            add_stroke(layer, f, arc_points(head_cx, head_cy - 0.10 * s, 0.20 * s, 200, 340, n=12),
                       line_width=35, mat_index=0)
        else:
            add_stroke(layer, f, [(head_cx - 0.15 * s, head_cy - 0.18 * s),
                                  (head_cx + 0.15 * s, head_cy - 0.18 * s)],
                       line_width=30, mat_index=0)

        torso_pts = [
            (cx - 0.30 * s, cy + 0.50 * s),
            (cx - 0.30 * s, cy + 1.80 * s),
            (cx + 0.30 * s, cy + 1.80 * s),
            (cx + 0.30 * s, cy + 0.50 * s),
            (cx - 0.30 * s, cy + 0.50 * s),
        ]
        add_stroke(layer, f, torso_pts, line_width=35, mat_index=2)
        add_stroke(layer, f, [(cx, cy + 1.80 * s), (cx, cy + 1.90 * s)],
                   line_width=40, mat_index=1)

        shoulder_y = cy + 1.70 * s
        add_stroke(layer, f, [(cx - 0.30 * s, shoulder_y), (cx - 0.60 * s, shoulder_y - 0.70 * s),
                              (cx - 0.55 * s, shoulder_y - 1.20 * s)], line_width=40, mat_index=0)
        add_stroke(layer, f, [(cx + 0.30 * s, shoulder_y), (cx + 0.60 * s, shoulder_y - 0.70 * s),
                              (cx + 0.55 * s, shoulder_y - 1.20 * s)], line_width=40, mat_index=0)
        for hx, hy in [(cx - 0.55 * s, shoulder_y - 1.20 * s),
                       (cx + 0.55 * s, shoulder_y - 1.20 * s)]:
            add_stroke(layer, f, circle_points(hx, hy, 0.10 * s, n=10), line_width=25, mat_index=1)

        hip_y = cy + 0.50 * s
        add_stroke(layer, f, [(cx, hip_y), (cx - 0.30 * s, hip_y - 0.80 * s),
                              (cx - 0.25 * s, hip_y - 1.50 * s)], line_width=40, mat_index=0)
        add_stroke(layer, f, [(cx, hip_y), (cx + 0.30 * s, hip_y - 0.80 * s),
                              (cx + 0.25 * s, hip_y - 1.50 * s)], line_width=40, mat_index=0)
        for fx, fy in [(cx - 0.25 * s, hip_y - 1.50 * s), (cx + 0.25 * s, hip_y - 1.50 * s)]:
            sign = -1 if fx < cx else 1
            add_stroke(layer, f, [(fx, fy), (fx + sign * 0.30 * s, fy)],
                       line_width=40, mat_index=0)

        self.obj = self.gp_obj


def figure_at(name, cx, cy, scale=1.0, smile=False, frame=1, loc_z=0):
    """Build a figure and keyframe its location at the given frame."""
    fb = FigureBuilder(name, cx, cy, scale=scale, smile=smile)
    obj = fb.obj
    obj.location = (0, 0, loc_z)
    obj.keyframe_insert("location", frame=frame)
    return obj


# ── prop / environment helpers ─────────────────────────────────────────────────


def gp_rect(name, x, y, w, h, fill_color, stroke_color=None, frame=1, z=0):
    """Draw a filled rectangle as a GP object."""
    gp_obj, gp_data = new_gp(name)
    sc = stroke_color or COL_DARK
    gp_data.materials.append(gp_material(f"{name}_fill", sc, use_fill=True, fill_color=fill_color))
    layer = gp_data.layers.new("l", set_active=True)
    add_stroke(layer, frame, [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)],
               line_width=30, mat_index=0)
    gp_obj.location = (0, 0, z)
    return gp_obj


def gp_circle(name, cx, cy, r, fill_color, stroke_color=None, frame=1, z=0, n=32):
    """Draw a filled circle as a GP object."""
    gp_obj, gp_data = new_gp(name)
    sc = stroke_color or COL_DARK
    gp_data.materials.append(gp_material(f"{name}_fill", sc, use_fill=True, fill_color=fill_color))
    layer = gp_data.layers.new("l", set_active=True)
    add_stroke(layer, frame, circle_points(cx, cy, r, n=n), line_width=30, mat_index=0)
    gp_obj.location = (0, 0, z)
    return gp_obj


def add_text(text, x, y, size=0.45, color=COL_DARK, name="Text"):
    """Add an emissive text object centred at (x, y)."""
    bpy.ops.object.text_add(location=(x, 0, y))
    txt_obj = bpy.context.object
    txt_obj.name = name
    txt_obj.data.body = text
    txt_obj.data.size = size
    txt_obj.data.align_x = "CENTER"
    txt_obj.rotation_euler = (math.radians(90), 0, 0)
    mat = bpy.data.materials.new(f"{name}_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color[:3], 1)
        bsdf.inputs["Emission Color"].default_value = (*color[:3], 1)
        bsdf.inputs["Emission Strength"].default_value = 2.0
    txt_obj.data.materials.append(mat)
    txt_obj.location = (x, 0, y)
    return txt_obj


def subtitle_card(text, frame_start, frame_end, z=-3.0):
    """Semi-transparent white card + dark caption text at the bottom."""
    card = gp_rect("SubCard", -5.5, z - 0.45, 11, 0.90, fill_color=(*COL_WHITE[:3], 0.85),
                   stroke_color=COL_GREY, frame=frame_start)
    hide_at(card, frame_end)
    txt = add_text(text, 0, z, size=0.38, color=COL_DARK, name=f"Sub_{frame_start}")
    hide_at(txt, frame_end)
    return card, txt


def hide_at(obj, frame):
    """Keyframe an object to become hidden at the given frame."""
    obj.hide_viewport = False
    obj.hide_render = False
    obj.keyframe_insert("hide_viewport", frame=frame - 1)
    obj.keyframe_insert("hide_render", frame=frame - 1)
    obj.hide_viewport = True
    obj.hide_render = True
    obj.keyframe_insert("hide_viewport", frame=frame)
    obj.keyframe_insert("hide_render", frame=frame)


def show_between(obj, frame_start, frame_end):
    """Keyframe an object visible only within [frame_start, frame_end)."""
    obj.hide_viewport = True
    obj.hide_render = True
    obj.keyframe_insert("hide_viewport", frame=1)
    obj.keyframe_insert("hide_render", frame=1)
    obj.hide_viewport = False
    obj.hide_render = False
    obj.keyframe_insert("hide_viewport", frame=frame_start)
    obj.keyframe_insert("hide_render", frame=frame_start)
    obj.hide_viewport = True
    obj.hide_render = True
    obj.keyframe_insert("hide_viewport", frame=frame_end)
    obj.keyframe_insert("hide_render", frame=frame_end)


def bathroom_wall(frame_start, frame_end):
    """Tiled bathroom wall backdrop."""
    for row in range(5):
        for col in range(9):
            tile = gp_rect(f"tile_{row}_{col}", -4.8 + col * 1.1, -3.5 + row * 1.4, 1.0, 1.3,
                           fill_color=(*COL_WHITE[:3], 1), stroke_color=COL_GREY,
                           frame=frame_start)
            show_between(tile, frame_start, frame_end)


def mirror_prop(frame_start, frame_end, cx=2.5, cy=0.5):
    """Wall mirror prop."""
    m = gp_rect("Mirror", cx - 1.1, cy - 0.2, 2.2, 2.8, fill_color=COL_LBLUE,
                stroke_color=COL_GREY, frame=frame_start)
    show_between(m, frame_start, frame_end)


def sink_prop(frame_start, frame_end, cx=0.0, cy=-2.5):
    """Sink prop."""
    s = gp_rect("Sink", cx - 2.2, cy, 4.4, 0.7, fill_color=COL_WHITE, stroke_color=COL_GREY,
                frame=frame_start)
    show_between(s, frame_start, frame_end)


def toothbrush_prop(name, x, y, frame_start, frame_end):
    """Toothbrush prop."""
    tb = gp_rect(name, x, y, 1.5, 0.25, fill_color=COL_BLUE, stroke_color=COL_DARK,
                 frame=frame_start)
    show_between(tb, frame_start, frame_end)


def toothpaste_prop(name, x, y, frame_start, frame_end):
    """Toothpaste prop."""
    tp = gp_rect(name, x, y, 0.5, 1.4, fill_color=COL_GREEN, stroke_color=COL_DARK,
                 frame=frame_start)
    show_between(tp, frame_start, frame_end)


def sparkle(name, cx, cy, frame_start, frame_end):
    """Small sparkle accent."""
    sp = gp_circle(name, cx, cy, 0.15, fill_color=COL_YELLOW, stroke_color=COL_YELLOW,
                   frame=frame_start, n=5)
    show_between(sp, frame_start, frame_end)


def _moving_brush(name, frame_start, frame_end, step, pose):
    """Create a brush that re-keys its stroke each ``step`` frames via ``pose``.

    ``pose(kf)`` returns a list of stroke points for keyframe ``kf``.
    """
    gp_data = bpy.data.grease_pencils.new(name)
    gp_obj = bpy.data.objects.new(name, gp_data)
    bpy.context.scene.collection.objects.link(gp_obj)
    gp_data.materials.append(gp_material(f"{name}_mat", COL_BLUE, use_fill=True,
                                         fill_color=COL_BLUE))
    layer = gp_data.layers.new("l", set_active=True)
    for kf in range(frame_start, frame_end, step):
        frm = layer.frames.new(kf)
        stroke = frm.strokes.new()
        stroke.line_width = 80
        pts = pose(kf)
        stroke.points.add(len(pts))
        for i, (px, pz) in enumerate(pts):
            stroke.points[i].co = (px, 0, pz)
            stroke.points[i].pressure = 1.0
    show_between(gp_obj, frame_start, frame_end)


# ── scene builders (caption + frame range supplied by the render plan) ────────


def build_scene_title(fs, fe, title):
    """Title card; the story title comes from the plan."""
    show_between(add_text(title, 0, 1.2, size=0.65, color=COL_DARK, name="Title_main"), fs, fe)
    show_between(add_text("Kathai Chithiram", 0, 0.3, size=0.38, color=COL_GREY,
                          name="Title_sub"), fs, fe)
    toothbrush_prop("Title_brush", -0.75, -0.8, fs, fe)
    for i in range(5):
        sparkle(f"Title_sp_{i}", -1.8 + i * 0.9, -1.5, fs, fe)
    show_between(figure_at("Title_fig", 0, -3.8, scale=0.7, smile=True, frame=fs), fs, fe)


def build_scene_mirror(fs, fe, caption):
    """Scene 1 — deep breath at the mirror."""
    bathroom_wall(fs, fe)
    mirror_prop(fs, fe, cx=2.5, cy=0.0)
    sink_prop(fs, fe)
    show_between(figure_at("Mirror_fig", -1.5, -3.5, scale=0.9, smile=False, frame=fs), fs, fe)
    show_between(figure_at("Mirror_ref", 2.5, -1.5, scale=0.45, smile=True, frame=fs), fs, fe)
    subtitle_card(caption, fs, fe)


def build_scene_grab_brush(fs, fe, caption):
    """Scene 2 — full-hand grip on the toothbrush."""
    bathroom_wall(fs, fe)
    sink_prop(fs, fe)
    toothbrush_prop("Grab_brush", 1.5, -1.9, fs, fe)
    toothpaste_prop("Grab_paste", 3.2, -1.9, fs, fe)
    show_between(figure_at("Grab_fig", -1.2, -3.5, scale=0.9, frame=fs), fs, fe)
    show_between(add_text("Full-hand grip", 2.5, 1.2, size=0.38, color=COL_BLUE,
                          name="GrabLbl"), fs, fe)
    subtitle_card(caption, fs, fe)


def build_scene_apply_paste(fs, fe, caption):
    """Scene 3 — pea-sized paste on the brush."""
    bathroom_wall(fs, fe)
    sink_prop(fs, fe)
    toothbrush_prop("Paste_brush", -1.5, -1.75, fs, fe)
    toothpaste_prop("Paste_tube", 0.8, -1.9, fs, fe)
    show_between(gp_circle("PasteDot", -0.3, -1.55, 0.20, fill_color=COL_PASTE,
                           stroke_color=COL_PASTE, frame=fs, n=16), fs, fe)
    show_between(figure_at("Paste_fig", -2.5, -3.5, scale=0.9, frame=fs), fs, fe)
    show_between(add_text("Pea-sized!", 0.5, 0.5, size=0.38, color=COL_PASTE,
                          name="PasteLbl"), fs, fe)
    subtitle_card(caption, fs, fe)


def build_scene_wet_brush(fs, fe, caption):
    """Scene 4 — wet the brush, count one-two-three."""
    bathroom_wall(fs, fe)
    sink_prop(fs, fe)
    toothbrush_prop("Wet_brush", -1.0, -1.8, fs, fe)
    for i in range(6):
        show_between(gp_circle(f"WaterDrop_{i}", -0.3, -1.0 - i * 0.35, 0.08,
                               fill_color=COL_LBLUE, stroke_color=COL_LBLUE, frame=fs, n=8),
                     fs, fe)
    step = max((fe - fs) // 3, 1)
    for i, n in enumerate(["1", "2", "3"]):
        show_between(add_text(n, 2.5, 0.5, size=1.2, color=COL_BLUE, name=f"Count_{n}"),
                     fs + i * step, fs + (i + 1) * step)
    show_between(figure_at("Wet_fig", -2.0, -3.5, scale=0.9, frame=fs), fs, fe)
    subtitle_card(caption, fs, fe)


def build_scene_brush_front(fs, fe, caption):
    """Scene 5 — small circles on the front teeth, count to ten."""
    show_between(figure_at("Front_fig", 0, -3.5, scale=1.0, frame=fs), fs, fe)
    _moving_brush("Front_brush", fs, fe, 8,
                  lambda kf: [(0.5 - 0.6 + 0.15 * math.sin((kf - fs) * 0.4), 2.0),
                              (0.5 + 0.6 + 0.15 * math.sin((kf - fs) * 0.4), 2.0)])
    step = max((fe - fs) // 10, 1)
    for i in range(10):
        show_between(add_text(str(i + 1), -3.5, 1.0, size=0.8, color=COL_BLUE, name=f"FC_{i + 1}"),
                     fs + i * step, fs + (i + 1) * step)
    show_between(add_text("Count to 10!", -3.5, 2.2, size=0.38, color=COL_DARK,
                          name="FCLbl"), fs, fe)
    subtitle_card(caption, fs, fe)


def build_scene_brush_sides(fs, fe, caption):
    """Scene 6 — outer back teeth, left then right."""
    show_between(figure_at("Sides_fig", 0, -3.5, scale=1.0, frame=fs), fs, fe)
    for kf in range(fs, fe, 48):
        side = ((kf - fs) // 48) % 2
        x = -1.0 if side == 0 else 1.0
        _moving_brush(f"SBrush_{kf}", kf, min(kf + 48, fe), 48,
                      lambda _kf, x=x: [(x - 0.5, 1.8), (x + 0.5, 1.8)])
    half = (fe - fs) // 2
    show_between(add_text("LEFT", -3.0, 1.5, size=0.55, color=COL_BLUE, name="SideLblL"),
                 fs, fs + half)
    show_between(add_text("RIGHT", 3.0, 1.5, size=0.55, color=COL_BLUE, name="SideLblR"),
                 fs + half, fe)
    subtitle_card(caption, fs, fe)


def build_scene_brush_inside(fs, fe, caption):
    """Scene 7 — inside surfaces, up-and-down strokes."""
    show_between(figure_at("Inside_fig", 0, -3.5, scale=1.0, frame=fs), fs, fe)
    _moving_brush("Inside_brush", fs, fe, 8,
                  lambda kf: [(0.3, 1.2 + 0.20 * math.sin((kf - fs) * 0.35)),
                              (0.3, 2.2 + 0.20 * math.sin((kf - fs) * 0.35))])
    show_between(add_text("Up & Down\nStrokes", 2.5, 1.5, size=0.40, color=COL_GREEN,
                          name="InsideLbl"), fs, fe)
    subtitle_card(caption, fs, fe)


def build_scene_brush_molars(fs, fe, caption):
    """Scene 8 — molars, back-and-forth like a train."""
    show_between(figure_at("Molar_fig", 0, -3.5, scale=1.0, frame=fs), fs, fe)
    _moving_brush("Molar_brush", fs, fe, 6,
                  lambda kf: [(0.80 * math.sin((kf - fs) * 0.30) - 0.6, 1.8),
                              (0.80 * math.sin((kf - fs) * 0.30) + 0.6, 1.8)])
    show_between(add_text("Like a train on a track!", 0, 0.5, size=0.40, color=COL_HAIR,
                          name="MolarLbl"), fs, fe)
    gp_obj, gp_data = new_gp("Track")
    gp_data.materials.append(gp_material("TrackMat", COL_GREY))
    layer = gp_data.layers.new("l", set_active=True)
    for rail_z in [1.6, 1.9]:
        add_stroke(layer, fs, [(-4.0, rail_z), (4.0, rail_z)], line_width=20, mat_index=0)
    for tie_x in range(-4, 5):
        add_stroke(layer, fs, [(tie_x, 1.5), (tie_x, 2.0)], line_width=30, mat_index=0)
    show_between(gp_obj, fs, fe)
    subtitle_card(caption, fs, fe)


def build_scene_rinse(fs, fe, caption):
    """Scene 9 — rinse and a bright smile in the mirror."""
    bathroom_wall(fs, fe)
    mirror_prop(fs, fe, cx=2.5, cy=0.0)
    sink_prop(fs, fe)
    for i in range(8):
        show_between(gp_circle(f"Rinse_drop_{i}", -0.2, -0.8 - i * 0.3, 0.09,
                               fill_color=COL_LBLUE, stroke_color=COL_LBLUE, frame=fs + i * 6,
                               n=8), fs + i * 6, min(fs + i * 6 + 30, fe))
    show_between(figure_at("Rinse_fig", -1.8, -3.5, scale=0.9, smile=True, frame=fs), fs, fe)
    show_between(figure_at("Rinse_ref", 2.5, -1.5, scale=0.45, smile=True, frame=fs), fs, fe)
    for i in range(6):
        sparkle(f"Rinse_sp_{i}", 1.5 + 0.7 * math.cos(i * math.pi / 3),
                1.2 + 0.7 * math.sin(i * math.pi / 3), fs, fe)
    subtitle_card(caption, fs, fe)


def build_scene_done(fs, fe, caption):
    """Scene 10 — accomplishment, ready to start the day."""
    for i in range(16):
        angle = 2 * math.pi * i / 16
        gp_obj, gp_data = new_gp(f"Ray_{i}")
        gp_data.materials.append(gp_material(f"RayMat_{i}", COL_YELLOW))
        layer = gp_data.layers.new("l", set_active=True)
        add_stroke(layer, fs, [(0, 0), (5.5 * math.cos(angle), 5.5 * math.sin(angle))],
                   line_width=15, mat_index=0)
        show_between(gp_obj, fs, fe)
    show_between(figure_at("Done_fig", 0, -3.2, scale=1.1, smile=True, frame=fs), fs, fe)
    gp_obj, gp_data = new_gp("Arms_raised")
    gp_data.materials.append(gp_material("ArmMat", COL_DARK))
    layer = gp_data.layers.new("l", set_active=True)
    add_stroke(layer, fs, [(-0.33, 0.8), (-1.0, 2.0), (-0.8, 2.8)], line_width=45, mat_index=0)
    add_stroke(layer, fs, [(0.33, 0.8), (1.0, 2.0), (0.8, 2.8)], line_width=45, mat_index=0)
    show_between(gp_obj, fs, fe)
    for i in range(8):
        sparkle(f"Done_sp_{i}", 2.5 * math.cos(i * math.pi / 4),
                2.5 * math.sin(i * math.pi / 4) + 0.5, fs, fe)
    show_between(add_text("Ready to start the day!", 0, 3.2, size=0.60, color=COL_DARK,
                          name="DoneTitle"), fs, fe)
    subtitle_card(caption, fs, fe)


# ── content-driven scene art (for arbitrary stories) ─────────────────────────
# The bespoke SCENE_BUILDERS below are hand-authored for the demo. Any other story
# is drawn from an art hint (background + expression + gesture) derived from the
# scene's setting and caption — the same content vocabulary the matplotlib renderer
# uses — so an arbitrary scene gets a roughly-appropriate backdrop rather than the
# demo's bathroom frames.


def _bd_calm(fs, fe):
    show_between(gp_rect("bd_sky", -6, 1.6, 12, 2.0, fill_color=(*COL_LBLUE[:3], 0.25),
                         stroke_color=(*COL_LBLUE[:3], 0.0), frame=fs), fs, fe)


def _bd_bathroom(fs, fe):
    show_between(gp_rect("bd_wall", -6, -1.2, 12, 5.0, fill_color=(*COL_LBLUE[:3], 0.18),
                         stroke_color=(*COL_GREY[:3], 0.0), frame=fs), fs, fe)
    show_between(gp_rect("bd_sink", -1.3, -3.4, 2.6, 0.9, fill_color=COL_LBLUE,
                         stroke_color=COL_GREY, frame=fs), fs, fe)


def _bd_bedroom(fs, fe):
    show_between(gp_rect("bd_floor", -6, -3.5, 12, 1.4, fill_color=(*COL_HAIR[:3], 0.35),
                         stroke_color=(*COL_HAIR[:3], 0.0), frame=fs), fs, fe)
    show_between(gp_rect("bd_bed", 1.4, -3.2, 3.6, 1.2, fill_color=COL_LBLUE,
                         stroke_color=COL_GREY, frame=fs), fs, fe)
    show_between(gp_circle("bd_moon", -3.6, 2.4, 0.5, fill_color=COL_YELLOW,
                           stroke_color=COL_YELLOW, frame=fs), fs, fe)


def _bd_kitchen(fs, fe):
    show_between(gp_rect("bd_counter", -6, -2.6, 12, 0.7, fill_color=(*COL_BROWN[:3], 0.7),
                         stroke_color=COL_DARK, frame=fs), fs, fe)
    show_between(gp_rect("bd_cupboard", -4.2, 1.0, 2.2, 2.0, fill_color=COL_LBLUE,
                         stroke_color=COL_GREY, frame=fs), fs, fe)


def _bd_classroom(fs, fe):
    show_between(gp_rect("bd_board", -3.6, 0.4, 4.2, 2.6, fill_color=COL_BOARD,
                         stroke_color=COL_BROWN, frame=fs), fs, fe)
    show_between(gp_rect("bd_desk", 1.8, -3.2, 2.6, 1.1, fill_color=(*COL_BROWN[:3], 0.7),
                         stroke_color=COL_DARK, frame=fs), fs, fe)


def _bd_outdoors(fs, fe):
    show_between(gp_rect("bd_grass", -6, -3.5, 12, 1.8, fill_color=(*COL_GREEN[:3], 0.5),
                         stroke_color=(*COL_GREEN[:3], 0.0), frame=fs), fs, fe)
    show_between(gp_circle("bd_sun", 4.2, 2.6, 0.6, fill_color=COL_YELLOW,
                           stroke_color=COL_YELLOW, frame=fs), fs, fe)
    show_between(gp_rect("bd_trunk", -4.2, -1.6, 0.3, 1.6, fill_color=COL_BROWN,
                         stroke_color=COL_BROWN, frame=fs), fs, fe)
    show_between(gp_circle("bd_canopy", -4.05, 0.4, 0.9, fill_color=COL_GREEN,
                           stroke_color=COL_GREEN, frame=fs), fs, fe)


_BACKDROP = {
    Background.CALM: _bd_calm,
    Background.BATHROOM: _bd_bathroom,
    Background.BEDROOM: _bd_bedroom,
    Background.KITCHEN: _bd_kitchen,
    Background.CLASSROOM: _bd_classroom,
    Background.OUTDOORS: _bd_outdoors,
}


def _prop_shape(name, canonical, x, y, fs, fe):
    """Draw one recognized prop as a small GP shape; skip unknown props."""
    if canonical in ("ball",):
        show_between(gp_circle(name, x, y, 0.35, COL_BLUE, frame=fs), fs, fe)
    elif canonical in ("book",):
        show_between(gp_rect(name, x - 0.4, y - 0.3, 0.8, 0.6, COL_GREEN, frame=fs), fs, fe)
    elif canonical in ("cup", "drink"):
        show_between(gp_rect(name, x - 0.25, y - 0.35, 0.5, 0.7, COL_LBLUE, frame=fs), fs, fe)
    elif canonical in ("plate", "food"):
        show_between(gp_circle(name, x, y, 0.4, COL_WHITE, stroke_color=COL_GREY, frame=fs), fs, fe)
    elif canonical in ("apple", "fruit"):
        show_between(gp_circle(name, x, y, 0.32, COL_RED, frame=fs), fs, fe)
    elif canonical in ("backpack", "bag"):
        show_between(gp_rect(name, x - 0.35, y - 0.4, 0.7, 0.85, COL_BLUE, frame=fs), fs, fe)
    elif canonical in ("block",):
        for i, col in enumerate((COL_BLUE, COL_GREEN, COL_YELLOW)):
            show_between(gp_rect(f"{name}_{i}", x - 0.25, y - 0.4 + i * 0.28, 0.5, 0.25,
                                 col, frame=fs), fs, fe)
    elif canonical in ("toy", "teddy", "bear", "doll"):
        show_between(gp_circle(name, x, y, 0.35, COL_HAIR, frame=fs), fs, fe)
    # unrecognized props are silently skipped


def _canonical_prop(prop):
    """Map a scene prop label to the canonical key drawn above (or None)."""
    low = prop.lower()
    for key in ("toothbrush", "toothpaste", "backpack", "bag", "apple", "fruit", "spoon",
                "shoe", "ball", "book", "cup", "drink", "block", "toy", "teddy", "bear",
                "doll", "plate", "food"):
        if key in low:
            return key
    return None


def build_scene_content(fs, fe, scene):
    """Draw a scene from its setting/caption/props/character — content-driven."""
    hint = art_hint_for(scene.setting, scene.caption)
    expr, gesture = resolve_figure_cues(scene.pose, scene.expression, scene.caption)
    _BACKDROP[hint.background](fs, fe)
    smile = expr in (Expression.SMILE, Expression.CALM)
    show_between(figure_at(f"Fig_{fs}", 0, -3.2, scale=1.0, smile=smile, frame=fs), fs, fe)
    if gesture is Gesture.WAVE:
        gp_obj, gp_data = new_gp(f"Wave_{fs}")
        gp_data.materials.append(gp_material(f"WaveMat_{fs}", COL_DARK))
        layer = gp_data.layers.new("l", set_active=True)
        add_stroke(layer, fs, [(0.33, -2.4), (1.1, -1.4), (1.0, -0.7)], line_width=45, mat_index=0)
        show_between(gp_obj, fs, fe)
    drawn = 0
    for prop in scene.props:
        canonical = _canonical_prop(prop)
        if canonical is None:
            continue
        x = -3.6 if drawn == 0 else 3.6
        _prop_shape(f"Prop_{fs}_{drawn}", canonical, x, -1.2, fs, fe)
        drawn += 1
        if drawn >= 2:
            break
    subtitle_card(scene.caption, fs, fe)


def _is_demo_story(plan: RenderPlan) -> bool:
    """Whether this is the hand-authored demo (keeps its bespoke per-scene art)."""
    return "Shines His Smile" in plan.title


def _apply_transitions(plan: RenderPlan, title_frames: int) -> None:
    """Render each scene's fade/dissolve as a keyframed black overlay.

    One full-frame black grease-pencil layer sits in front of the scene (the ortho
    camera is at Y=-10 looking +Y, so Y=-5 is in front); its opacity is keyframed
    per frame from the shared :func:`composite_plan` — ``1 - content_weight`` — so a
    scene fades from/to black on its declared transitions and is fully clear in
    between. Dissolve is rendered as the same soft fade-through-black here (a true
    crossfade to the neighbouring scene is a follow-up); ``cut`` frames stay clear.
    """
    gp_obj, gp_data = new_gp("FadeOverlay")
    gp_data.materials.append(gp_material("FadeMat", COL_DARK, use_fill=True,
                                         fill_color=(0.0, 0.0, 0.0, 1.0)))
    layer = gp_data.layers.new("l", set_active=True)
    add_stroke(layer, 1, [(-8, -7), (8, -7), (8, 7), (-8, 7), (-8, -7)],
               line_width=30, mat_index=0)
    gp_obj.location = (0, -5.0, 0)  # in front of the scene

    def key(frame, opacity):
        layer.opacity = max(0.0, min(1.0, opacity))
        layer.keyframe_insert("opacity", frame=frame)

    key(1, 0.0)  # the title card carries no transition
    cursor = title_frames + 1
    for prepared in plan.scenes:
        comp = composite_plan(
            prepared.frame_count, plan.fps, prepared.transition_in, prepared.transition_out
        )
        for offset, frame in enumerate(comp):
            opacity = 0.0 if frame.source is BlendSource.KEEP else (1.0 - frame.weight)
            key(cursor + offset, opacity)
        cursor += prepared.frame_count


# Bespoke scene builders for the 10 narrated scenes, keyed by 1-based index.
SCENE_BUILDERS = {
    1: build_scene_mirror,
    2: build_scene_grab_brush,
    3: build_scene_apply_paste,
    4: build_scene_wet_brush,
    5: build_scene_brush_front,
    6: build_scene_brush_sides,
    7: build_scene_brush_inside,
    8: build_scene_brush_molars,
    9: build_scene_rinse,
    10: build_scene_done,
}


def build_scene_generic(fs, fe, caption):
    """Fallback for any scene index without a bespoke builder."""
    show_between(figure_at(f"Gen_fig_{fs}", 0, -3.2, scale=1.0, smile=True, frame=fs), fs, fe)
    subtitle_card(caption, fs, fe)


class BlenderGreasePencilRenderer(SceneScriptRenderer):
    """Reference v2 renderer: Blender Grease-Pencil animation."""

    name = "blender-grease-pencil-v2"
    supported_majors = frozenset({1})

    def _render(self, plan: RenderPlan, *, draft_path: str | None) -> RenderSafetyReport:
        """Build the GP scene from the plan, render it, and return a report.

        Args:
            plan: The validated, name-reinserted render plan.
            draft_path: Where Blender writes the draft mp4, or ``None`` to build
                the scene without rendering (used when no output is requested).

        Returns:
            A structural :class:`RenderSafetyReport`: this renderer is calm by
            construction (fixed palette, silent, no fast motion), so a constant
            luminance signal is reported. Pixel-accurate analysis is a follow-up.

        Raises:
            RuntimeError: If Blender's ``bpy`` is unavailable.
        """
        bpy_module = _load_bpy()
        bpy_module.ops.wm.read_factory_settings(use_empty=True)

        title_frames = plan.fps * 2
        setup_render(plan.fps, draft_path or "//draft.mp4")

        scene = bpy_module.context.scene
        scene.frame_start = 1
        scene.frame_end = title_frames + plan.total_frames

        build_scene_title(1, title_frames, plan.title)
        demo = _is_demo_story(plan)
        cursor = title_frames + 1
        for prepared in plan.scenes:
            start, end = cursor, cursor + prepared.frame_count
            if demo and prepared.index in SCENE_BUILDERS:
                SCENE_BUILDERS[prepared.index](start, end, prepared.caption)
            else:
                build_scene_content(start, end, prepared)
            cursor = end

        _apply_transitions(plan, title_frames)

        if draft_path is not None:
            bpy_module.ops.render.render(animation=True)

        total = title_frames + plan.total_frames
        return RenderSafetyReport(
            fps=plan.fps,
            luminances=[0.7] * total,
            narration_volume=0.0,
            sfx_levels=[],
        )


def main() -> None:
    """Render the bundled demo to ``silas_shines_his_smile_v2.mp4``."""
    import os

    from kathai_chithiram.rendering.silas_story import (
        SILAS_SCENE_SCRIPT,
        silas_mapping,
    )

    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "silas_shines_his_smile_v2.mp4"
    )
    BlenderGreasePencilRenderer().render(
        SILAS_SCENE_SCRIPT, mapping=silas_mapping(), output_path=output_path
    )
    print(f"Done! → {output_path}")


if __name__ == "__main__":
    main()
