"""Onahole torse : output/torse/onahole_torse.blend + planche d'aperçus rapides.

Usage : python poche_canine/build_torse.py [--no-render]

Objets : « Onahole_Torse » (torse, vulve, anus, deux canaux, shape keys) et « Queue »
(enfant du torse, shape keys Queue_Chat / Queue_Loup, base = moignon). La propriété
« Echelle » du torse règle la taille de tout l'ensemble (1 = grandeur nature,
0.4 = petit jouet de poche, entrées et canaux compris, donc plus serrés).
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from lib import studio  # noqa: E402
from lib.geom import smoothstep  # noqa: E402
from lib.materials import latex_controls  # noqa: E402
from poche_canine import torse  # noqa: E402
from poche_canine.objet import make_sleeve, set_keys  # noqa: E402
from lib.uv import deplier, marquer_coutures  # noqa: E402
from poche_canine.queue import ANNEAUX, SEGMENTS, build_queue  # noqa: E402

OUT = os.path.join(ROOT, "output", "torse")
RENDER = "--no-render" not in sys.argv
MATERIAU = {"Couleur Vulve": (0.035, 0.022, 0.024, 1.0), "Teinte Vulve": 0.95,
            "Couleur Interieur": (0.70, 0.16, 0.22, 1.0)}
QUEUE_Z = 0.215                      # hauteur d'attache de la queue (repère du torse)


def masque_areoles(ob, P):
    """Canal B de « Masques » : aréoles (disques autour des tétons de la forme de base)."""
    me = ob.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    w = np.zeros(len(co))
    zs = 0.418 + 0.012 * P["t_seins_haut"] - 0.004
    for sx in (1, -1):
        phi = torse.DEVANT + sx * 0.45
        R = float(torse.rayon(P, np.array([phi]), np.array([zs]))[0])
        c = np.array([R * math.cos(phi), R * math.sin(phi), zs + torse.DECALAGE_Z])
        d = np.linalg.norm(co - c, axis=1)
        w = np.maximum(w, 1.0 - smoothstep((d - 0.0145) / 0.004))
    attr = me.color_attributes["Masques"]
    rgba = np.empty(len(co) * 4, np.float32)
    attr.data.foreach_get("color", rgba)
    rgba = rgba.reshape(-1, 4)
    rgba[:, 2] = w
    attr.data.foreach_set("color", rgba.ravel())


def creer_queue(P, torse_ob, mat):
    phi = math.pi / 2
    R = float(torse.rayon(P, np.array([phi]), np.array([QUEUE_Z]))[0])
    base = (0.0, R, QUEUE_Z + torse.DECALAGE_Z)
    v, f = build_queue("moignon", base)
    ob = studio.mesh_object("Queue", v, f, [mat])
    # UV : coutures autour des deux bouts et le long d'une génératrice, puis dépliage
    N, R = SEGMENTS, ANNEAUX - 2
    coutures = [(r * N + k, r * N + (k + 1) % N) for r in (0, R - 1) for k in range(N)]
    coutures += [(r * N + N // 2, (r + 1) * N + N // 2) for r in range(R - 1)]
    marquer_coutures(ob, coutures)
    deplier(ob)
    ob.shape_key_add(name="Basis", from_mix=False)
    for nom in ("chat", "loup"):
        vk, _ = build_queue(nom, base)
        k = ob.shape_key_add(name=f"Queue_{nom.capitalize()}", from_mix=False)
        k.data.foreach_set("co", vk.astype(np.float32).ravel())
    studio.add_subsurf(ob, 1, 2)
    ob.parent = torse_ob
    return ob


def echelle(ob):
    """Propriété « Echelle » (0,3 à 1) qui pilote l'échelle de l'objet (et de ses enfants)."""
    ob["Echelle"] = 1.0
    ui = ob.id_properties_ui("Echelle")
    ui.update(min=0.3, max=1.0, soft_min=0.3, soft_max=1.0,
              description="1 = grandeur nature, 0,4 = petit jouet de poche (entrées et canaux compris)")
    for i in range(3):
        fc = ob.driver_add("scale", i)
        drv = fc.driver
        drv.type = "AVERAGE"
        var = drv.variables.new()
        var.name = "e"
        var.targets[0].id = ob
        var.targets[0].data_path = '["Echelle"]'


def creer():
    P, cles = torse.parametres("bulbe")
    ob, mat = make_sleeve("Onahole_Torse", params=P, cles=cles, materiau=MATERIAU, nom_materiau="Latex_Torse")
    masque_areoles(ob, P)
    queue = creer_queue(P, ob, mat)
    echelle(ob)
    return ob, queue, mat, P


def apercus(scene, ob, queue, mat):
    studio.setup_render(scene, (420, 560), 12)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    zc = 0.42
    studio.area_light("Cle", (-1.0, -1.2, 1.3), (0, 0, zc), 1.0, 120)
    studio.area_light("Contre", (1.0, 1.0, 1.0), (0, 0, zc), 0.8, 60, (0.95, 0.97, 1.0))
    studio.area_light("Bas", (0.6, -0.9, 0.1), (0, 0, 0.2), 0.8, 30)
    latex_controls(mat).inputs["Transparence"].default_value = 0.0
    vues = [
        ("face", (0, -1.6, zc), (0, 0, zc), {}),
        ("profil, queue de chat", (-1.6, 0.05, zc), (0, 0.05, zc), {"Queue_Chat": 1.0}),
        ("dos, queue de loup", (0.35, 1.55, zc + 0.1), (0, 0.05, zc), {"Queue_Loup": 1.0}),
        ("trois-quarts", (-1.05, -1.15, zc + 0.35), (0, 0, zc), {}),
        ("entrejambe", (0.0, -0.05, -0.50), (0, 0.02, 0.12), {}),
        ("entrejambe, styles cœur + anus plissé", (0.0, -0.05, -0.50), (0, 0.02, 0.12),
         {"Style_Coeur": 1.0, "Anus_Plisse": 1.0}),
        ("seins gros, fesses grosses", (-1.05, -1.15, zc + 0.35), (0, 0, zc),
         {"Seins_Gros": 1.0, "Fesses_Grosses": 1.0, "Hanches_Larges": 1.0}),
        ("seins petits, muscles marqués", (-1.05, -1.15, zc + 0.35), (0, 0, zc),
         {"Seins_Petits": 1.0, "Muscles_Marques": 1.0, "Ventre_Plat": 1.0}),
    ]
    tuiles = []
    for i, (nom, loc, cible, cles) in enumerate(vues):
        set_keys(ob, **{k: v for k, v in cles.items() if not k.startswith("Queue_")})
        set_keys(queue, **{k: v for k, v in cles.items() if k.startswith("Queue_")})
        cam = studio.camera(f"Cam_{i}", loc, cible, 50 if i < 4 or i > 5 else 60)
        tuiles.append((studio.render(scene, os.path.join(OUT, f"_tile_{i}.png"), cam), nom))
    set_keys(ob)
    set_keys(queue)
    studio.contact_sheet([t[0] for t in tuiles], [t[1] for t in tuiles], os.path.join(OUT, "60_torse.png"), cols=4)


def main():
    os.makedirs(OUT, exist_ok=True)
    scene = studio.reset_scene()
    ob, queue, mat, P = creer()
    print(studio.mesh_report(ob))
    print(studio.mesh_report(queue))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "onahole_torse.blend"), compress=True)
    if RENDER:
        apercus(scene, ob, queue, mat)


if __name__ == "__main__":
    main()
