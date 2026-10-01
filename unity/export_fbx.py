"""Export FBX pour Unity 6 (URP) : output/unity/*.fbx.

Usage : python unity/export_fbx.py [--subdiv-poche=1] [--subdiv-jouets=N] [--only=poche,lisse,perles,noue,...]

`--only` accepte aussi les variantes de la poche (Poche_Oeuf_Bulbe, Poche_Sablier_Coeur,
Poche_Fessier_Double, Poche_Sablier_Anus) ; par défaut, tout est exporté.

Subdivision par défaut : poche 1, jouets lisse et à perles 1, jouet noué 0 (son gabarit
est déjà dense : 160 x 300). `--subdiv-jouets` impose le même niveau à tous les jouets.

Chaque objet est « figé » : les modificateurs (Geometry Nodes, Subdivision) sont
appliqués, et chaque blend shape est recalculée à travers eux. Les blend shapes
suivent donc la géométrie subdivisée, et les réglages des jouets (taille du nœud,
épaisseur, longueur...) deviennent des blend shapes, car la topologie du gabarit ne
change jamais.

Repère Unity : Y en haut, mètres, échelle 1, rotation 0 (transformations appliquées).
- Poche : pivot au centre de l'entrée du canal ; la vulve regarde +Z (avant de l'objet),
  le canal s'enfonce vers -Z. Double entrée : pivot à l'entrée du vagin, anus au-dessus.
- Jouets : pivot au centre de la base ; la pointe vers +Y ; le dessous (urètre du
  jouet noué) vers -Z.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from jouets.generateurs import creer_jouet, regler  # noqa: E402
from lib import studio  # noqa: E402
from lib.materials import latex_material  # noqa: E402
from poche_canine.build_variantes import creer  # noqa: E402
from poche_canine.objet import make_sleeve, set_keys  # noqa: E402
from poche_canine.variantes import VARIANTES  # noqa: E402

OUT = os.path.join(ROOT, "output", "unity")


def option(nom, defaut):
    return next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{nom}=")), defaut)


SUBDIV_POCHE = int(option("subdiv-poche", "1"))
SUBDIV_JOUETS = {"lisse": 1, "perles": 1, "noue": 0}
if option("subdiv-jouets", None) is not None:
    SUBDIV_JOUETS = dict.fromkeys(SUBDIV_JOUETS, int(option("subdiv-jouets", None)))
SEULEMENT = option("only", ",".join(["poche", "lisse", "perles", "noue", *VARIANTES])).split(",")


def _fois(f, *noms):
    return lambda d: {n: d[n] * f for n in noms}


# Blend shapes des jouets : nom -> réglages GN modifiés (fonction des valeurs par défaut)
# ou shape key du gabarit à pousser à 1 (clé « _cle »).
DIAMETRES_NOUE = ("Diamètre pointe", "Diamètre gland", "Diamètre tige (gland)", "Diamètre tige (nœud)",
                  "Diamètre lobes", "Écart des lobes", "Diamètre col", "Bourrelet gland")
VARIANTES_JOUETS = {
    "lisse": {
        "Epais": _fois(1.2, "Diamètre", "Diamètre pointe"),
        "Fin": _fois(0.8, "Diamètre", "Diamètre pointe"),
        "Long": _fois(1.25, "Longueur"),
        "Court": _fois(0.8, "Longueur"),
    },
    "perles": {
        "Perles_Grosses": _fois(1.2, *(f"Perle {i}" for i in range(1, 9))),
        "Perles_Petites": _fois(0.8, *(f"Perle {i}" for i in range(1, 9))),
        "Ecarts_Grands": _fois(2.5, *(f"Écart {i}" for i in range(1, 9))),
        "Perles_Allongees": _fois(1.5, "Allongement perles"),
        "Tige_Epaisse": _fois(1.4, "Diamètre tige"),
    },
    "noue": {
        "Veines": {"_cle": "Veines"},
        "Noeud_Gros": _fois(1.2, "Diamètre lobes", "Écart des lobes", "Longueur nœud"),
        "Noeud_Petit": _fois(0.8, "Diamètre lobes", "Écart des lobes", "Longueur nœud"),
        "Gland_Gros": _fois(1.15, "Diamètre gland", "Longueur gland"),
        "Epais": _fois(1.15, *DIAMETRES_NOUE),
        "Fin": _fois(0.87, *DIAMETRES_NOUE),
        "Long": _fois(1.2, "Pointe → centre du nœud", "Longueur gland", "Longueur col"),
        "Court": _fois(0.85, "Pointe → centre du nœud", "Longueur gland", "Longueur col"),
    },
}
COULEURS = {"lisse": (0.30, 0.55, 0.95, 1.0), "perles": (0.55, 0.30, 0.85, 1.0), "noue": (0.80, 0.30, 0.36, 1.0)}


# --------------------------------------------------------------------------- figer
def coordonnees(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    ev.to_mesh_clear()
    return co.reshape(-1, 3)


def figer(ob, nom, variantes, decalage=(0.0, 0.0, 0.0)):
    """Copie `ob` avec ses modificateurs appliqués, et ajoute une shape key par variante.

    `variantes` : liste de (nom, appliquer, annuler), où appliquer/annuler modifient `ob`.
    """
    ob.name = ob.data.name = f"{nom}_source"         # libère le nom pour l'objet exporté
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.name = nom
    for a in [a.name for a in me.attributes
              if not a.name.startswith(".") and a.name not in ("position", "sharp_face", "material_index")
              and a.name not in me.uv_layers and a.name not in me.color_attributes]:
        me.attributes.remove(me.attributes[a])
    d = np.array(decalage, np.float32)
    base = coordonnees(ob) + d
    me.vertices.foreach_set("co", base.ravel())
    fige = bpy.data.objects.new(nom, me)
    bpy.context.scene.collection.objects.link(fige)
    fige.shape_key_add(name="Basis", from_mix=False)
    for nom_cle, appliquer, annuler in variantes:
        appliquer()
        co = coordonnees(ob) + d
        annuler()
        if co.shape != base.shape:
            raise RuntimeError(f"{nom} / {nom_cle} : topologie différente ({co.shape} vs {base.shape})")
        cle = fige.shape_key_add(name=nom_cle, from_mix=False)
        cle.data.foreach_set("co", co.ravel())
        print(f"  {nom_cle:24s} déplacement max {np.abs(co - base).max() * 1000:6.2f} mm")
    ob.hide_set(True)
    return fige


def exporter(ob, chemin):
    for o in bpy.context.view_layer.objects:
        o.select_set(o == ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(
        filepath=chemin, use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z", axis_up="Y", bake_space_transform=True,
        use_mesh_modifiers=False, mesh_smooth_type="FACE", use_tspace=False,
        colors_type="LINEAR", use_custom_props=False, add_leaf_bones=False,
        bake_anim=False, path_mode="AUTO", embed_textures=False,
    )
    taille = os.path.getsize(chemin) / 1e6
    me = ob.data
    print(f"-> {os.path.relpath(chemin, ROOT)} : {len(me.vertices)} sommets, {len(me.polygons)} faces, "
          f"{len(me.shape_keys.key_blocks) - 1} blend shapes, {taille:.1f} Mo")


# --------------------------------------------------------------------------- objets
def poche(nom="Poche_Canine"):
    if nom == "Poche_Canine":
        ob, _ = make_sleeve()
    else:
        ob, _, _ = creer(nom)
    ob.modifiers["Subdivision"].levels = SUBDIV_POCHE
    cles = [kb.name for kb in ob.data.shape_keys.key_blocks[1:]]
    variantes = [(c, (lambda c=c: set_keys(ob, **{c: 1.0})), (lambda: set_keys(ob))) for c in cles]
    set_keys(ob)
    fige = figer(ob, nom, variantes, decalage=(0.0, 0.0, -ob["axe_canal_z"]))
    print(f"  profondeur du canal : {ob['profondeur_canal'] * 100:.1f} cm")
    if "axe_anus_z" in ob:
        print(f"  anus : axe {(ob['axe_anus_z'] - ob['axe_canal_z']) * 100:.1f} cm au-dessus du pivot, "
              f"canal de {ob['profondeur_anus'] * 100:.1f} cm")
    return fige


def jouet(kind):
    mat = latex_material(f"Latex_{kind.capitalize()}", Couleur=COULEURS[kind], Transparence=0.0, Reflet=0.75)
    niveau = SUBDIV_JOUETS[kind]
    ob = creer_jouet(kind, mat, subdivision=(niveau, niveau))
    if not niveau:
        ob.modifiers.remove(ob.modifiers["Subdivision"])
    gn = ob.modifiers["Generateur"]
    tree = gn.node_group
    sockets = {s.name: s.identifier for s in tree.interface.items_tree
               if s.item_type == "SOCKET" and s.in_out == "INPUT" and s.socket_type != "NodeSocketGeometry"}
    defauts = {n: gn[i] for n, i in sockets.items()}

    def fabrique(spec):
        if isinstance(spec, dict):
            kb = ob.data.shape_keys.key_blocks[spec["_cle"]]

            def appliquer(v=1.0):
                kb.value = v
                ob.data.update()
            return appliquer, (lambda: appliquer(0.0))
        valeurs = spec(defauts)
        return (lambda: regler(ob, **{n.replace(" ", "_"): v for n, v in valeurs.items()}),
                lambda: regler(ob, **{n.replace(" ", "_"): defauts[n] for n in valeurs}))

    variantes = [(nom, *fabrique(spec)) for nom, spec in VARIANTES_JOUETS[kind].items()]
    return figer(ob, ob.name, variantes)


def main():
    os.makedirs(OUT, exist_ok=True)
    studio.reset_scene()
    for kind in SEULEMENT:
        print(f"== {kind}")
        ob = poche() if kind == "poche" else poche(kind) if kind in VARIANTES else jouet(kind)
        exporter(ob, os.path.join(OUT, f"{ob.name}.fbx"))


if __name__ == "__main__":
    main()
