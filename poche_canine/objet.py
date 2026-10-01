"""Création de l'objet Blender du vagin de poche (maillage, masques, shape keys, matériau)."""
import numpy as np

from lib import studio
from lib.materials import latex_material
from lib.uv import deplier, marquer_coutures
from poche_canine.sleeve import SHAPE_KEYS, build


def zones(infos):
    """Indices d'anneaux qui délimitent les zones du maillage."""
    tags = infos["tags"]
    prof = infos["profondeurs"]
    r_fente = tags.index("fente")
    canal = [r for r in range(r_fente) if tags[r] == "canal"]
    return dict(
        fente=r_fente,
        bord_vulve=max(i for i, t in enumerate(tags) if t == "levres"),
        bord_face=max(i for i, t in enumerate(tags) if t == "face"),
        dos=len(tags) - 1,
        coupe_canal=min(canal, key=lambda r: abs(prof[r] - 0.095)),   # après la chambre du nœud
    )


def uv_poche(ob, infos):
    """Coutures fournies par le générateur (bas de la poche, sous la pointe de la vulve, bord
    de la fente, contour de la vulve, bord de la face, fonds), dépliage, densité par zone
    (vulve et anus en double densité)."""
    marquer_coutures(ob, infos["coutures"])
    zf = infos["zones_faces"]
    deplier(ob, {f: e for zone, e in infos["echelles_uv"].items() for f in zf.get(zone, ())})


def make_sleeve(name="Poche_Canine", subdivision=True, params=None, cles=None, materiau=None,
                nom_materiau="Latex_Poche"):
    """Objet de la poche : maillage, masques, UV, shape keys (cles : nom -> réglages), matériau."""
    verts, faces, attrs, infos = build(params)
    rgba = np.column_stack([attrs["vulve"], attrs["interieur"], np.zeros(len(verts)), np.ones(len(verts))])
    mat = latex_material(nom_materiau, **(materiau or {}))
    ob = studio.mesh_object(name, verts, faces, [mat], attrs={"Masques": rgba})
    for nom in ("levre_t", "levre_k", "pointe"):
        a = ob.data.attributes.new(nom, "FLOAT", "POINT")
        a.data.foreach_set("value", attrs[nom].astype(np.float32))
    uv_poche(ob, infos)

    ob.shape_key_add(name="Basis", from_mix=False)
    for key_name, overrides in (SHAPE_KEYS if cles is None else cles).items():
        v, _, _, _ = build(params, **overrides)
        k = ob.shape_key_add(name=key_name, from_mix=False)
        k.data.foreach_set("co", v.astype(np.float32).ravel())
        k.slider_min, k.slider_max = 0.0, 1.0

    if subdivision:
        studio.add_subsurf(ob, 1, 2)
    for cle in ("axe_canal_z", "profondeur_canal", "axe_anus_z", "profondeur_anus"):
        if cle in infos:
            ob[cle] = infos[cle]
    return ob, mat


def set_keys(ob, **values):
    for kb in ob.data.shape_keys.key_blocks[1:]:
        kb.value = values.get(kb.name, 0.0)
