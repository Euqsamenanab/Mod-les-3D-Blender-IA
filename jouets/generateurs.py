"""Jouets de test procéduraux (Geometry Nodes) : lisse, à perles, à nœud stylisé.

Principe : un gabarit de maillage fixe (anneaux + caps en grille, 100 % quads) porte
deux attributs, `t` (0 = centre de la base, 1 = centre de la pointe) et `theta`
(angle). L'arbre Geometry Nodes calcule un profil de révolution r(w) à partir des
réglages, le transforme en courbe, puis place chaque sommet du gabarit à l'abscisse
curviligne `t` de cette courbe. La topologie ne change jamais : les réglages se
font en direct dans le panneau du modificateur, et l'export Unity reste propre.

Repère du jouet : axe = Z local, base à z = 0, pointe en haut.
w = distance depuis la pointe (w = 0 à la pointe, w = L à la base).
"""
import math

import bpy
import numpy as np

from lib.geom import RingMesh
from lib.nodes import NodeBuilder, add_socket, new_tree
from lib.studio import mesh_object

SEGMENTS = 48          # sommets par anneau (multiple de 8)
ANNEAUX = 240          # anneaux le long du profil
T_CAP = 0.035          # part du profil couverte par chaque cap
PROFIL_POINTS = 1500   # échantillons du profil


# --------------------------------------------------------------------------- gabarit
def gabarit():
    rm = RingMesh(SEGMENTS)
    th = -math.pi / 2 + 2 * math.pi * np.arange(SEGMENTS) / SEGMENTS
    for i in range(ANNEAUX):
        t = T_CAP + (1 - 2 * T_CAP) * i / (ANNEAUX - 1)
        rm.add_ring(np.column_stack([np.cos(th), np.sin(th), np.full(SEGMENTS, t)]), "anneau", t=t, theta=th)

    def theta_of(Q):
        return np.arctan2(Q[:, 1], Q[:, 0])

    q = SEGMENTS // 8
    rm.cap(0, lambda R: R[:, :2], lambda Q: np.column_stack([Q, np.full(len(Q), T_CAP)]), q,
           t=lambda Q: T_CAP * np.hypot(Q[:, 0], Q[:, 1]), theta=theta_of)
    rm.cap(ANNEAUX - 1, lambda R: R[:, :2], lambda Q: np.column_stack([Q, np.full(len(Q), 1 - T_CAP)]), q,
           t=lambda Q: 1 - T_CAP * np.hypot(Q[:, 0], Q[:, 1]), theta=theta_of)
    return rm.build()


# --------------------------------------------------------------------------- profils
def _finalise(nb, termes, k):
    """Union lisse des termes, forcée à 0 là où tous les termes sont nuls (extrémités fermées)."""
    lisse, brut = termes[0], termes[0]
    for t in termes[1:]:
        lisse = nb.smax(lisse, t, k)
        brut = nb.max(brut, t)
    return nb.min(lisse, nb.mul(brut, 1.3))


def _pointe(nb, w, rp, corps):
    """Bout arrondi (demi-sphère de rayon rp) raccordé sans bourrelet au reste du corps."""
    return nb.switch("FLOAT", nb.lt(w, rp), corps, nb.ellipsoid(w, rp, rp, rp))


def profil_lisse(nb, g):
    L = g["Longueur"]
    rp, R, rb = (nb.mul(g[n], 0.5) for n in ("Diamètre pointe", "Diamètre", "Diamètre base"))
    h = nb.mul(g["Hauteur base"], 0.5)

    def r(w):
        x = nb.clamp01(nb.div(nb.sub(w, rp), nb.sub(nb.sub(L, nb.mul(h, 2.0)), rp)))
        tige = nb.mul(nb.lerp(rp, R, nb.pow(x, 0.6)), nb.between(w, 0.0, nb.sub(L, h)))
        corps = _pointe(nb, w, rp, tige)
        return _finalise(nb, [corps, nb.ellipsoid(w, nb.sub(L, h), rb, h)], g["Lissage"])

    return L, r


