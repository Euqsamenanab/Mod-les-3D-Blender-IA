"""Scène de simulation physique : output/poche_canine/test_physique.blend + rendus 30 à 32.

Usage : python poche_canine/build_physique.py [--fps=30] [--boucles=1] [--vitesse=1] [--quick] [--no-render]
        python poche_canine/build_physique.py --video [--fps=30] [--boucles=1] [--res=1920x1080] [--samples=64]
                                              [--camera=exterieur|coupe] [--png --debut=1 --fin=170]
        python poche_canine/build_physique.py --assembler [mêmes options]   (images PNG -> MP4)

Un cycle dure 11,3 s à vitesse 1, quelle que soit la cadence (--fps) : entrée jusqu'à
6,7 s, maintien en butée jusqu'à 7,9 s, retrait jusqu'à 10,8 s, retour au repos.
--boucles=N enchaîne N cycles ; la première et la dernière image sont identiques, la
vidéo boucle donc sans à-coup. --vitesse=2 rend le mouvement deux fois plus rapide.
Le .blend est prêt pour le rendu vidéo : caméras « Cam_Exterieur » (latex transparent)
et « Cam_Coupe », éclairage studio, sortie MP4 H.264 1920 x 1080 dans //rendu/.

Principe (hybride, stable et propre) :
- Poche_Proxy (masquée, ~4 200 sommets) : modificateur « Cible » (forme cible de la
  déformation, calculée sur la vraie position du jouet) puis « Cloth » en mode
  Dynamic Mesh. La simulation suit la forme cible avec l'inertie, le retard et les
  ondulations du latex ; le maintien (rappel vers la cible) est faible dans le canal
  et les lèvres, fort sur la surface extérieure tenue en main.
- Poche_Canine (visible) : la poche détaillée suit le proxy (Surface Deform).
- Jouets : animés le long de l'axe du canal (images 1 à 260 : entrée, butée,
  maintien, retrait). Un jouet souple se tasse et fléchit (« Cible_Jouet »), calculé
  contre Poche_Repos, copie figée de la poche.
- Reglages_Physique : « Rigidité latex », « Rigidité jouet », « Flexion » (drivers).
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from deformation import coupe, physique  # noqa: E402
from deformation.insertion import arbre_cible_jouet, arbre_insertion  # noqa: E402
from jouets.generateurs import creer_jouet  # noqa: E402
from lib import studio  # noqa: E402
from lib.materials import latex_controls, latex_material  # noqa: E402
from poche_canine.objet import make_sleeve  # noqa: E402
from poche_canine.sleeve import build  # noqa: E402

OUT = os.path.join(ROOT, "output", "poche_canine")
QUICK = "--quick" in sys.argv
RENDER = "--no-render" not in sys.argv
ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)


def option(nom, defaut):
    return next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{nom}=")), defaut)


FPS = int(option("fps", "30"))
VIDEO = "--video" in sys.argv
ASSEMBLER = "--assembler" in sys.argv

PROXY = dict(N=48, canal_step=0.004, M_lip=10, M_vest=8, face_s=(0.1, 0.3, 0.6, 1.0),
             corner_n=3, side_step=0.02, back_n=4, end_n=3)
COULEURS = {"lisse": (0.30, 0.55, 0.95, 1.0), "perles": (0.55, 0.30, 0.85, 1.0), "noue": (0.80, 0.30, 0.36, 1.0)}
BOUCLES = int(option("boucles", "1"))
VITESSE = float(option("vitesse", "1"))
# moments clés d'un cycle (secondes) : fin de l'entrée, fin du maintien, fin du retrait, fin du repos
T_ENTREE, T_MAINTIEN, T_RETRAIT, T_CYCLE = (t / VITESSE for t in (160 / 24, 190 / 24, 260 / 24, 272 / 24))


def image(t):
    """Numéro d'image correspondant à l'instant t (s) à la cadence choisie."""
    return 1 + round(t * FPS)


FIN = image(BOUCLES * T_CYCLE)


def want(tag):
    return ONLY is None or tag in ONLY


def sid(mod, name):
    return next(s.identifier for s in mod.node_group.interface.items_tree
                if s.item_type == "SOCKET" and s.in_out == "INPUT" and s.name == name)


def driver(ob, mod, entree, controle, prop):
    fc = ob.driver_add(f'modifiers["{mod.name}"]["{sid(mod, entree)}"]')
    drv = fc.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "v"
    var.targets[0].id = controle
    var.targets[0].data_path = f'["{prop}"]'
    drv.expression = "v"


def longueur(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    co = np.empty(len(ev.data.vertices) * 3)
    ev.data.vertices.foreach_get("co", co)
    return float(co.reshape(-1, 3)[:, 2].max())


def build_scene(actif="noue"):
    scene = studio.reset_scene()
    scene.frame_start, scene.frame_end = 1, FIN
    scene.render.fps = FPS

    controle = bpy.data.objects.new("Reglages_Physique", None)
    scene.collection.objects.link(controle)
    for prop, val, info in (("Rigidité latex", 0.3, "0 = latex très souple, 1 = rigide"),
                            ("Rigidité jouet", 1.0, "0 = jouet très souple, 1 = rigide"),
                            ("Flexion", 0.6, "part du tassement d'un jouet souple absorbée en flexion")):
        controle[prop] = val
        ui = controle.id_properties_ui(prop)
        ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description=info)

    # ---- poche détaillée (visible) et copie figée (référence des jouets)
    poche, mat_poche = make_sleeve("Poche_Canine", subdivision=False)
    zc, fond = poche["axe_canal_z"], poche["profondeur_canal"]
    repos = bpy.data.objects.new("Poche_Repos", poche.data)   # même maillage, sans modificateur
    scene.collection.objects.link(repos)
    studio.invisible(repos)

    # ---- jouets
    jouets = {}
    for kind in ("lisse", "perles", "noue"):
        mat = latex_material(f"Latex_{kind.capitalize()}", Couleur=COULEURS[kind], Transparence=0.0, Reflet=0.75)
        ob = creer_jouet(kind, mat, subdivision=(0, 2))   # vue : léger pour la lecture ; rendu : lisse
        cj = ob.modifiers.new("Cible_Jouet", "NODES")
        cj.node_group = bpy.data.node_groups.get("Cible_Jouet") or arbre_cible_jouet()
        cj[sid(cj, "Poche repos")] = repos
        cj[sid(cj, "Fond du canal")] = fond
        physique.deplacer_avant(ob, "Cible_Jouet", "Subdivision")
        for entree, prop in (("Rigidité poche", "Rigidité latex"), ("Rigidité jouet", "Rigidité jouet"),
                             ("Flexion", "Flexion")):
            driver(ob, cj, entree, controle, prop)
        ob.rotation_euler = (-math.pi / 2, 0.0, 0.0)
        ob.location = (0.0, -0.4, zc)
        jouets[kind] = ob
    for kind, ob in jouets.items():
        L = longueur(ob)
        for b in range(BOUCLES):
            t0 = b * T_CYCLE
            for t, pointe in ((0.0, -0.02), (T_ENTREE, fond + 0.015), (T_MAINTIEN, fond + 0.015),
                              (T_RETRAIT, -0.02), (T_CYCLE, -0.02)):
                ob.location = (0.0, pointe - L, zc)
                ob.keyframe_insert("location", frame=image(t0 + t))
        if kind != actif:
            ob.hide_render = True
            ob.hide_set(True)

    # ---- proxy simulé
    v, f, _, _ = build(**PROXY)
    proxy = studio.mesh_object("Poche_Proxy", v, f)
    physique.groupe(proxy, "Maintien", physique.poids_maintien_poche(v, zc, souple=0.3))
    cible = proxy.modifiers.new("Cible", "NODES")
    cible.node_group = arbre_insertion("cible")
    cible[sid(cible, "Jouet")] = jouets[actif]
    cible[sid(cible, "Axe canal Z")] = zc
    cible[sid(cible, "Fond du canal")] = fond
    driver(proxy, cible, "Rigidité poche", controle, "Rigidité latex")
    cloth = physique.cloth_latex(proxy, "Maintien", controle, "Rigidité latex", 2.5, 0.06)
    cloth.settings.quality = max(4, round(8 * 24 / FPS))   # même précision par seconde
    cloth.collision_settings.use_collision = False
    cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, FIN
    studio.invisible(proxy)
    proxy.hide_set(True)

    # ---- la poche détaillée suit le proxy
    scene.frame_set(1)
    sd = poche.modifiers.new("Suivi_Simulation", "SURFACE_DEFORM")
    sd.target = proxy
    with bpy.context.temp_override(object=poche, active_object=poche):
        bpy.ops.object.surfacedeform_bind(modifier=sd.name)
    studio.add_subsurf(poche, 0, 2)
    coupe.ajouter(poche, False)
    preparer_rendu(scene, poche)
    return scene, controle, poche, mat_poche, proxy, cloth, jouets


def preparer_rendu(scene, poche):
    """Studio, caméras et réglages de rendu vidéo enregistrés dans le .blend."""
    zc = poche["axe_canal_z"]
    studio.backdrop(scale=3.0)
    studio.setup_render(scene, (1920, 1080), 64)
    scene.cycles.device = "GPU"   # utilise le GPU s'il est configuré dans les préférences, sinon le CPU
    studio.area_light("Cle", (-0.45, -0.55, 0.6), (0.0, 0.0, 0.06), 0.5, 30)
    studio.area_light("Contre", (0.45, 0.45, 0.4), (0.0, 0.05, 0.08), 0.3, 12, (0.95, 0.97, 1.0))
    studio.area_light("Coupe", (0.5, 0.0, 0.45), (0, 0.02, zc), 0.6, 20)
    cam_ext = studio.camera("Cam_Exterieur", (-0.46, -0.24, 0.24), (0.0, 0.0, 0.05), 35)
    studio.camera("Cam_Coupe", (0.52, 0.02, zc + 0.28), (0, 0.02, zc), 40)
    scene.camera = cam_ext
    r = scene.render
    r.image_settings.file_format = "FFMPEG"
    r.ffmpeg.format = "MPEG4"
    r.ffmpeg.codec = "H264"
    r.ffmpeg.constant_rate_factor = "HIGH"
    r.ffmpeg.ffmpeg_preset = "GOOD"
    r.filepath = "//rendu/physique_noue_"


def simuler(scene, jusqua):
    for frame in range(1, jusqua + 1):
        scene.frame_set(frame)


def main():
    os.makedirs(OUT, exist_ok=True)
    scene, controle, poche, mat_poche, proxy, cloth, jouets = build_scene()
    print("proxy", len(proxy.data.vertices), "sommets ; liaison Surface Deform :", poche.modifiers["Suivi_Simulation"].is_bound)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "test_physique.blend"), compress=True)
    if not RENDER:
        return

    if VIDEO:
        return video(scene, poche, mat_poche)
    if ASSEMBLER:
        return assembler(scene)

    zc = poche["axe_canal_z"]
    res = (480, 300) if QUICK else (800, 500)
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.cycles.samples = 12 if QUICK else 48
    scene.cycles.device = "CPU"
    scene.render.image_settings.file_format = "PNG"
    scene.camera = studio.camera("Cam_Coupe_Validation", (0.40, 0.09, zc + 0.22), (0, 0.09, zc), 50)
    bpy.data.objects["Cle"].hide_render = True
    latex_controls(mat_poche).inputs["Transparence"].default_value = 0.0
    coupe.regler(poche, True)

    def out(name):
        return os.path.join(OUT, name)

    # ---- séquence du jouet noué (entrée, nœud, butée, retrait)
    if want("30") or want("gif"):
        images = tuple(image(f / 24) for f in (40, 80, 120, 160, 210, 235))
        tiles, labels, gif = [], [], []
        for frame in range(1, FIN + 1):
            scene.frame_set(frame)
            if want("gif") and frame % max(1, round(FPS / 6)) == 1:
                scene.render.resolution_x, scene.render.resolution_y = (320, 200) if QUICK else (480, 300)
                scene.cycles.samples = 8
                gif.append(studio.render(scene, out(f"_gif_{frame:03d}.png")))
                scene.render.resolution_x, scene.render.resolution_y = res
                scene.cycles.samples = 12 if QUICK else 48
            if want("30") and frame in images:
                tiles.append(studio.render(scene, out(f"_tile_30_{frame}.png")))
                labels.append(f"{(frame - 1) / FPS:.1f} s")
        if tiles:
            studio.contact_sheet(tiles, labels, out("30_physique_noue.png"), cols=3)
        if gif:
            from PIL import Image
            ims = [Image.open(p).convert("P", palette=Image.ADAPTIVE) for p in gif]
            ims[0].save(out("physique_noue.gif"), save_all=True, append_images=ims[1:], duration=120, loop=0)
            for p in gif:
                os.remove(p)

    # ---- rigidités : latex souple / ferme, jouet souple
    if want("31"):
        tiles, labels = [], []
        for label, props in (("Latex souple (0.1)", {"Rigidité latex": 0.1}),
                             ("Latex ferme (0.8)", {"Rigidité latex": 0.8}),
                             ("Jouet souple (0.15), latex 0.3", {"Rigidité jouet": 0.15}),
                             ("Jouet rigide, latex 0.3", {})):
            controle["Rigidité latex"], controle["Rigidité jouet"] = 0.3, 1.0
            for k, val in props.items():
                controle[k] = val
            # invalide le cache de simulation, puis recalcule depuis l'image 1
            cloth.point_cache.frame_start = 1
            cloth.settings.quality = cloth.settings.quality
            scene.frame_set(1)
            simuler(scene, image(170 / 24))
            tiles.append(studio.render(scene, out(f"_tile_31_{len(tiles)}.png")))
            labels.append(label)
        studio.contact_sheet(tiles, labels, out("31_physique_rigidites.png"), cols=2)


def nom_video():
    h = option("res", "1920x1080").split("x")[1]
    return f"physique_noue_{option('camera', 'exterieur')}_{h}p{FPS}_x{BOUCLES}"


def video(scene, poche, mat_poche):
    """Rendu de l'animation : MP4 direct, ou images PNG par tranche (--png --debut --fin)."""
    w, h = (int(x) for x in option("res", "1920x1080").split("x"))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.cycles.samples = int(option("samples", "64"))
    scene.cycles.device = "CPU"
    if option("camera", "exterieur") == "coupe":
        scene.camera = bpy.data.objects["Cam_Coupe"]
        latex_controls(mat_poche).inputs["Transparence"].default_value = 0.0
        coupe.regler(poche, True)
    os.makedirs(os.path.join(OUT, "rendu"), exist_ok=True)
    debut, fin = int(option("debut", "1")), int(option("fin", str(FIN)))
    simuler(scene, fin)                     # remplit le cache de la simulation, dans l'ordre
    if "--png" in sys.argv:
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = os.path.join(OUT, "rendu", nom_video(), "####")
    else:
        scene.render.filepath = os.path.join(OUT, "rendu", nom_video() + "_")
    scene.frame_start, scene.frame_end = debut, fin
    bpy.ops.render.render(animation=True)


def assembler(scene):
    """Assemble les images PNG rendues par tranches en une vidéo MP4 (séquenceur vidéo)."""
    dossier = os.path.join(OUT, "rendu", nom_video())
    images = sorted(f for f in os.listdir(dossier) if f.endswith(".png"))
    seq = scene.sequence_editor_create()
    strip = seq.sequences.new_image("images", os.path.join(dossier, images[0]), channel=1, frame_start=1)
    for f in images[1:]:
        strip.elements.append(f)
    scene.frame_start, scene.frame_end = 1, len(images)
    from PIL import Image
    w, h = Image.open(os.path.join(dossier, images[0])).size
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = w, h, 100
    scene.render.use_sequencer = True
    scene.render.filepath = os.path.join(OUT, "rendu", nom_video() + ".mp4")
    scene.render.use_file_extension = False
    bpy.ops.render.render(animation=True)
    print("vidéo :", scene.render.filepath)


main()
