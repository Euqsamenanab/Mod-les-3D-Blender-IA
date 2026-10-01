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
    """Coutures sur la structure en anneaux (bas de la poche, sous la pointe de la vulve, bord de
    la fente, contour de la vulve, bord de la face, fonds), dépliage, vulve en double densité."""
    N = infos["N"]
    z = zones(infos)

    def idx(r, k):
        return r * N + (k % N)

    coutures = [(idx(r, k), idx(r, k + 1)) for r in (0, z["coupe_canal"], z["fente"], z["bord_vulve"],
                                                       z["bord_face"], z["dos"]) for k in range(N)]
    coutures += [(idx(r, 0), idx(r + 1, 0)) for r in range(z["dos"])]   # ligne du dessous, d'un bout à l'autre
    marquer_coutures(ob, coutures)
    echelles = {r * N + k: 2.0 for r in range(z["fente"], z["bord_vulve"]) for k in range(N)}
    echelles.update({r * N + k: 1.2 for r in range(z["bord_vulve"], z["bord_face"]) for k in range(N)})
    deplier(ob, echelles)


def make_sleeve(name="Poche_Canine", subdivision=True):
    verts, faces, attrs, infos = build()
    rgba = np.column_stack([attrs["vulve"], attrs["interieur"], np.zeros(len(verts)), np.ones(len(verts))])
    mat = latex_material("Latex_Poche")
    ob = studio.mesh_object(name, verts, faces, [mat], attrs={"Masques": rgba})
    for nom in ("levre_t", "levre_k", "pointe"):
        a = ob.data.attributes.new(nom, "FLOAT", "POINT")
        a.data.foreach_set("value", attrs[nom].astype(np.float32))
    uv_poche(ob, infos)

    ob.shape_key_add(name="Basis", from_mix=False)

    def add_key(name, **overrides):
        v, _, _, _ = build(**overrides)
        k = ob.shape_key_add(name=name, from_mix=False)
        k.data.foreach_set("co", v.astype(np.float32).ravel())
        k.slider_min, k.slider_max = 0.0, 1.0
        return k

    for key_name, overrides in SHAPE_KEYS.items():
        add_key(key_name, **overrides)

    if subdivision:
        studio.add_subsurf(ob, 1, 2)
    ob["axe_canal_z"] = infos["axe_canal_z"]
    ob["profondeur_canal"] = infos["profondeur_canal"]
    return ob, mat


def set_keys(ob, **values):
    for kb in ob.data.shape_keys.key_blocks[1:]:
        kb.value = values.get(kb.name, 0.0)
