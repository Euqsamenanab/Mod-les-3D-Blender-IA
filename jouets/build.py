"""Construit les jouets seuls (output/jouets/jouets.blend) et rend les vues du jouet noué.

Usage : python jouets/build.py [--quick] [--no-render]
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from jouets.generateurs import creer_jouet  # noqa: E402
from lib import studio  # noqa: E402
from lib.materials import latex_material  # noqa: E402

OUT = os.path.join(ROOT, "output", "jouets")
QUICK = "--quick" in sys.argv
COULEURS = {"lisse": (0.30, 0.55, 0.95, 1.0), "perles": (0.55, 0.30, 0.85, 1.0), "noue": (0.80, 0.30, 0.36, 1.0)}


def main():
    os.makedirs(OUT, exist_ok=True)
    scene = studio.reset_scene()
    jouets = {}
    for i, kind in enumerate(("lisse", "perles", "noue")):
        mat = latex_material(f"Latex_{kind.capitalize()}", Couleur=COULEURS[kind], Transparence=0.0, Reflet=0.75)
        jouets[kind] = creer_jouet(kind, mat, location=(-0.12 + 0.12 * i, 0.0, 0.0))
    for ob in jouets.values():
        print(studio.mesh_report(ob))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "jouets.blend"), compress=True)
    if "--no-render" in sys.argv:
        return

    # vues du jouet noué seul, centré
    for kind, ob in jouets.items():
        ob.hide_render = kind != "noue"
    noue = jouets["noue"]
    noue.location = (0, 0, 0)
    studio.backdrop(scale=3.0)
    studio.setup_render(scene, (480, 640) if QUICK else (900, 1200), 16 if QUICK else 64)
    zc = 0.11
    studio.area_light("Cle", (-0.45, -0.5, 0.6), (0, 0, zc), 0.5, 30)
    studio.area_light("Contre", (0.45, 0.45, 0.45), (0, 0, zc), 0.3, 14, (0.95, 0.97, 1.0))
    studio.area_light("Bas", (0.0, 0.6, 0.15), (0, 0, zc), 0.4, 8)
    vues = [
        ("Profil", (-0.55, 0.0, zc), (0, 0, zc)),
        ("Dessous (uretre)", (0.0, 0.55, zc), (0, 0, zc)),
        ("Trois-quarts dessous", (-0.40, 0.38, zc + 0.08), (0, 0, zc)),
        ("Trois-quarts dessus", (0.38, -0.40, zc + 0.16), (0, 0, zc)),
    ]
    veines = noue.data.shape_keys.key_blocks["Veines"]
    veines.value = 0.0
    tiles, labels = [], []
    for i, (label, loc, target) in enumerate(vues):
        cam = studio.camera(f"Cam_{i}", loc, target, 50)
        tiles.append(studio.render(scene, os.path.join(OUT, f"_tile_{i}.png"), cam))
        labels.append(label)
    studio.contact_sheet(tiles, labels, os.path.join(OUT, "jouet_noue_vues.png"), cols=4)

    # shape key « Veines » : 0, 1 et gros plan
    tiles, labels = [], []
    plans = [
        ("Veines 0", 0.0, (-0.40, -0.30, zc + 0.10), (0, 0, zc + 0.02), 50),
        ("Veines 1", 1.0, (-0.40, -0.30, zc + 0.10), (0, 0, zc + 0.02), 50),
        ("Veines 1 (dessus)", 1.0, (0.30, -0.40, zc + 0.12), (0, 0, zc + 0.02), 50),
        ("Veines 1 (gros plan)", 1.0, (-0.12, -0.10, zc + 0.03), (0, 0, zc), 60),
    ]
    for i, (label, val, loc, target, lens) in enumerate(plans):
        veines.value = val
        cam = studio.camera(f"Cam_V{i}", loc, target, lens)
        tiles.append(studio.render(scene, os.path.join(OUT, f"_tile_v{i}.png"), cam))
        labels.append(label)
    studio.contact_sheet(tiles, labels, os.path.join(OUT, "jouet_noue_veines.png"), cols=4)
    veines.value = 0.0


if __name__ == "__main__":
    main()
