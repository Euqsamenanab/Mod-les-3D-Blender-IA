"""Jouets de test procéduraux (Geometry Nodes) : lisse, à perles, à nœud canin stylisé.

Principe : un gabarit de maillage fixe (anneaux + caps en grille, 100 % quads) porte
deux attributs, `t` (0 = centre de la base, 1 = centre de la pointe) et `theta`
(angle). L'arbre Geometry Nodes calcule un profil de révolution r(w) à partir des
réglages, le transforme en courbe, puis place chaque sommet du gabarit à l'abscisse
curviligne `t` de cette courbe. La topologie ne change jamais : les réglages se
font en direct dans le panneau du modificateur, et l'export Unity reste propre.

Formes non symétriques (jouet noué) : le profil de révolution sert seulement à
répartir les anneaux le long de l'axe ; le rayon final de chaque sommet est
recalculé selon son angle `theta` (sillon de l'urètre, nœud en deux lobes).
Le dessous du jouet (côté urètre) est le côté +Y local.

Veines (jouet noué) : la shape key « Veines » du gabarit décale chaque sommet de
+1 en X. Le générateur lit ce décalage (position - x_repos) comme intensité des
veines : le curseur de la shape key règle donc en direct le relief des veines,
dont la forme se règle dans le modificateur.

Repère du jouet : axe = Z local, base à z = 0, pointe en haut.
w = distance depuis la pointe (w = 0 à la pointe, w = L à la base).
"""
import math

import bpy
import numpy as np

from lib.geom import RingMesh
from lib.nodes import NodeBuilder, add_socket, new_tree
from lib.studio import mesh_object

SEGMENTS = 48          # sommets par anneau par défaut (multiple de 8)
ANNEAUX = 240          # anneaux le long du profil par défaut
T_CAP = 0.035          # part du profil couverte par chaque cap
PROFIL_POINTS = 1500   # échantillons du profil


