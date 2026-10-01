"""Scène de test : vagin de poche + jouets réglables + test d'insertion en Geometry Nodes.

Usage : python poche_canine/build_test.py [--quick] [--no-render] [--only=20,22]

Dans le .blend produit (output/poche_canine/test_insertion.blend) :
- « Test_Insertion » : modificateur « Test_Insertion » -> choisir le jouet, faire glisser
  « Insertion » (animée de l'image 1 à 200), régler les rigidités, la diffusion, la flexion.
- « Poche_Canine_Source » (masqué) : le vagin de poche et ses shape keys ; les changer
  modifie directement le test.
- Jouet_Lisse / Jouet_Perles / Jouet_Noue : modificateur « Generateur » pour les tailles.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from deformation.insertion import arbre_insertion  # noqa: E402
from jouets.generateurs import creer_jouet, regler  # noqa: E402
from lib import studio  # noqa: E402
from lib.materials import latex_controls, latex_material  # noqa: E402
from poche_canine.objet import make_sleeve  # noqa: E402

OUT = os.path.join(ROOT, "output", "poche_canine")
QUICK = "--quick" in sys.argv
RENDER = "--no-render" not in sys.argv
ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)

COULEURS = {"lisse": (0.30, 0.55, 0.95, 1.0), "perles": (0.55, 0.30, 0.85, 1.0), "noue": (0.85, 0.22, 0.32, 1.0)}


def want(tag):
    return ONLY is None or tag in ONLY


def build_scene():
    scene = studio.reset_scene()
    poche, mat_poche = make_sleeve("Poche_Canine_Source", subdivision=False)
    studio.invisible(poche)
    poche.hide_set(True)

    jouets = {}
    for i, kind in enumerate(("lisse", "perles", "noue")):
        mat = latex_material(f"Latex_{kind.capitalize()}", Couleur=COULEURS[kind], Transparence=0.0, Reflet=0.75)
        jouets[kind] = creer_jouet(kind, mat, location=(0.16 + 0.09 * i, 0.05, 0.0))

    me = bpy.data.meshes.new("Test_Insertion")
    test = bpy.data.objects.new("Test_Insertion", me)
    scene.collection.objects.link(test)
    mod = test.modifiers.new("Test_Insertion", "NODES")
    mod.node_group = arbre_insertion()
    reglages(test, Poche=poche, Jouet=jouets["noue"], Axe_canal_Z=poche["axe_canal_z"],
             Fond_du_canal=poche["profondeur_canal"])

    # animation de l'insertion : entrée, butée au fond, maintien, retrait
    sid = socket(test, "Insertion")
    fond = poche["profondeur_canal"]
    for frame, val in ((1, -0.03), (100, fond + 0.02), (130, fond + 0.02), (200, -0.03)):
        mod[sid] = val
        test.keyframe_insert(data_path=f'modifiers["Test_Insertion"]["{sid}"]', frame=frame)
    scene.frame_start, scene.frame_end = 1, 200
    scene.frame_set(60)
    return scene, poche, mat_poche, jouets, test


def socket(ob, name, modifier="Test_Insertion"):
    tree = ob.modifiers[modifier].node_group
    return next(s.identifier for s in tree.interface.items_tree
                if s.item_type == "SOCKET" and s.in_out == "INPUT" and s.name == name)


def reglages(test, **values):
    mod = test.modifiers["Test_Insertion"]
    for key, val in values.items():
        mod[socket(test, key.replace("_", " "))] = val
    test.data.update()


def main():
    os.makedirs(OUT, exist_ok=True)
    scene, poche, mat_poche, jouets, test = build_scene()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "test_insertion.blend"), compress=True)
    if not RENDER:
        return

    test.animation_data_clear()  # les rendus fixent l'insertion à la main
    studio.backdrop(scale=3.0)
    res = (480, 360) if QUICK else (1200, 900)
    studio.setup_render(scene, res, 16 if QUICK else 64)
    zc = poche["axe_canal_z"]
    key = studio.area_light("Cle", (-0.45, -0.55, 0.6), (0.1, 0.05, 0.08), 0.5, 30)
    studio.area_light("Contre", (0.45, 0.45, 0.4), (0.1, 0.05, 0.08), 0.3, 12, (0.95, 0.97, 1.0))
    coupe = studio.area_light("Coupe", (0.5, 0.05, 0.45), (0, 0.05, zc), 0.6, 30)
    coupe.hide_render = True
    reglages(test, Subdivision=1 if QUICK else 2)
    ctl = latex_controls(mat_poche)

    def out(name):
        return os.path.join(OUT, name)

    def sheet(tag, name, cam, combos, setup, cols=2, tile=(800, 500)):
        if not want(tag):
            return
        scene.render.resolution_x, scene.render.resolution_y = (320, 200) if QUICK else tile
        tiles, labels = [], []
        for i, (label, values) in enumerate(combos):
            setup(values)
            tiles.append(studio.render(scene, out(f"_tile_{tag}_{i}.png"), cam))
            labels.append(label)
        studio.contact_sheet(tiles, labels, out(name), cols=cols)
        scene.render.resolution_x, scene.render.resolution_y = res

    # ---------------------------------------------------------------- jouets seuls
    test.hide_render = True
    cam_jouets = studio.camera("Cam_Jouets", (0.25, -0.80, 0.30), (0.25, 0.05, 0.155), 50)
    if want("20"):
        studio.render(scene, out("20_jouets.png"), cam_jouets)

    defauts = {}

    def regle_jouets(values):
        for kind, ob in jouets.items():
            regler(ob, **defauts.get(kind, {}))
        for kind, vals in values.items():
            regler(jouets[kind], **vals)

    sheet("21", "21_jouets_reglages.png", cam_jouets, [
        ("Réglages par défaut", {}),
        ("Réglages modifiés", {
            "lisse": dict(Diamètre=0.05, Diamètre_pointe=0.04, Longueur=0.26),
            "perles": {"Nombre_de_perles": 8, "Écart_1": 0.015, "Écart_3": 0.015, "Écart_5": 0.015,
                       "Perle_2": 0.022, "Perle_4": 0.03, "Perle_6": 0.038},
            "noue": {"Diamètre_nœud": 0.075, "Renflement_tige": 0.2, "Diamètre_tige": 0.042},
        }),
    ], lambda v: regle_jouets(v), cols=2, tile=(900, 675))
    defauts.update({
        "lisse": dict(Diamètre=0.042, Diamètre_pointe=0.032, Longueur=0.235),
        "perles": {"Nombre_de_perles": 6, "Écart_1": 0.006, "Écart_3": 0.006, "Écart_5": 0.006,
                   "Perle_2": 0.028, "Perle_4": 0.036, "Perle_6": 0.044},
        "noue": {"Diamètre_nœud": 0.062, "Renflement_tige": 0.08, "Diamètre_tige": 0.038},
    })
    regle_jouets({})

    # ---------------------------------------------------------------- insertions en coupe
    for ob in jouets.values():
        studio.invisible(ob)
    test.hide_render = False
    reglages(test, Vue_en_coupe=True)
    key.hide_render, coupe.hide_render = True, False
    ctl.inputs["Transparence"].default_value = 0.0
    cam_coupe = studio.camera("Cam_Coupe_Test", (0.40, 0.09, zc + 0.22), (0, 0.09, zc), 50)

    fond = poche["profondeur_canal"]
    sequences = {
        "22": ("lisse", "22_insertion_lisse.png", (0.03, 0.10, fond - 0.005, fond + 0.02)),
        "23": ("perles", "23_insertion_perles.png", (0.04, 0.11, fond - 0.005, fond + 0.02)),
        "24": ("noue", "24_insertion_noue.png", (0.06, 0.13, fond - 0.005, fond + 0.02)),
    }
    for tag, (kind, name, depths) in sequences.items():
        sheet(tag, name, cam_coupe,
              [(f"Insertion {d * 100:.1f} cm", d) for d in depths],
              lambda d, k=kind: reglages(test, Jouet=jouets[k], Insertion=d, Rigidité_jouet=1.0))

    sheet("25", "25_jouet_souple.png", cam_coupe, [
        ("Jouet rigide, butée au fond (+3 cm)", dict(Rigidité_jouet=1.0)),
        ("Jouet souple, butée au fond (+3 cm)", dict(Rigidité_jouet=0.15)),
        ("Latex souple (rigidité 0.1)", dict(Rigidité_jouet=1.0, Rigidité_poche=0.1)),
        ("Latex ferme (rigidité 0.8)", dict(Rigidité_jouet=1.0, Rigidité_poche=0.8)),
    ], lambda v: reglages(test, **{"Jouet": jouets["lisse"], "Insertion": fond + 0.03, "Rigidité_poche": 0.3, **v}))
    reglages(test, Rigidité_poche=0.3, Rigidité_jouet=1.0)

    # ---------------------------------------------------------------- vue extérieure, latex transparent
    reglages(test, Vue_en_coupe=False)
    coupe.hide_render, key.hide_render = True, False
    ctl.inputs["Transparence"].default_value = 0.9
    if want("26"):
        reglages(test, Jouet=jouets["noue"], Insertion=fond + 0.015)
        scene.cycles.samples = 24 if QUICK else 160
        cam = studio.camera("Cam_34_Test", (-0.30, -0.42, 0.26), (0.0, 0.04, 0.05), 50)
        studio.render(scene, out("26_insertion_transparente.png"), cam)


main()
