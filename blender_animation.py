"""
blender_animation.py
Run with:  blender --background --python blender_animation.py

Produces:  silas_shines_his_smile_v2.mp4
           11 scenes × 4 s each at 24 fps  =  ~44 s

Uses Blender 4.x  Grease Pencil + compositor text cards.
Each stick-figure pose is built from GP strokes; limbs are
interpolated between keyframes by Blender's built-in tweening.
"""

import bpy
import math
import os

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "silas_shines_his_smile_v2.mp4")
FPS          = 24
SCENE_FRAMES = 96          # 4 s per scene
TOTAL_SCENES = 11


# ── palette ────────────────────────────────────────────────────────────────────
def rgb(r, g, b, a=1.0):
    return (r / 255, g / 255, b / 255, a)

COL_BG       = rgb(245, 245, 240)
COL_DARK     = rgb( 30,  30,  30)
COL_BLUE     = rgb( 74, 144, 217)
COL_LBLUE    = rgb(174, 214, 241)
COL_GREEN    = rgb( 93, 187,  99)
COL_YELLOW   = rgb(245, 197,  24)
COL_SKIN     = rgb(244, 192, 138)
COL_HAIR     = rgb(139,  94,  60)
COL_SHIRT    = rgb( 74, 144, 217)
COL_WHITE    = rgb(255, 255, 255)
COL_GREY     = rgb(180, 180, 180)
COL_PASTE    = rgb( 86, 180, 211)


# ── scene / render setup ───────────────────────────────────────────────────────

def setup_render():
    scene = bpy.context.scene
    scene.render.engine          = 'BLENDER_EEVEE'
    scene.render.resolution_x    = 1280
    scene.render.resolution_y    = 720
    scene.render.resolution_percentage = 100
    scene.render.fps             = FPS
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format   = 'MPEG4'
    scene.render.ffmpeg.codec    = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
    scene.render.filepath        = OUTPUT_PATH

    # world background
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs[0].default_value = COL_BG + (1,) if len(COL_BG) == 3 else (*COL_BG[:3], 1)

    # camera — orthographic, fills frame
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type         = 'ORTHO'
    cam_data.ortho_scale  = 10.0
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    cam_obj.location = (0, -10, 0)
    cam_obj.rotation_euler = (math.radians(90), 0, 0)

    # light
    light_data = bpy.data.lights.new("Light", type='SUN')
    light_data.energy = 3
    light_obj = bpy.data.objects.new("Light", light_data)
    scene.collection.objects.link(light_obj)
    light_obj.location = (5, -5, 10)


# ── Grease-Pencil helpers ──────────────────────────────────────────────────────

def new_gp(name, collection=None):
    """Create a new Grease Pencil object."""
    gp_data = bpy.data.grease_pencils.new(name)
    gp_obj  = bpy.data.objects.new(name, gp_data)
    col     = collection or bpy.context.scene.collection
    col.objects.link(gp_obj)
    gp_obj.location = (0, 0, 0)
    return gp_obj, gp_data


def gp_material(name, color, use_fill=False, fill_color=None):
    mat = bpy.data.materials.new(name)
    bpy.data.materials.create_gpencil_data(mat)
    mat.grease_pencil.color      = color
    mat.grease_pencil.show_stroke = True
    if use_fill and fill_color:
        mat.grease_pencil.show_fill  = True
        mat.grease_pencil.fill_color = fill_color
    return mat


def add_stroke(layer, frame_number, points_2d, pressure=1.0,
               line_width=50, mat_index=0):
    """
    Add a stroke to a GP layer at the given frame.
    points_2d : list of (x, y) in world coords  (z = 0)
    """
    frame = None
    for f in layer.frames:
        if f.frame_number == frame_number:
            frame = f
            break
    if frame is None:
        frame = layer.frames.new(frame_number)

    stroke = frame.strokes.new()
    stroke.material_index = mat_index
    stroke.line_width     = line_width
    stroke.points.add(len(points_2d))
    for i, (x, y) in enumerate(points_2d):
        stroke.points[i].co       = (x, 0, y)     # GP uses X/Z for 2D in world
        stroke.points[i].pressure = pressure
        stroke.points[i].strength = 1.0
    return stroke