# --------------------------------------------------------------------------- gabarit
def gabarit(segments=SEGMENTS, anneaux=ANNEAUX):
    rm = RingMesh(segments)
    th = -math.pi / 2 + 2 * math.pi * np.arange(segments) / segments
    for i in range(anneaux):
        t = T_CAP + (1 - 2 * T_CAP) * i / (anneaux - 1)
        rm.add_ring(np.column_stack([np.cos(th), np.sin(th), np.full(segments, t)]), "anneau", t=t, theta=th)

    def theta_of(Q):
        return np.arctan2(Q[:, 1], Q[:, 0])

    q = segments // 8
    rm.cap(0, lambda R: R[:, :2], lambda Q: np.column_stack([Q, np.full(len(Q), T_CAP)]), q,
           t=lambda Q: T_CAP * np.hypot(Q[:, 0], Q[:, 1]), theta=theta_of)
    rm.cap(anneaux - 1, lambda R: R[:, :2], lambda Q: np.column_stack([Q, np.full(len(Q), 1 - T_CAP)]), q,
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

    return L, r, None


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

    return L, r, None


def profil_noue(nb, g):
    """Jouet noué canin stylisé : petite pointe, gland formé, tige avec sillon d'urètre
    sur le dessous (+Y), nœud en deux lobes latéraux (±X), col et base."""
    La = g["Pointe → centre du nœud"]
    rn, ln = nb.mul(g["Diamètre pointe"], 0.5), g["Longueur pointe"]
    rg, Lg = nb.mul(g["Diamètre gland"], 0.5), g["Longueur gland"]
    r1, r2 = nb.mul(g["Diamètre tige (gland)"], 0.5), nb.mul(g["Diamètre tige (nœud)"], 0.5)
    rl, d = nb.mul(g["Diamètre lobes"], 0.5), nb.mul(g["Écart des lobes"], 0.5)
    Ll = nb.mul(g["Longueur nœud"], 0.5)
    rc, rb = nb.mul(g["Diamètre col"], 0.5), nb.mul(g["Diamètre base"], 0.5)
    h = nb.mul(g["Hauteur base"], 0.5)
    L = nb.add(nb.add(nb.add(La, Ll), g["Longueur col"]), nb.mul(h, 2.0))
    k = g["Lissage"]

    def corps(w):
        """Gland + tige, de révolution."""
        # gland en obus : s'élargit presque linéairement depuis la petite pointe, puis s'arrondit
        x1 = nb.clamp01(nb.div(nb.sub(w, ln), nb.max(nb.sub(nb.mul(Lg, 0.9), ln), 1e-4)))
        tete = nb.lerp(rn, rg, nb.sub(1.0, nb.pow(nb.sub(1.0, x1), 1.6)))
        tige = nb.lerp(r1, r2, nb.clamp01(nb.div(nb.sub(w, Lg), nb.max(nb.sub(La, Lg), 1e-4))))
        f = nb.smoothstep(nb.mul(Lg, 0.85), nb.mul(Lg, 1.15), w)
        bourrelet = nb.mul(g["Bourrelet gland"], nb.exp(nb.mul(-1.0, nb.pow(nb.div(nb.sub(w, Lg), 0.006), 2.0))))
        r = nb.mul(nb.add(nb.lerp(tete, tige, f), bourrelet), nb.between(w, 0.0, La))
        return nb.switch("FLOAT", nb.lt(w, ln), r, nb.ellipsoid(w, ln, rn, ln))   # petite pointe au bout

    def autres(w):
        col = nb.mul(rc, nb.between(w, La, nb.sub(L, h)))
        return [col, nb.ellipsoid(w, nb.sub(L, h), rb, h)]

    def enveloppe(w):
        return _finalise(nb, [corps(w), nb.ellipsoid(w, La, nb.add(d, rl), Ll)] + autres(w), k)

    def veines(w, th):
        """Relief des veines (m) : 5 veines sinueuses sur le dessus et les flancs, 2 ramifications."""
        graine = g["Veines : graine"]

        def alea(kv, j):
            v = nb.sin(nb.add(nb.mul(graine, 12.9898), 78.233 * kv + 37.719 * j))
            return nb.math("FRACT", nb.mul(v, 43758.5453))

        sin_ = g["Veines : sinuosité"]
        demi0 = nb.div(nb.mul(g["Veines : épaisseur"], 0.5), r2)   # demi-largeur angulaire
        total = 0.0
        chemins = {}
        for kv, base in enumerate((-1.57, -0.75, -2.39, 0.15, 2.99)):
            th0 = nb.add(base, nb.mul(0.25, nb.sub(alea(kv, 1), 0.5)))
            lam = nb.add(0.06, nb.mul(0.05, alea(kv, 2)))
            phi = nb.mul(2 * math.pi, alea(kv, 3))
            onde = nb.add(nb.sin(nb.add(nb.div(nb.mul(w, 2 * math.pi), lam), phi)),
                          nb.mul(0.4, nb.sin(nb.add(nb.div(nb.mul(w, 2 * math.pi), nb.mul(lam, 0.43)),
                                                    nb.mul(phi, 2.0)))))
            th_k = nb.add(th0, nb.mul(sin_, onde))
            w0 = nb.add(nb.mul(Lg, 1.05), nb.mul(0.015, alea(kv, 4)))
            w1 = nb.sub(nb.sub(La, nb.mul(Ll, 0.85)), nb.mul(0.012, alea(kv, 5)))
            env = nb.mul(nb.smoothstep(w0, nb.add(w0, 0.018), w),
                         nb.sub(1.0, nb.smoothstep(nb.sub(w1, 0.018), w1, w)))
            x = nb.clamp01(nb.div(nb.sub(w, w0), nb.max(nb.sub(w1, w0), 1e-3)))
            haut = nb.mul(nb.mul(g["Veines : relief"], nb.add(0.65, nb.mul(0.35, alea(kv, 6)))),
                          nb.add(0.6, nb.mul(0.4, x)))
            sigma = nb.mul(demi0, nb.add(0.65, nb.mul(0.35, x)))
            chemins[kv] = (th_k, env, haut, sigma, w0, w1)

        def trace(th_k, env, haut, sigma, index):
            actif = nb.gt(g["Veines : nombre"], index - 0.5)
            # profil de tube : 1 - (corde / demi-largeur)², corde² = 2 (1 - cos(écart angulaire))
            corde2 = nb.mul(2.0, nb.sub(1.0, nb.cos(nb.sub(th, th_k))))
            profil = nb.pow(nb.max(0.0, nb.sub(1.0, nb.div(corde2, nb.mul(sigma, sigma)))), 0.75)
            return nb.mul(nb.mul(actif, haut), nb.mul(env, profil))

        for kv, (th_k, env, haut, sigma, _, _) in chemins.items():
            total = nb.add(total, trace(th_k, env, haut, sigma, kv + 1))
        # ramifications vers le gland, depuis les veines 2 et 3
        for idx, (parent, ecart) in enumerate(((1, 0.5), (2, -0.5)), start=6):
            th_p, env_p, haut_p, sigma_p, w0, w1 = chemins[parent]
            wb = nb.add(w0, nb.mul(nb.sub(w1, w0), nb.add(0.5, nb.mul(0.15, alea(idx, 7)))))
            th_b = nb.add(th_p, nb.mul(ecart, nb.smoothstep(0.0, 0.04, nb.sub(wb, w))))
            env_b = nb.mul(env_p, nb.sub(1.0, nb.smoothstep(nb.sub(wb, 0.003), nb.add(wb, 0.003), w)))
            total = nb.add(total, trace(th_b, env_b, nb.mul(haut_p, 0.75), nb.mul(sigma_p, 0.85), idx))
        return total

    def rayon_3d(w, th):
        # sillon de l'urètre sur le dessous (+Y), bordé de deux bourrelets
        s0 = nb.sin(th)
        sig2 = nb.mul(g["Largeur urètre"], g["Largeur urètre"])
        delta = nb.mul(g["Largeur urètre"], 2.2)

        def gauss(c):
            return nb.exp(nb.div(nb.sub(c, 1.0), sig2))

        bords = nb.add(gauss(nb.sin(nb.sub(th, delta))), gauss(nb.sin(nb.add(th, delta))))
        prof = g["Profondeur urètre"]
        mod = nb.add(nb.sub(1.0, nb.mul(prof, gauss(s0))), nb.mul(nb.mul(prof, 0.35), bords))
        masque = nb.mul(nb.smoothstep(nb.mul(ln, 2.0), nb.mul(Lg, 0.7), w),
                        nb.sub(1.0, nb.smoothstep(nb.sub(La, nb.mul(Ll, 1.2)), nb.sub(La, nb.mul(Ll, 0.5)), w)))
        corps3d = nb.mul(corps(w), nb.add(1.0, nb.mul(masque, nb.sub(mod, 1.0))))
        # veines : intensité lue sur la shape key « Veines » du gabarit
        px, _, _ = nb.xyz(nb.position())
        intensite = nb.sub(px, nb.named("x_repos"))
        corps3d = nb.add(corps3d, nb.mul(intensite, veines(w, th)))
        # nœud : deux lobes ellipsoïdaux centrés en x = ±d ; distance depuis l'axe dans la direction th
        q = nb.div(nb.sub(w, La), Ll)
        rho_c = nb.mul(rl, nb.sqrt(nb.max(0.0, nb.sub(1.0, nb.mul(q, q)))))
        ds = nb.mul(d, s0)
        disc = nb.sub(nb.mul(rho_c, rho_c), nb.mul(ds, ds))
        lobes = nb.mul(nb.gt(disc, 0.0),
                       nb.add(nb.mul(d, nb.math("ABSOLUTE", nb.cos(th))), nb.sqrt(nb.max(disc, 0.0))))
        return _finalise(nb, [corps3d, lobes] + autres(w), k)

    return L, enveloppe, rayon_3d


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
        segments=160, anneaux=300,
        veines=True,
        entrees=[("Pointe → centre du nœud", "FLOAT", 0.155, 0.04, 0.4, D),
                 ("Diamètre pointe", "FLOAT", 0.006, 0.002, 0.04, D), ("Longueur pointe", "FLOAT", 0.013, 0.002, 0.05, D),
                 ("Diamètre gland", "FLOAT", 0.040, 0.005, 0.12, D), ("Longueur gland", "FLOAT", 0.060, 0.01, 0.15, D),
                 ("Bourrelet gland", "FLOAT", 0.0008, 0.0, 0.01, D),
                 ("Diamètre tige (gland)", "FLOAT", 0.037, 0.005, 0.12, D),
                 ("Diamètre tige (nœud)", "FLOAT", 0.040, 0.005, 0.12, D),
                 ("Profondeur urètre", "FLOAT", 0.14, 0.0, 0.4, F), ("Largeur urètre", "FLOAT", 0.16, 0.05, 0.6, None),
                 ("Diamètre lobes", "FLOAT", 0.050, 0.01, 0.12, D), ("Écart des lobes", "FLOAT", 0.028, 0.0, 0.1, D),
                 ("Longueur nœud", "FLOAT", 0.050, 0.01, 0.15, D),
                 ("Diamètre col", "FLOAT", 0.034, 0.005, 0.12, D), ("Longueur col", "FLOAT", 0.018, 0.0, 0.15, D),
                 ("Diamètre base", "FLOAT", 0.07, 0.0, 0.2, D), ("Hauteur base", "FLOAT", 0.014, 0.002, 0.05, D),
                 ("Lissage", "FLOAT", 0.005, 0.0, 0.03, D),
                 ("Veines : nombre", "INT", 7, 0, 7, None), ("Veines : épaisseur", "FLOAT", 0.0036, 0.001, 0.012, D),
                 ("Veines : relief", "FLOAT", 0.0014, 0.0, 0.004, D),
                 ("Veines : sinuosité", "FLOAT", 0.22, 0.0, 0.8, None), ("Veines : graine", "INT", 3, 0, 1000, None)],
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

    L, rayon, rayon_3d = spec["profil"](nb, g)

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
    if rayon_3d:
        r = rayon_3d(nb.sub(L, z), th)
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


def uv_gabarit(me, verts, attrs, segments, anneaux):
    """UV fixes du gabarit (valables pour tous les réglages GN) : la tige en bande
    (U = angle, V = abscisse curviligne t), coupée sous le jouet ; base et pointe en
    deux îlots carrés."""
    S = segments
    n_anneau = (anneaux - 1) * S
    n_cap = (S // 4) ** 2
    t = attrs["t"]
    uv = np.zeros((len(me.loops), 2), np.float32)
    for p in me.polygons:
        idx = [me.loops[li].vertex_index for li in p.loop_indices]
        if p.index < n_anneau:
            ks = [(i % S if i < anneaux * S else 0) for i in idx]
            boucle = max(ks) - min(ks) > 1                  # face qui traverse la couture (k = S-1 -> 0)
            for li, i, k in zip(p.loop_indices, idx, ks):
                kk = S if (boucle and k == 0) else k
                uv[li] = (0.02 + 0.5 * kk / S, 0.01 + 0.98 * (t[i] - T_CAP) / (1 - 2 * T_CAP))
        else:
            v0 = 0.05 if p.index < n_anneau + n_cap else 0.55   # base en bas, pointe en haut
            for li, i in zip(p.loop_indices, idx):
                x, y = verts[i, 0], verts[i, 1]
                uv[li] = (0.56 + 0.2 * (x + 1), v0 + 0.2 * (y + 1))
    couche = me.uv_layers.new(name="UVMap")
    couche.data.foreach_set("uv", uv.ravel())


def creer_jouet(kind, material, location=(0, 0, 0), subdivision=(1, 2)):
    spec = JOUETS[kind]
    verts, faces, attrs = gabarit(spec.get("segments", SEGMENTS), spec.get("anneaux", ANNEAUX))
    ob = mesh_object(JOUETS[kind]["nom"], verts, faces, [material])
    me = ob.data
    uv_gabarit(me, verts, attrs, spec.get("segments", SEGMENTS), spec.get("anneaux", ANNEAUX))
    for name in ("t", "theta"):
        a = me.attributes.new(name, "FLOAT", "POINT")
        a.data.foreach_set("value", attrs[name].astype(np.float32))
    if spec.get("veines"):
        # x_repos + shape key « Veines » (+1 en X) : le générateur en déduit l'intensité des veines
        a = me.attributes.new("x_repos", "FLOAT", "POINT")
        a.data.foreach_set("value", verts[:, 0].astype(np.float32))
        ob.shape_key_add(name="Basis", from_mix=False)
        cle = ob.shape_key_add(name="Veines", from_mix=False)
        co = verts.astype(np.float32).copy()
        co[:, 0] += 1.0
        cle.data.foreach_set("co", co.ravel())
        cle.slider_min, cle.slider_max = 0.0, 2.0
    mod = ob.modifiers.new("Generateur", "NODES")
    mod.node_group = arbre_jouet(kind)
    if subdivision:
        sub = ob.modifiers.new("Subdivision", "SUBSURF")
        sub.levels, sub.render_levels = subdivision
    ob.location = location
    return ob