def profil_perles(nb, g, n_max=8):
    e = g["Allongement perles"]
    n_actives = g["Nombre de perles"]
    W = 0.0
    perles = []
    for i in range(1, n_max + 1):
        actif = nb.gt(n_actives, i - 0.5)
        ri = nb.mul(g[f"Perle {i}"], 0.5)
        demi = nb.mul(ri, e)
        centre = nb.add(W, demi)
        perles.append((actif, ri, demi, centre))
        W = nb.add(W, nb.mul(actif, nb.add(nb.mul(demi, 2.0), g[f"Écart {i}"])))
    h = nb.mul(g["Hauteur base"], 0.5)
    L = nb.add(nb.add(W, g["Longueur manche"]), nb.mul(h, 2.0))
    rs = nb.mul(g["Diamètre tige"], 0.5)
    rb = nb.mul(g["Diamètre base"], 0.5)

    def r(w):
        termes = [nb.mul(rs, nb.between(w, perles[0][3], nb.sub(L, h))), nb.ellipsoid(w, nb.sub(L, h), rb, h)]
        termes += [nb.mul(actif, nb.ellipsoid(w, c, ri, demi)) for actif, ri, demi, c in perles]
        return _finalise(nb, termes, g["Lissage"])

    return L, r


def profil_noue(nb, g):
    La, Lp = g["Pointe → centre du nœud"], g["Longueur pointe"]
    rp, R, rk, rc, rb = (nb.mul(g[n], 0.5) for n in
                         ("Diamètre pointe", "Diamètre tige", "Diamètre nœud", "Diamètre col", "Diamètre base"))
    demi_k = nb.mul(g["Longueur nœud"], 0.5)
    h = nb.mul(g["Hauteur base"], 0.5)
    L = nb.add(nb.add(nb.add(La, demi_k), g["Longueur col"]), nb.mul(h, 2.0))

    def r(w):
        x1 = nb.clamp01(nb.div(nb.sub(w, rp), nb.sub(Lp, rp)))
        ogive = nb.lerp(rp, R, nb.pow(nb.sin(nb.mul(x1, math.pi / 2)), 0.85))
        x2 = nb.clamp01(nb.div(nb.sub(w, Lp), nb.max(nb.sub(nb.sub(La, demi_k), Lp), 1e-4)))
        renfle = nb.add(1.0, nb.mul(g["Renflement tige"], nb.sin(nb.mul(x2, math.pi))))
        tige = nb.mul(nb.mul(ogive, renfle), nb.between(w, 0.0, La))
        col = nb.mul(rc, nb.between(w, La, nb.sub(L, h)))
        termes = [_pointe(nb, w, rp, tige), nb.ellipsoid(w, La, rk, demi_k), col,
                  nb.ellipsoid(w, nb.sub(L, h), rb, h)]
        return _finalise(nb, termes, g["Lissage"])

    return L, r


D, F = "DISTANCE", "FACTOR"
BASE = [("Diamètre base", "FLOAT", 0.065, 0.0, 0.2, D), ("Hauteur base", "FLOAT", 0.014, 0.002, 0.05, D),
        ("Lissage", "FLOAT", 0.006, 0.0, 0.03, D)]

JOUETS = {
    "lisse": dict(
        nom="Jouet_Lisse",
        profil=profil_lisse,
        entrees=[("Longueur", "FLOAT", 0.235, 0.05, 0.5, D), ("Diamètre", "FLOAT", 0.042, 0.005, 0.12, D),
                 ("Diamètre pointe", "FLOAT", 0.032, 0.005, 0.12, D)] + BASE,
    ),
    "perles": dict(
        nom="Jouet_Perles",
        profil=profil_perles,
        entrees=[("Nombre de perles", "INT", 6, 1, 8, None)]
        + [(f"Perle {i}", "FLOAT", d, 0.005, 0.12, D)
           for i, d in enumerate((0.024, 0.028, 0.032, 0.036, 0.040, 0.044, 0.046, 0.048), 1)]
        + [(f"Écart {i}", "FLOAT", 0.006, 0.0, 0.1, D) for i in range(1, 9)]
        + [("Diamètre tige", "FLOAT", 0.014, 0.004, 0.08, D), ("Allongement perles", "FLOAT", 1.0, 0.4, 2.5, None),
           ("Longueur manche", "FLOAT", 0.03, 0.0, 0.2, D)] + BASE[:2] + [("Lissage", "FLOAT", 0.004, 0.0, 0.03, D)],
    ),
    "noue": dict(
        nom="Jouet_Noue",
        profil=profil_noue,
        entrees=[("Pointe → centre du nœud", "FLOAT", 0.155, 0.04, 0.4, D),
                 ("Diamètre pointe", "FLOAT", 0.012, 0.003, 0.08, D), ("Longueur pointe", "FLOAT", 0.09, 0.01, 0.2, D),
                 ("Diamètre tige", "FLOAT", 0.038, 0.005, 0.12, D), ("Renflement tige", "FLOAT", 0.08, -0.3, 0.6, F),
                 ("Diamètre nœud", "FLOAT", 0.062, 0.01, 0.15, D), ("Longueur nœud", "FLOAT", 0.055, 0.01, 0.15, D),
                 ("Diamètre col", "FLOAT", 0.036, 0.005, 0.12, D), ("Longueur col", "FLOAT", 0.02, 0.0, 0.15, D),
                 ("Diamètre base", "FLOAT", 0.07, 0.0, 0.2, D)] + BASE[1:],
    ),
}


