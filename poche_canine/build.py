"""Construit le vagin de poche dans Blender, sauvegarde le .blend et rend les vues de validation.

Usage : python poche_canine/build.py [--quick] [--no-render] [--only=01,04]
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402  (bpy doit être importé avant bmesh / mathutils)
import numpy as np  # noqa: E402

from lib import studio  # noqa: E402
from lib.materials import latex_controls, simple_material  # noqa: E402
from poche_canine.objet import make_sleeve, set_keys  # noqa: E402
from poche_canine.sleeve import CANAL_VARIANTS  # noqa: E402

OUT = os.path.join(ROOT, "output", "poche_canine")
QUICK = "--quick" in sys.argv
RENDER = "--no-render" not in sys.argv
ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)


def want(tag):
    return ONLY is None or tag in ONLY


def topology_overlay(ob):
    """Copie du maillage de base (sans subdivision) + fil de fer, pour la vue topologie."""
    col = bpy.data.collections.new("Apercu_Topologie")
    bpy.context.scene.collection.children.link(col)
    clay = simple_material("Apercu_Argile", (0.80, 0.80, 0.80), 0.6)
    wire = simple_material("Apercu_Fil", (0.02, 0.02, 0.025), 0.5)
    objs = []
    for suffix, mat, wf in (("_argile", clay, False), ("_fil", wire, True)):
        me = ob.data.copy()
        me.materials.clear()
        me.materials.append(mat)
        dup = bpy.data.objects.new(ob.name + suffix, me)
        col.objects.link(dup)
        if wf:
            w = dup.modifiers.new("Fil", "WIREFRAME")
            w.thickness, w.use_even_offset, w.use_replace = 0.00018, True, True
        objs.append(dup)
    return col, objs


def main():
    os.makedirs(OUT, exist_ok=True)
    scene = studio.reset_scene()
    ob, mat = make_sleeve()
    print(studio.mesh_report(ob))

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "poche_canine.blend"), compress=True)
    if not RENDER:
        return

    # ---------------------------------------------------------------- studio
    studio.backdrop(scale=3.0)
    res = (480, 360) if QUICK else (1200, 900)
    studio.setup_render(scene, res, 16 if QUICK else 64)
    zc = ob["axe_canal_z"]
    key = studio.area_light("Cle", (-0.35, -0.45, 0.45), (0, 0.04, 0.06), 0.4, 14)
    studio.area_light("Contre", (0.35, 0.30, 0.30), (0, 0.04, 0.06), 0.25, 8, (0.95, 0.97, 1.0))
    studio.area_light("Debouche", (0.45, -0.35, 0.10), (0, 0.04, 0.06), 0.45, 3)
    coupe = studio.area_light("Coupe", (0.45, 0.05, 0.40), (0, 0.10, zc), 0.5, 18)
    coupe.hide_render = True

    cam_face = studio.camera("Cam_Face", (0.0, -0.42, 0.075), (0, 0, 0.068), 85)
    cam_34 = studio.camera("Cam_34", (-0.26, -0.34, 0.22), (0.0, 0.05, 0.055), 60)
    cam_coupe = studio.camera("Cam_Coupe", (0.42, 0.105, zc + 0.06), (0, 0.105, zc), 50)
    cam_profil = studio.camera("Cam_Profil", (-0.40, -0.02, 0.07), (0, -0.02, 0.065), 85)
    cam_entree = studio.camera("Cam_Entree", (0.17, 0.045, zc + 0.02), (0, 0.045, zc), 50)
    cam_canal = studio.camera("Cam_Canal", (0.115, 0.075, zc + 0.03), (0, 0.075, zc), 50)

    ctl = latex_controls(mat)
    ctl.inputs["Transparence"].default_value = 0.0   # opaque pour lire la forme

    def shot(name, cam):
        if want(name[:2]):
            studio.render(scene, os.path.join(OUT, name), cam)

    out = lambda name: os.path.join(OUT, name)  # noqa: E731
    set_keys(ob)
    shot("01_face.png", cam_face)
    shot("02_trois_quarts.png", cam_34)
    set_keys(ob, Levres_Gonflees=1.0)
    shot("03_trois_quarts_levres_gonflees.png", cam_34)
    shot("03b_face_levres_gonflees.png", cam_face)
    shot("09b_profil_levres_gonflees.png", cam_profil)
    set_keys(ob)
    shot("09_profil.png", cam_profil)

    # ---------------------------------------------------------------- coupe
    cutter = studio.mesh_object("Decoupe", [(0, -0.1, -0.1), (0.3, -0.1, -0.1), (0.3, 0.4, -0.1), (0, 0.4, -0.1),
                                            (0, -0.1, 0.3), (0.3, -0.1, 0.3), (0.3, 0.4, 0.3), (0, 0.4, 0.3)],
                                [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)],
                                smooth=False)
    cutter.hide_render = True
    cutter.display_type = "WIRE"
    boolean = ob.modifiers.new("Coupe", "BOOLEAN")
    boolean.operation, boolean.object, boolean.solver = "DIFFERENCE", cutter, "EXACT"
    boolean.material_mode = "TRANSFER"
    cutter.data.materials.append(simple_material("Face_De_Coupe", (0.10, 0.11, 0.13), 0.7))
    coupe.hide_render = False
    key.hide_render = True
    shot("04_coupe_canal_lisse.png", cam_coupe)

    def sheet(tag, name, cam, combos, cols=3, tile=(600, 450)):
        if not want(tag):
            return
        scene.render.resolution_x, scene.render.resolution_y = (240, 180) if QUICK else tile
        tiles, labels = [], []
        for i, (label, keys) in enumerate(combos):
            set_keys(ob, **keys)
            tiles.append(studio.render(scene, out(f"_tile_{tag}_{i}.png"), cam))
            labels.append(label)
        studio.contact_sheet(tiles, labels, out(name), cols=cols)
        set_keys(ob)
        scene.render.resolution_x, scene.render.resolution_y = res

    sheet("11", "11_reglages_canal.png", cam_entree, [
        ("Base", {}),
        ("Anneau serre", {"Anneau_Serre": 1}),
        ("Anneau large", {"Anneau_Large": 1}),
        ("Chambre large", {"Chambre_Large": 1}),
        ("Chambre fine", {"Chambre_Fine": 1}),
        ("Anneau serre + chambre large", {"Anneau_Serre": 1, "Chambre_Large": 1}),
    ], tile=(800, 500))

    if want("05"):
        tiles, labels = [], []
        scene.render.resolution_x, scene.render.resolution_y = (320, 200) if QUICK else (800, 500)
        for var in CANAL_VARIANTS:
            set_keys(ob, **{f"Canal_{var}": 1.0})
            tiles.append(studio.render(scene, out(f"_tile_{var}.png"), cam_canal))
            labels.append(var.replace("_", " + "))
        studio.contact_sheet(tiles, labels, out("05_variantes_canal.png"), cols=3)
    set_keys(ob)
    ob.modifiers.remove(boolean)
    bpy.data.objects.remove(cutter)
    coupe.hide_render = True
    key.hide_render = False
    scene.render.resolution_x, scene.render.resolution_y = res

    # ---------------------------------------------------------------- latex semi-transparent
    ctl.inputs["Transparence"].default_value = 0.9
    scene.cycles.samples = 24 if QUICK else 160
    shot("06_latex_transparent.png", cam_34)
    ctl.inputs["Transparence"].default_value = 0.0
    scene.cycles.samples = 16 if QUICK else 64
    sheet("10", "10_reglages_vulve.png", cam_face, [
        ("Base", {}),
        ("Vulve grande", {"Vulve_Grande": 1}),
        ("Vulve petite", {"Vulve_Petite": 1}),
        ("Levres gonflees", {"Levres_Gonflees": 1}),
        ("Levres fines", {"Levres_Fines": 1}),
        ("Branches longues", {"Fente_Branches_Longues": 1}),
        ("Branches courtes", {"Fente_Branches_Courtes": 1}),
        ("Pointe allongee", {"Pointe_Allongee": 1}),
        ("Pointe arrondie", {"Pointe_Arrondie": 1}),
    ])
    ctl.inputs["Transparence"].default_value = 0.9
    scene.cycles.samples = 16 if QUICK else 64

    # ---------------------------------------------------------------- topologie
    col, topo = topology_overlay(ob)
    ob.hide_render = True
    shot("07_topologie_face.png", cam_face)
    shot("08_topologie_34.png", cam_34)


main()