def circle_points(cx, cy, r, n=32):
    return [(cx + r * math.cos(2 * math.pi * i / n),
             cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def arc_points(cx, cy, r, a1_deg, a2_deg, n=16):
    pts = []
    for i in range(n + 1):
        a = math.radians(a1_deg + (a2_deg - a1_deg) * i / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# ── stick-figure builder ───────────────────────────────────────────────────────

class FigureBuilder:
    """
    Builds a complete stick figure as a single GP object.
    All strokes land on the SAME frame so they move together
    when the object is keyframed as a unit.
    """

    def __init__(self, name, cx, cy, scale=1.0, smile=False):
        self.gp_obj, self.gp_data = new_gp(name)
        s = scale

        # materials
        self.gp_data.materials.append(gp_material(f"{name}_dark",  COL_DARK))
        self.gp_data.materials.append(gp_material(f"{name}_skin",  COL_DARK,
                                                   use_fill=True, fill_color=COL_SKIN))
        self.gp_data.materials.append(gp_material(f"{name}_shirt", COL_DARK,
                                                   use_fill=True, fill_color=COL_SHIRT))
        self.gp_data.materials.append(gp_material(f"{name}_hair",  COL_HAIR))

        layer = self.gp_data.layers.new("fig", set_active=True)
        F = 1   # build on frame 1

        # ── head ──────────────────────────────────────────────────────────────
        head_r = 0.5 * s
        head_cx, head_cy = cx, cy + 2.4 * s
        add_stroke(layer, F, circle_points(head_cx, head_cy, head_r),
                   line_width=40, mat_index=1)  # skin fill

        # hair arc
        add_stroke(layer, F, arc_points(head_cx, head_cy, head_r * 1.05, 20, 160, n=20),
                   line_width=60, mat_index=3)

        # eyes
        for ex in [head_cx - 0.18 * s, head_cx + 0.18 * s]:
            add_stroke(layer, F, circle_points(ex, head_cy + 0.08 * s, 0.07 * s, n=12),
                       line_width=60, mat_index=0)

        # mouth
        if smile:
            add_stroke(layer, F,
                       arc_points(head_cx, head_cy - 0.10 * s, 0.20 * s, 200, 340, n=12),
                       line_width=35, mat_index=0)
        else:
            add_stroke(layer, F,
                       [(head_cx - 0.15 * s, head_cy - 0.18 * s),
                        (head_cx + 0.15 * s, head_cy - 0.18 * s)],
                       line_width=30, mat_index=0)

        # ── shirt / torso ─────────────────────────────────────────────────────
        torso_pts = [
            (cx - 0.30 * s, cy + 0.50 * s),
            (cx - 0.30 * s, cy + 1.80 * s),
            (cx + 0.30 * s, cy + 1.80 * s),
            (cx + 0.30 * s, cy + 0.50 * s),
            (cx - 0.30 * s, cy + 0.50 * s),
        ]
        add_stroke(layer, F, torso_pts, line_width=35, mat_index=2)

        # neck line
        add_stroke(layer, F,
                   [(cx, cy + 1.80 * s), (cx, cy + 1.90 * s)],
                   line_width=40, mat_index=1)

        # ── arms ──────────────────────────────────────────────────────────────
        shoulder_y = cy + 1.70 * s
        # left arm down
        add_stroke(layer, F,
                   [(cx - 0.30 * s, shoulder_y),
                    (cx - 0.60 * s, shoulder_y - 0.70 * s),
                    (cx - 0.55 * s, shoulder_y - 1.20 * s)],
                   line_width=40, mat_index=0)
        # right arm down
        add_stroke(layer, F,
                   [(cx + 0.30 * s, shoulder_y),
                    (cx + 0.60 * s, shoulder_y - 0.70 * s),
                    (cx + 0.55 * s, shoulder_y - 1.20 * s)],
                   line_width=40, mat_index=0)

        # hands
        for hx, hy in [(cx - 0.55 * s, shoulder_y - 1.20 * s),
                       (cx + 0.55 * s, shoulder_y - 1.20 * s)]:
            add_stroke(layer, F, circle_points(hx, hy, 0.10 * s, n=10),
                       line_width=25, mat_index=1)

        # ── legs ──────────────────────────────────────────────────────────────
        hip_y = cy + 0.50 * s
        add_stroke(layer, F,
                   [(cx, hip_y),
                    (cx - 0.30 * s, hip_y - 0.80 * s),
                    (cx - 0.25 * s, hip_y - 1.50 * s)],
                   line_width=40, mat_index=0)
        add_stroke(layer, F,
                   [(cx, hip_y),
                    (cx + 0.30 * s, hip_y - 0.80 * s),
                    (cx + 0.25 * s, hip_y - 1.50 * s)],
                   line_width=40, mat_index=0)

        # feet
        for fx, fy in [(cx - 0.25 * s, hip_y - 1.50 * s),
                       (cx + 0.25 * s, hip_y - 1.50 * s)]:
            sign = -1 if fx < cx else 1
            add_stroke(layer, F,
                       [(fx, fy), (fx + sign * 0.30 * s, fy)],
                       line_width=40, mat_index=0)

        # store reference
        self.obj = self.gp_obj


def figure_at(name, cx, cy, scale=1.0, smile=False, frame=1, loc_z=0):
    fb = FigureBuilder(name, cx, cy, scale=scale, smile=smile)
    obj = fb.obj
    obj.location = (0, 0, loc_z)
    obj.keyframe_insert("location", frame=frame)
    return obj


# ── prop / environment helpers ─────────────────────────────────────────────────

def gp_rect(name, x, y, w, h, fill_color, stroke_color=None, frame=1, z=0):
    gp_obj, gp_data = new_gp(name)
    sc = stroke_color or COL_DARK
    gp_data.materials.append(gp_material(f"{name}_fill", sc,
                                          use_fill=True, fill_color=fill_color))
    layer = gp_data.layers.new("l", set_active=True)
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
    add_stroke(layer, frame, pts, line_width=30, mat_index=0)
    gp_obj.location = (0, 0, z)
    return gp_obj


def gp_circle(name, cx, cy, r, fill_color, stroke_color=None, frame=1, z=0, n=32):
    gp_obj, gp_data = new_gp(name)
    sc = stroke_color or COL_DARK
    gp_data.materials.append(gp_material(f"{name}_fill", sc,
                                          use_fill=True, fill_color=fill_color))
    layer = gp_data.layers.new("l", set_active=True)
    add_stroke(layer, frame, circle_points(cx, cy, r, n=n), line_width=30, mat_index=0)
    gp_obj.location = (0, 0, z)
    return gp_obj


def add_text(text, x, y, size=0.45, color=COL_DARK, name="Text", z=0.1):
    bpy.ops.object.text_add(location=(x, 0, y))
    txt_obj             = bpy.context.object
    txt_obj.name        = name
    txt_obj.data.body   = text
    txt_obj.data.size   = size
    txt_obj.data.align_x = 'CENTER'
    txt_obj.rotation_euler = (math.radians(90), 0, 0)
    mat = bpy.data.materials.new(f"{name}_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color[:3], 1)
        bsdf.inputs["Emission Color"].default_value = (*color[:3], 1)
        bsdf.inputs["Emission Strength"].default_value = 2.0
    txt_obj.data.materials.append(mat)
    txt_obj.location.y = 0
    txt_obj.location.z = y
    txt_obj.location.x = x
    return txt_obj


def subtitle_card(text, frame_start, frame_end, z=-3.0):
    """Semi-transparent white card + dark text at bottom of frame."""
    card = gp_rect("SubCard", -5.5, z - 0.45, 11, 0.90,
                   fill_color=(*COL_WHITE[:3], 0.85),
                   stroke_color=COL_GREY,
                   frame=frame_start)
    hide_at(card, frame_end)

    txt = add_text(text, 0, z, size=0.38, color=COL_DARK, name=f"Sub_{frame_start}")
    hide_at(txt, frame_end)
    return card, txt


def hide_at(obj, frame):
    obj.hide_viewport = False
    obj.hide_render   = False
    obj.keyframe_insert("hide_viewport", frame=frame - 1)
    obj.keyframe_insert("hide_render",   frame=frame - 1)
    obj.hide_viewport = True
    obj.hide_render   = True
    obj.keyframe_insert("hide_viewport", frame=frame)
    obj.keyframe_insert("hide_render",   frame=frame)


def show_between(obj, frame_start, frame_end):
    # hidden before
    obj.hide_viewport = True
    obj.hide_render   = True
    obj.keyframe_insert("hide_viewport", frame=1)
    obj.keyframe_insert("hide_render",   frame=1)
    # visible from frame_start
    obj.hide_viewport = False
    obj.hide_render   = False
    obj.keyframe_insert("hide_viewport", frame=frame_start)
    obj.keyframe_insert("hide_render",   frame=frame_start)
    # hidden again at frame_end
    obj.hide_viewport = True
    obj.hide_render   = True
    obj.keyframe_insert("hide_viewport", frame=frame_end)
    obj.keyframe_insert("hide_render",   frame=frame_end)


# ── tile / bathroom wall ───────────────────────────────────────────────────────

def bathroom_wall(frame_start, frame_end):
    objs = []
    for row in range(5):
        for col in range(9):
            tile = gp_rect(f"tile_{row}_{col}",
                           -4.8 + col * 1.1, -3.5 + row * 1.4,
                           1.0, 1.3,
                           fill_color=(*COL_WHITE[:3], 1),
                           stroke_color=COL_GREY,
                           frame=frame_start)
            show_between(tile, frame_start, frame_end)
            objs.append(tile)
    return objs


def mirror_prop(frame_start, frame_end, cx=2.5, cy=0.5):
    m = gp_rect("Mirror", cx - 1.1, cy - 0.2, 2.2, 2.8,
                fill_color=COL_LBLUE, stroke_color=COL_GREY, frame=frame_start)
    show_between(m, frame_start, frame_end)
    return m


def sink_prop(frame_start, frame_end, cx=0.0, cy=-2.5):
    s = gp_rect("Sink", cx - 2.2, cy, 4.4, 0.7,
                fill_color=COL_WHITE, stroke_color=COL_GREY, frame=frame_start)
    show_between(s, frame_start, frame_end)
    return s


def toothbrush_prop(name, x, y, frame_start, frame_end):
    tb = gp_rect(name, x, y, 1.5, 0.25,
                 fill_color=COL_BLUE, stroke_color=COL_DARK, frame=frame_start)
    show_between(tb, frame_start, frame_end)
    return tb


def toothpaste_prop(name, x, y, frame_start, frame_end):
    tp = gp_rect(name, x, y, 0.5, 1.4,
                 fill_color=COL_GREEN, stroke_color=COL_DARK, frame=frame_start)
    show_between(tp, frame_start, frame_end)
    return tp


def sparkle(name, cx, cy, frame_start, frame_end):
    sp = gp_circle(name, cx, cy, 0.15,
                   fill_color=COL_YELLOW, stroke_color=COL_YELLOW,
                   frame=frame_start, n=5)
    show_between(sp, frame_start, frame_end)
    return sp


# ── scene builders ─────────────────────────────────────────────────────────────

def S(n):
    """Return (frame_start, frame_end) for scene index n (0-based)."""
    return n * SCENE_FRAMES + 1, (n + 1) * SCENE_FRAMES


def build_scene_title():
    fs, fe = S(0)
    t1 = add_text("Silas Shines His Smile", 0, 1.2, size=0.65,
                  color=COL_DARK, name="Title_main")
    show_between(t1, fs, fe)
    t2 = add_text("By Sivakumar Mambakkam", 0, 0.3, size=0.38,
                  color=COL_GREY, name="Title_sub")
    show_between(t2, fs, fe)
    # decorative brush
    tb = toothbrush_prop("Title_brush", -0.75, -0.8, fs, fe)
    for i in range(5):
        sp = sparkle(f"Title_sp_{i}", -1.8 + i * 0.9, -1.5, fs, fe)
    fig = figure_at("Title_fig", 0, -3.8, scale=0.7, smile=True, frame=fs)
    show_between(fig, fs, fe)


def build_scene_mirror():
    fs, fe = S(1)
    bathroom_wall(fs, fe)
    mirror_prop(fs, fe, cx=2.5, cy=0.0)
    sink_prop(fs, fe)

    fig = figure_at("Mirror_fig", -1.5, -3.5, scale=0.9, smile=False, frame=fs)
    show_between(fig, fs, fe)

    # reflection (smaller, inside mirror bounds)
    ref = figure_at("Mirror_ref", 2.5, -1.5, scale=0.45, smile=True, frame=fs)
    show_between(ref, fs, fe)

    subtitle_card("Silas takes a deep breath and\nlooks in the mirror to centre himself.",
                  fs, fe)


def build_scene_grab_brush():
    fs, fe = S(2)
    bathroom_wall(fs, fe)
    sink_prop(fs, fe)
    tb = toothbrush_prop("Grab_brush", 1.5, -1.9, fs, fe)
    tp = toothpaste_prop("Grab_paste", 3.2, -1.9, fs, fe)

    fig = figure_at("Grab_fig", -1.2, -3.5, scale=0.9, frame=fs)
    show_between(fig, fs, fe)

    lbl = add_text("Full-hand grip", 2.5, 1.2, size=0.38, color=COL_BLUE, name="GrabLbl")
    show_between(lbl, fs, fe)

    subtitle_card("He uses a full-hand grip to hold\nthe toothbrush securely.", fs, fe)


def build_scene_apply_paste():
    fs, fe = S(3)
    bathroom_wall(fs, fe)
    sink_prop(fs, fe)

    # brush resting on sink
    tb = toothbrush_prop("Paste_brush", -1.5, -1.75, fs, fe)
    tp = toothpaste_prop("Paste_tube", 0.8, -1.9, fs, fe)

    # paste dot
    paste_dot = gp_circle("PasteDot", -0.3, -1.55, 0.20,
                           fill_color=COL_PASTE, stroke_color=COL_PASTE,
                           frame=fs, n=16)
    show_between(paste_dot, fs, fe)

    fig = figure_at("Paste_fig", -2.5, -3.5, scale=0.9, frame=fs)
    show_between(fig, fs, fe)

    lbl = add_text("Pea-sized!", 0.5, 0.5, size=0.38, color=COL_PASTE, name="PasteLbl")
    show_between(lbl, fs, fe)

    subtitle_card("He squeezes a pea-sized amount\nof paste onto the brush.", fs, fe)


def build_scene_wet_brush():
    fs, fe = S(4)
    bathroom_wall(fs, fe)
    sink_prop(fs, fe)
    tb = toothbrush_prop("Wet_brush", -1.0, -1.8, fs, fe)

    # water stream (series of small circles)
    for i in range(6):
        drop = gp_circle(f"WaterDrop_{i}", -0.3, -1.0 - i * 0.35, 0.08,
                         fill_color=COL_LBLUE, stroke_color=COL_LBLUE,
                         frame=fs, n=8)
        show_between(drop, fs, fe)

    # count 1-2-3 labels (each visible for ~32 frames)
    for i, n in enumerate(["1", "2", "3"]):
        lbl = add_text(n, 2.5, 0.5, size=1.2, color=COL_BLUE, name=f"Count_{n}")
        show_between(lbl, fs + i * 32, fs + (i + 1) * 32)

    fig = figure_at("Wet_fig", -2.0, -3.5, scale=0.9, frame=fs)
    show_between(fig, fs, fe)

    subtitle_card("Brush under cool water for three seconds\n— one, two, three.", fs, fe)


def build_scene_brush_front():
    fs, fe = S(5)
    fig = figure_at("Front_fig", 0, -3.5, scale=1.0, frame=fs)
    show_between(fig, fs, fe)

    # brush at face — animate X position slightly (oscillate)
    tb_data = bpy.data.grease_pencils.new("Front_brush_gp")
    tb_obj  = bpy.data.objects.new("Front_brush", tb_data)
    bpy.context.scene.collection.objects.link(tb_obj)
    mat = gp_material("FBrush_mat", COL_BLUE, use_fill=True, fill_color=COL_BLUE)
    tb_data.materials.append(mat)
    layer = tb_data.layers.new("l", set_active=True)
    pts = [(-0.6, 0.0), (0.6, 0.0)]
    for kf in range(fs, fe, 8):
        offset = 0.15 * math.sin((kf - fs) * 0.4)
        f = layer.frames.new(kf)
        stroke = f.strokes.new()
        stroke.line_width = 80
        stroke.points.add(2)
        for ii, (px, py) in enumerate(pts):
            stroke.points[ii].co = (0.5 + px + offset, 0, 2.0 + py)
            stroke.points[ii].pressure = 1.0
    show_between(tb_obj, fs, fe)

    # counter
    for i in range(10):
        lbl = add_text(str(i + 1), -3.5, 1.0, size=0.8, color=COL_BLUE,
                       name=f"FC_{i+1}")
        show_between(lbl, fs + i * (SCENE_FRAMES // 10),
                         fs + (i + 1) * (SCENE_FRAMES // 10))

    lbl2 = add_text("Count to 10!", -3.5, 2.2, size=0.38, color=COL_DARK,
                    name="FCLbl")
    show_between(lbl2, fs, fe)

    subtitle_card("Small circles on the front teeth —\ncounting slowly to ten.", fs, fe)


def build_scene_brush_sides():
    fs, fe = S(6)
    fig = figure_at("Sides_fig", 0, -3.5, scale=1.0, frame=fs)
    show_between(fig, fs, fe)

    # brush alternates left / right
    for kf in range(fs, fe, 48):
        side = ((kf - fs) // 48) % 2
        x    = -1.0 if side == 0 else 1.0
        tb_data = bpy.data.grease_pencils.new(f"SBrush_{kf}")
        tb_obj  = bpy.data.objects.new(f"SBrush_{kf}", tb_data)
        bpy.context.scene.collection.objects.link(tb_obj)
        mat = gp_material(f"SBMat_{kf}", COL_BLUE, use_fill=True, fill_color=COL_BLUE)
        tb_data.materials.append(mat)
        layer = tb_data.layers.new("l", set_active=True)
        frm = layer.frames.new(kf)
        stroke = frm.strokes.new()
        stroke.line_width = 70
        stroke.points.add(2)
        stroke.points[0].co = (x - 0.5, 0, 1.8); stroke.points[0].pressure = 1
        stroke.points[1].co = (x + 0.5, 0, 1.8); stroke.points[1].pressure = 1
        show_between(tb_obj, kf, min(kf + 48, fe))

    lbl_l = add_text("LEFT", -3.0, 1.5, size=0.55, color=COL_BLUE, name="SideLblL")
    show_between(lbl_l, fs, fs + SCENE_FRAMES // 2)
    lbl_r = add_text("RIGHT", 3.0, 1.5, size=0.55, color=COL_BLUE, name="SideLblR")
    show_between(lbl_r, fs + SCENE_FRAMES // 2, fe)

    subtitle_card("Outer back teeth — left side count to 5,\nthen right side count to 5.", fs, fe)


def build_scene_brush_inside():
    fs, fe = S(7)
    fig = figure_at("Inside_fig", 0, -3.5, scale=1.0, frame=fs)
    show_between(fig, fs, fe)

    # vertical brush, oscillates up-down
    tb_data = bpy.data.grease_pencils.new("Inside_brush_gp")
    tb_obj  = bpy.data.objects.new("Inside_brush", tb_data)
    bpy.context.scene.collection.objects.link(tb_obj)
    mat = gp_material("IBMat", COL_BLUE, use_fill=True, fill_color=COL_BLUE)
    tb_data.materials.append(mat)
    layer = tb_data.layers.new("l", set_active=True)
    for kf in range(fs, fe, 8):
        offset = 0.20 * math.sin((kf - fs) * 0.35)
        frm = layer.frames.new(kf)
        stroke = frm.strokes.new()
        stroke.line_width = 80
        stroke.points.add(2)
        stroke.points[0].co = (0.3, 0, 1.2 + offset)
        stroke.points[0].pressure = 1
        stroke.points[1].co = (0.3, 0, 2.2 + offset)
        stroke.points[1].pressure = 1
    show_between(tb_obj, fs, fe)

    lbl = add_text("Up & Down\nStrokes", 2.5, 1.5, size=0.40, color=COL_GREEN,
                   name="InsideLbl")
    show_between(lbl, fs, fe)

    subtitle_card("He tilts the brush vertically for\nthe inside surfaces — up-and-down strokes.", fs, fe)


def build_scene_brush_molars():
    fs, fe = S(8)
    fig = figure_at("Molar_fig", 0, -3.5, scale=1.0, frame=fs)
    show_between(fig, fs, fe)

    # horizontal brush oscillates back-and-forth
    tb_data = bpy.data.grease_pencils.new("Molar_brush_gp")
    tb_obj  = bpy.data.objects.new("Molar_brush", tb_data)
    bpy.context.scene.collection.objects.link(tb_obj)
    mat = gp_material("MBMat", COL_BLUE, use_fill=True, fill_color=COL_BLUE)
    tb_data.materials.append(mat)
    layer = tb_data.layers.new("l", set_active=True)
    for kf in range(fs, fe, 6):
        offset = 0.80 * math.sin((kf - fs) * 0.30)
        frm = layer.frames.new(kf)
        stroke = frm.strokes.new()
        stroke.line_width = 80
        stroke.points.add(2)
        stroke.points[0].co = (offset - 0.6, 0, 1.8)
        stroke.points[0].pressure = 1
        stroke.points[1].co = (offset + 0.6, 0, 1.8)
        stroke.points[1].pressure = 1
    show_between(tb_obj, fs, fe)

    lbl = add_text("Like a train on a track!", 0, 0.5, size=0.40,
                   color=rgb(139, 94, 60), name="MolarLbl")
    show_between(lbl, fs, fe)

    # track lines
    gp_obj, gp_data = new_gp("Track")
    gp_data.materials.append(gp_material("TrackMat", COL_GREY))
    layer2 = gp_data.layers.new("l", set_active=True)
    for rail_z in [1.6, 1.9]:
        add_stroke(layer2, fs, [(-4.0, rail_z), (4.0, rail_z)],
                   line_width=20, mat_index=0)
    for tie_x in range(-4, 5):
        add_stroke(layer2, fs, [(tie_x, 1.5), (tie_x, 2.0)],
                   line_width=30, mat_index=0)
    show_between(gp_obj, fs, fe)

    subtitle_card("Back-and-forth on the molars —\nlike a train on a track.", fs, fe)


def build_scene_rinse():
    fs, fe = S(9)
    bathroom_wall(fs, fe)
    mirror_prop(fs, fe, cx=2.5, cy=0.0)
    sink_prop(fs, fe)

    # water drops falling
    for i in range(8):
        drop = gp_circle(f"Rinse_drop_{i}", -0.2, -0.8 - i * 0.3, 0.09,
                         fill_color=COL_LBLUE, stroke_color=COL_LBLUE,
                         frame=fs + i * 6, n=8)
        show_between(drop, fs + i * 6, min(fs + i * 6 + 30, fe))

    fig = figure_at("Rinse_fig", -1.8, -3.5, scale=0.9, smile=True, frame=fs)
    show_between(fig, fs, fe)

    ref = figure_at("Rinse_ref", 2.5, -1.5, scale=0.45, smile=True, frame=fs)
    show_between(ref, fs, fe)

    for i in range(6):
        sp = sparkle(f"Rinse_sp_{i}", 1.5 + 0.7 * math.cos(i * math.pi / 3),
                     1.2 + 0.7 * math.sin(i * math.pi / 3), fs, fe)

    subtitle_card("He rinses the brush, looks in the mirror\nand sees his bright smile!", fs, fe)


def build_scene_done():
    fs, fe = S(10)

    # sunburst rays
    for i in range(16):
        angle = 2 * math.pi * i / 16
        gp_obj, gp_data = new_gp(f"Ray_{i}")
        gp_data.materials.append(gp_material(f"RayMat_{i}", COL_YELLOW))
        layer = gp_data.layers.new("l", set_active=True)
        add_stroke(layer, fs,
                   [(0, 0), (5.5 * math.cos(angle), 5.5 * math.sin(angle))],
                   line_width=15, mat_index=0)
        show_between(gp_obj, fs, fe)

    fig = figure_at("Done_fig", 0, -3.2, scale=1.1, smile=True, frame=fs)
    show_between(fig, fs, fe)

    # arms raised — covered by separate arm strokes
    gp_obj2, gp_data2 = new_gp("Arms_raised")
    gp_data2.materials.append(gp_material("ArmMat", COL_DARK))
    layer2 = gp_data2.layers.new("l", set_active=True)
    add_stroke(layer2, fs,
               [(-0.33, 0.8), (-1.0, 2.0), (-0.8, 2.8)],
               line_width=45, mat_index=0)
    add_stroke(layer2, fs,
               [(0.33, 0.8), (1.0, 2.0), (0.8, 2.8)],
               line_width=45, mat_index=0)
    show_between(gp_obj2, fs, fe)

    for i in range(8):
        sp = sparkle(f"Done_sp_{i}",
                     2.5 * math.cos(i * math.pi / 4),
                     2.5 * math.sin(i * math.pi / 4) + 0.5,
                     fs, fe)

    t1 = add_text("Ready to start the day!", 0, 3.2, size=0.60,
                  color=COL_DARK, name="DoneTitle")
    show_between(t1, fs, fe)

    subtitle_card("Teeth clean, mind calm — Silas feels proud\nand ready to shine his smile all day!", fs, fe)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Silas Shines His Smile — Blender GP Animation ===")

    # clean default scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    setup_render()

    total_frames = TOTAL_SCENES * SCENE_FRAMES
    scene.frame_start = 1
    scene.frame_end   = total_frames
    print(f"Total frames: {total_frames} ({total_frames // FPS}s at {FPS}fps)")

    print("Building scenes...")
    build_scene_title()
    build_scene_mirror()
    build_scene_grab_brush()
    build_scene_apply_paste()
    build_scene_wet_brush()
    build_scene_brush_front()
    build_scene_brush_sides()
    build_scene_brush_inside()
    build_scene_brush_molars()
    build_scene_rinse()
    build_scene_done()

    print(f"Rendering to: {OUTPUT_PATH}")
    bpy.ops.render.render(animation=True)
    print("Done!")


main()