# --------------------------------------------------------------------------- arbre GN
def arbre_jouet(kind):
    spec = JOUETS[kind]
    tree = new_tree(f"Generateur_{spec['nom']}")
    add_socket(tree, "Geometry", "GEO")
    for name, typ, default, lo, hi, sub in spec["entrees"]:
        add_socket(tree, name, typ, default, lo, hi, sub)
    add_socket(tree, "Geometry", "GEO", out=True)

    nb = NodeBuilder(tree)
    gi = nb.node("NodeGroupInput")
    go = nb.node("NodeGroupOutput")
    g = {s.name: gi.outputs[s.name] for s in tree.interface.items_tree
         if s.item_type == "SOCKET" and s.in_out == "INPUT" and s.socket_type != "NodeSocketGeometry"}

    L, rayon = spec["profil"](nb, g)

    # profil échantillonné de la base (u = 0) à la pointe (u = 1), plus dense aux extrémités
    line = nb.node("GeometryNodeMeshLine")
    line.inputs["Count"].default_value = PROFIL_POINTS
    u = nb.div(nb.index(), PROFIL_POINTS - 1)
    w = nb.mul(L, nb.mul(0.5, nb.add(1.0, nb.cos(nb.mul(u, math.pi)))))
    profil = nb.set_position(line.outputs["Mesh"], nb.vec(rayon(w), 0.0, nb.sub(L, w)))
    courbe = nb.node("GeometryNodeMeshToCurve")
    nb.set(courbe.inputs["Mesh"], profil)

    sample = nb.node("GeometryNodeSampleCurve", mode="FACTOR")
    nb.set(sample.inputs["Curves"], courbe.outputs["Curve"])
    nb.set(sample.inputs["Factor"], nb.named("t"))
    r, _, z = nb.xyz(sample.outputs["Position"])
    th = nb.named("theta")
    pos = nb.vec(nb.mul(r, nb.cos(th)), nb.mul(r, nb.sin(th)), z)
    nb.set(go.inputs["Geometry"], nb.set_position(gi.outputs["Geometry"], pos))
    return tree


def socket_id(ob, modifier, name):
    tree = ob.modifiers[modifier].node_group
    return next(s.identifier for s in tree.interface.items_tree
                if s.item_type == "SOCKET" and s.in_out == "INPUT" and s.name == name)


def regler(ob, modifier="Generateur", **valeurs):
    """Modifie les réglages GN d'un objet ; les noms peuvent utiliser _ à la place des espaces."""
    mod = ob.modifiers[modifier]
    for key, val in valeurs.items():
        name = key.replace("_", " ")
        mod[socket_id(ob, modifier, name)] = val
    ob.data.update()


def creer_jouet(kind, material, location=(0, 0, 0), subdivision=(1, 2)):
    verts, faces, attrs = gabarit()
    ob = mesh_object(JOUETS[kind]["nom"], verts, faces, [material])
    me = ob.data
    for name in ("t", "theta"):
        a = me.attributes.new(name, "FLOAT", "POINT")
        a.data.foreach_set("value", attrs[name].astype(np.float32))
    mod = ob.modifiers.new("Generateur", "NODES")
    mod.node_group = arbre_jouet(kind)
    if subdivision:
        sub = ob.modifiers.new("Subdivision", "SUBSURF")
        sub.levels, sub.render_levels = subdivision
    ob.location = location
    return ob
