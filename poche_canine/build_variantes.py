"""Variantes du vagin de poche : un .blend par variante + planche d'aperçus rapides.

Usage : python poche_canine/build_variantes.py [--only=Poche_Oeuf_Bulbe,...] [--no-render]

Sorties : output/poche_canine/variantes/<Variante>.blend et 50_variantes.png (aperçus
basse définition : face, trois-quarts, profil, coupe).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from deformation import coupe  # noqa: E402
from lib import studio  # noqa: E402
from lib.materials import latex_controls  # noqa: E402
from poche_canine.objet import make_sleeve, set_keys  # noqa: E402
from poche_canine.variantes import VARIANTES, parametres  # noqa: E402

OUT = os.path.join(ROOT, "output", "poche_canine")
DOSSIER = os.path.join(OUT, "variantes")
RENDER = "--no-render" not in sys.argv
SEULES = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), list(VARIANTES))


def creer(nom):
    V = VARIANTES[nom]
    P, cles = parametres(V["forme"], V["levres"], V["anus"])
    ob, mat = make_sleeve(nom, params=P, cles=cles, materiau=V["materiau"], nom_materiau=f"Latex_{nom}")
    ob["variante"] = V["description"]
    return ob, mat, P


def apercus(scene, ob, mat, P, nom):
    """Quatre vues rapides (latex opaque pour lire la forme)."""
    studio.backdrop(scale=3.0)
    studio.setup_render(scene, (400, 300), 12)
    zc, A, L = P["B"], P["A"], P["L"]
    taille = max(P["A"], P["B"])
    studio.area_light("Cle", (-0.35, -0.45, 0.45), (0, 0.04, zc), 0.4, 14)
    studio.area_light("Contre", (0.35, 0.30, 0.30), (0, 0.04, zc), 0.25, 8, (0.95, 0.97, 1.0))
    studio.area_light("Debouche", (0.45, -0.35, 0.10), (0, 0.04, zc), 0.45, 3)
    lumiere_coupe = studio.area_light("Coupe", (0.45, 0.05, 0.40), (0, 0.10, zc), 0.5, 18)
    k = taille / 0.065
    cams = [
        ("face", studio.camera("Cam_Face", (0.0, -0.42 * k, zc + 0.01), (0, 0, zc), 70)),
        ("trois-quarts", studio.camera("Cam_34", (-0.30 * k, -0.36 * k, zc + 0.17 * k), (0, 0.05, zc - 0.01), 55)),
        ("profil", studio.camera("Cam_Profil", (-0.50 * k - 0.1, L / 2, zc + 0.02), (0, L / 2 - 0.01, zc), 55)),
        ("coupe", studio.camera("Cam_Coupe", (0.50 * k + 0.1, L / 2, zc + 0.03), (0, L / 2 - 0.01, zc), 55)),
    ]
    latex_controls(mat).inputs["Transparence"].default_value = 0.0
    coupe.ajouter(ob, actif=False)
    set_keys(ob)
    tuiles = []
    for vue, cam in cams:
        coupe.regler(ob, vue == "coupe")
        lumiere_coupe.hide_render = vue != "coupe"
        tuiles.append((studio.render(scene, os.path.join(OUT, f"_tile_{nom}_{vue}.png"), cam), f"{nom} : {vue}"))
    return tuiles


def main():
    os.makedirs(DOSSIER, exist_ok=True)
    tuiles = []
    for nom in SEULES:
        scene = studio.reset_scene()
        ob, mat, P = creer(nom)
        print(studio.mesh_report(ob))
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DOSSIER, f"{nom}.blend"), compress=True)
        if RENDER:
            tuiles += apercus(scene, ob, mat, P, nom)
    if tuiles:
        studio.contact_sheet([t[0] for t in tuiles], [t[1] for t in tuiles], os.path.join(OUT, "50_variantes.png"), cols=4)


if __name__ == "__main__":
    main()
