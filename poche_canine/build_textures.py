"""UV et textures du vagin de poche : output/poche_canine/textures/ + poche_canine_textures.blend.

Usage : python poche_canine/build_textures.py [--res=4096|8192] [--quick] [--no-render]

Cartes produites (PNG 8 bits, prêtes pour Unity URP Lit) :
- Poche_Canine_BaseColor_<res>.png : couleur du latex, teinte de la vulve, intérieur (sRGB)
- Poche_Canine_Normal_<res>.png    : normal map tangente (OpenGL, comme Unity) : petits plis
                                     vers la pointe de la vulve, grain fin des lèvres
- Poche_Canine_AO_<res>.png        : occlusion ambiante (fente, pli du contour, canal)
- Poche_Canine_Masques_<res>.png   : R = vulve, G = intérieur (recoloration dans Unity)
"""
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from lib import studio  # noqa: E402
from lib.bake import cuire, materiau_emission, nouvelle_image  # noqa: E402
from lib.materials import latex_controls  # noqa: E402
from lib.uv import materiau_damier, planche_uv  # noqa: E402
from poche_canine.objet import make_sleeve, zones  # noqa: E402
from poche_canine.sleeve import build  # noqa: E402

OUT = os.path.join(ROOT, "output", "poche_canine")
TEX = os.path.join(OUT, "textures")
QUICK = "--quick" in sys.argv
RES = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--res=")), "4096"))
if QUICK:
    RES = 1024
SUFFIXE = f"{RES // 1024}k"


def attribut(nt, nom, sortie="Fac"):
    n = nt.nodes.new("ShaderNodeAttribute")
    n.attribute_name = nom
    return n.outputs[sortie]


def math_(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, bpy.types.NodeSocket):
            nt.links.new(v, n.inputs[i])
        else:
            n.inputs[i].default_value = v
    return n.outputs[0]


def mix_couleur(nt, fac, a, b):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    nt.links.new(fac, n.inputs[0])
    for sock, val in ((n.inputs[6], a), (n.inputs[7], b)):
        if isinstance(val, bpy.types.NodeSocket):
            nt.links.new(val, sock)
        else:
            sock.default_value = val
    return n.outputs[2]


def materiaux_cuisson(reglages):
    """Matériaux dédiés à chaque carte, avec les couleurs du matériau latex de la poche."""
    def couleur(nt):
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(attribut(nt, "Masques", "Color"), sep.inputs["Color"])
        fv = math_(nt, "MULTIPLY", sep.outputs["Red"], reglages["Teinte Vulve"], clamp=True)
        fi = math_(nt, "MULTIPLY", sep.outputs["Green"], reglages["Teinte Interieur"], clamp=True)
        c1 = mix_couleur(nt, fv, reglages["Couleur"], reglages["Couleur Vulve"])
        return mix_couleur(nt, fi, c1, reglages["Couleur Interieur"])

    def masques(nt):
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(attribut(nt, "Masques", "Color"), sep.inputs["Color"])
        comb = nt.nodes.new("ShaderNodeCombineColor")
        nt.links.new(sep.outputs["Red"], comb.inputs["Red"])
        nt.links.new(sep.outputs["Green"], comb.inputs["Green"])
        return comb.outputs["Color"]

    return materiau_emission("Cuisson_Couleur", couleur), materiau_emission("Cuisson_Masques", masques), relief()


