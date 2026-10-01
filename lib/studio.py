"""Scène, studio de rendu, contrôle qualité et création d'objets à partir de tableaux."""
import math
import os

import bpy
import bmesh
import numpy as np
from mathutils import Vector

from .materials import simple_material


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    return scene


def mesh_object(name, verts, faces, materials=(), attrs=None, smooth=True, collection=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for m in materials:
        me.materials.append(m)
    if smooth:
        me.shade_smooth()
    if attrs:
        for name_, values in attrs.items():
            a = me.color_attributes.new(name_, "FLOAT_COLOR", "POINT")
            a.data.foreach_set("color", np.asarray(values, np.float32).ravel())
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def add_subsurf(ob, viewport=1, render=2):
    mod = ob.modifiers.new("Subdivision", "SUBSURF")
    mod.levels, mod.render_levels = viewport, render
    return mod


def look_at(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


def area_light(name, loc, target, size, energy, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.size, ld.energy, ld.color = size, energy, color
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    look_at(ob, target)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def backdrop(scale=3.0, color=(0.50, 0.50, 0.52)):
    """Fond studio en L arrondi (sol + mur), mur côté +Y."""
    prof = [(-0.6, 0.0), (-0.2, 0.0), (0.15, 0.0)]
    cy, cz, rad = 0.15, 0.25, 0.25
    prof += [(cy + rad * math.sin(a), cz - rad * math.cos(a)) for a in (math.pi / 2 * i / 12 for i in range(1, 13))]
    prof += [(0.4, 0.8)]
    xs = (-0.9, 0.0, 0.9)
    verts, faces = [], []
    for y, z in prof:
        verts += [(x * scale, y * scale, z * scale) for x in xs]
    for r in range(len(prof) - 1):
        for k in range(len(xs) - 1):
            a, b = r * len(xs), (r + 1) * len(xs)
            faces.append((a + k, a + k + 1, b + k + 1, b + k))
    return mesh_object("Studio_Fond", verts, faces, [simple_material("Studio_Gris", color, 0.55)])


def camera(name, loc, target, lens=70):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.01
    ob = bpy.data.objects.new(name, cd)
    ob.location = loc
    look_at(ob, target)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def setup_render(scene, res=(1600, 1200), samples=128):
    world = bpy.data.worlds.new("Monde")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.6, 0.62, 0.66, 1)
    bg.inputs["Strength"].default_value = 0.15
    scene.world = world
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 16
    scene.cycles.transmission_bounces = 16
    scene.cycles.transparent_max_bounces = 16
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.view_settings.view_transform = "AgX"


def render(scene, path, cam=None):
    if cam:
        scene.camera = cam
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def mesh_report(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    sizes = [len(f.verts) for f in bm.faces]
    rep = {
        "objet": ob.name,
        "sommets": len(bm.verts),
        "faces": len(bm.faces),
        "quads": sizes.count(4),
        "tris": sizes.count(3),
        "ngons": sum(1 for s in sizes if s > 4),
        "aretes_non_manifold": sum(1 for e in bm.edges if not e.is_manifold),
        "normales_coherentes": all(e.is_contiguous for e in bm.edges if e.is_manifold),
        "shape_keys": [k.name for k in ob.data.shape_keys.key_blocks] if ob.data.shape_keys else [],
    }
    bm.free()
    return rep


def contact_sheet(paths, labels, out, cols=3):
    """Assemble plusieurs rendus en une planche légendée."""
    from PIL import Image, ImageDraw, ImageFont

    ims = [Image.open(p).convert("RGB") for p in paths]
    w, h = ims[0].size
    rows = math.ceil(len(ims) / cols)
    sheet = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(18, h // 18))
    except OSError:
        font = ImageFont.load_default()
    for i, (im, lab) in enumerate(zip(ims, labels)):
        x, y = (i % cols) * w, (i // cols) * h
        sheet.paste(im, (x, y))
        d = ImageDraw.Draw(sheet)
        d.rectangle([x, y, x + w, y + h // 11], fill=(30, 30, 34))
        d.text((x + 12, y + 6), lab, fill=(240, 240, 240), font=font)
    sheet.save(out)
    for p in paths:
        os.remove(p)
    return out
