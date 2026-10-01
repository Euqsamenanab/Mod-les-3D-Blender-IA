"""Création de l'objet Blender du vagin de poche (maillage, masques, shape keys, matériau)."""
import numpy as np

from lib import studio
from lib.materials import latex_material
from poche_canine.sleeve import SHAPE_KEYS, build


def make_sleeve(name="Poche_Canine", subdivision=True):
    verts, faces, attrs, infos = build()
    rgba = np.column_stack([attrs["vulve"], attrs["interieur"], np.zeros(len(verts)), np.ones(len(verts))])
    mat = latex_material("Latex_Poche")
    ob = studio.mesh_object(name, verts, faces, [mat], attrs={"Masques": rgba})

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