def relief():
    """Relief fin cuit dans la normal map : plis concentriques autour de la pointe basse de la
    vulve (là où la fente se termine), grain très fin sur les lèvres."""
    m = bpy.data.materials.new("Cuisson_Relief")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    bruit = nt.nodes.new("ShaderNodeTexNoise")
    bruit.inputs["Scale"].default_value = 120.0
    nt.links.new(coord.outputs["Object"], bruit.inputs["Vector"])
    grain = nt.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 900.0
    grain.inputs["Detail"].default_value = 4.0
    nt.links.new(coord.outputs["Object"], grain.inputs["Vector"])

    t = attribut(nt, "levre_t")
    pointe = attribut(nt, "pointe")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(attribut(nt, "Masques", "Color"), sep.inputs["Color"])
    # phase des plis : ~9 plis à travers la lèvre, ondulés par un bruit
    phase = math_(nt, "ADD", math_(nt, "MULTIPLY", t, 9.0),
                  math_(nt, "MULTIPLY", math_(nt, "SUBTRACT", bruit.outputs["Fac"], 0.5), 1.4))
    s = math_(nt, "ABSOLUTE", math_(nt, "SINE", math_(nt, "MULTIPLY", phase, math.pi)))
    pli = math_(nt, "SUBTRACT", 1.0, math_(nt, "POWER", s, 0.35))
    fenetre = math_(nt, "POWER", math_(nt, "SINE", math_(nt, "MULTIPLY", t, math.pi), clamp=True), 0.7)
    plis = math_(nt, "MULTIPLY", math_(nt, "MULTIPLY", pli, fenetre), pointe)
    micro = math_(nt, "MULTIPLY", math_(nt, "SUBTRACT", grain.outputs["Fac"], 0.5), sep.outputs["Red"])
    hauteur = math_(nt, "ADD", math_(nt, "MULTIPLY", plis, -1.0), math_(nt, "MULTIPLY", micro, 0.12))
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 0.0004
    nt.links.new(hauteur, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m


def materiau_texture(images, reglages):
    """Matériau de contrôle utilisant les textures cuites (comme dans Unity)."""
    m = bpy.data.materials.new("Latex_Poche_Textures")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]

    def tex(cle):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = images[cle]
        return n

    base = tex("BaseColor").outputs["Color"]
    ao = tex("AO").outputs["Color"]
    teinte = nt.nodes.new("ShaderNodeMix")
    teinte.data_type = "RGBA"
    teinte.blend_type = "MULTIPLY"
    teinte.inputs[0].default_value = 0.6
    nt.links.new(base, teinte.inputs[6])
    nt.links.new(ao, teinte.inputs[7])
    nt.links.new(teinte.outputs[2], p.inputs["Base Color"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "UVMap"
    nt.links.new(tex("Normal").outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
    p.inputs["Roughness"].default_value = 0.55 - 0.53 * reglages["Reflet"]
    p.inputs["Coat Weight"].default_value = reglages["Reflet"] ** 2
    p.inputs["Coat Roughness"].default_value = 0.05
    p.inputs["IOR"].default_value = 1.5
    p.inputs["Transmission Weight"].default_value = 0.0
    return m


def main():
    os.makedirs(TEX, exist_ok=True)
    scene = studio.reset_scene()
    poche, mat = make_sleeve()                       # maillage + UV + shape keys
    poche.modifiers["Subdivision"].levels = 2         # même géométrie lissée pour la cuisson
    poche.modifiers["Subdivision"].render_levels = 2
    ctl = latex_controls(mat)
    reglages = {i.name: (tuple(i.default_value) if hasattr(i.default_value, "__len__") else i.default_value)
                for i in ctl.inputs}

    world = bpy.data.worlds.new("Monde_Cuisson")
    world.light_settings.distance = 0.02              # portée de l'occlusion ambiante : 2 cm
    scene.world = world

    m_couleur, m_masques, m_relief = materiaux_cuisson(reglages)
    images = {}
    t0 = time.time()
    for cle, typ, m, couleur, ech in (("BaseColor", "EMIT", m_couleur, True, 1),
                                      ("Masques", "EMIT", m_masques, False, 1),
                                      ("Normal", "NORMAL", m_relief, False, 4),
                                      ("AO", "AO", None, False, 16 if QUICK else 64)):
        img = nouvelle_image(f"Poche_Canine_{cle}_{SUFFIXE}", RES, couleur)
        cuire(poche, img, os.path.join(TEX, f"Poche_Canine_{cle}_{SUFFIXE}.png"), typ, m, ech)
        images[cle] = img
        print(f"{cle} cuit en {time.time() - t0:.0f} s")

    mtex = materiau_texture(images, reglages)
    poche.data.materials.append(mtex)                 # 2e matériau disponible (non assigné)
    nom_blend = "poche_canine_textures.blend" if RES == 4096 else f"poche_canine_textures_{SUFFIXE}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, nom_blend), compress=True)
    bpy.ops.file.make_paths_relative()                # textures en chemins relatifs (//textures/...)
    bpy.ops.wm.save_mainfile(compress=True)
    if "--no-render" in sys.argv:
        return

    # ---------------------------------------------------------------- rendus de contrôle
    poche.modifiers["Subdivision"].levels = 1
    studio.backdrop(scale=3.0)
    studio.setup_render(scene, (640, 480) if QUICK else (1200, 900), 16 if QUICK else 64)
    studio.area_light("Cle", (-0.35, -0.45, 0.45), (0, 0.04, 0.06), 0.4, 14)
    studio.area_light("Contre", (0.35, 0.30, 0.30), (0, 0.04, 0.06), 0.25, 8, (0.95, 0.97, 1.0))
    studio.area_light("Debouche", (0.45, -0.35, 0.10), (0, 0.04, 0.06), 0.45, 3)
    cam_34 = studio.camera("Cam_34", (-0.26, -0.34, 0.22), (0.0, 0.05, 0.055), 60)
    cam_face = studio.camera("Cam_Face", (0.0, -0.42, 0.075), (0, 0, 0.068), 85)
    cam_pointe = studio.camera("Cam_Pointe", (-0.03, -0.11, 0.035), (0.0, -0.008, 0.032), 85)
    poche.material_slots[0].material = mtex

    def out(n):
        return os.path.join(OUT, n)

    tuiles = [(studio.render(scene, out("_t42_0.png"), cam_34), "Textures, trois-quarts"),
              (studio.render(scene, out("_t42_1.png"), cam_face), "Textures, face"),
              (studio.render(scene, out("_t42_2.png"), cam_pointe), "Plis vers la pointe (normal map)")]
    poche.material_slots[0].material = mat
    ctl.inputs["Transparence"].default_value = 0.9
    tuiles.append((studio.render(scene, out("_t42_3.png"), cam_34), "Latex transparent (matériau procédural)"))
    studio.contact_sheet([t[0] for t in tuiles], [t[1] for t in tuiles], out("42_rendu_textures.png"), cols=2)

    # damier et planche UV colorée par zone
    poche.material_slots[0].material = materiau_damier()
    tuiles = [studio.render(scene, out("_t40_0.png"), cam_34), studio.render(scene, out("_t40_1.png"), cam_face)]
    studio.contact_sheet(tuiles, ["Damier UV, trois-quarts", "Damier UV, face"], out("40_uv_damier.png"), cols=2)
    _, _, _, infos = build()
    z, N, R = zones(infos), infos["N"], len(infos["tags"])
    pal = [(200, 80, 80), (230, 150, 60), (220, 60, 200), (60, 160, 230), (90, 200, 110), (230, 230, 80)]
    cols = []
    for pl in poche.data.polygons:
        r = pl.index // N
        if pl.index >= (R - 1) * N:
            cols.append(pal[5])
        else:
            cols.append(pal[0 if r < z["coupe_canal"] else 1 if r < z["fente"] else 2 if r < z["bord_vulve"]
                            else 3 if r < z["bord_face"] else 4])
    planche_uv(poche, out("41_uv_disposition.png"), 2048, cols)

    # planche des cartes
    from PIL import Image
    vignettes = []
    for cle in ("BaseColor", "Normal", "AO", "Masques"):
        p = out(f"_t43_{cle}.png")
        Image.open(os.path.join(TEX, f"Poche_Canine_{cle}_{SUFFIXE}.png")).convert("RGB").resize((1024, 1024)).save(p)
        vignettes.append(p)
    studio.contact_sheet(vignettes, [f"{c} {SUFFIXE}" for c in ("BaseColor", "Normal", "AO", "Masques")],
                         out("43_cartes_textures.png"), cols=4)


main()
