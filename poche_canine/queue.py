"""Queue anthro pour le torse : moignon (forme de base), queue fine de chat et queue
touffue de loup (shape keys), sur la même topologie.

Maillage : anneaux de SEGMENTS sommets le long d'une ligne centrale (repère transporté
sans torsion), fermés aux deux bouts par une grille de quads. La base est enfoncée de
quelques millimètres dans le bas du dos, juste au-dessus du sillon des fesses.
"""
import math

import numpy as np

from lib.geom import RingMesh, smoothstep

SEGMENTS = 40          # sommets par anneau (multiple de 8)
ANNEAUX = 90           # anneaux le long de la queue

TYPES = {
    # longueur, rayon à la base, ligne centrale : (montée, courbure), mèches
    "moignon": dict(longueur=0.055, r_base=0.024, profil="moignon", montee=0.15, courbe=0.0, meches=0.0),
    "chat": dict(longueur=0.46, r_base=0.020, profil="chat", montee=0.55, courbe=1.6, meches=0.0),
    "loup": dict(longueur=0.42, r_base=0.027, profil="loup", montee=-0.30, courbe=1.1, meches=1.0),
}


def rayon_profil(nom, s, r_base):
    """Rayon le long de la queue (s = 0 à la base, 1 au bout)."""
    if nom == "moignon":
        return r_base * (1.0 + 0.10 * np.sin(math.pi * np.minimum(s / 0.6, 1.0))) * np.sqrt(np.maximum(1 - s ** 3, 0))
    if nom == "chat":
        r = r_base * (1.0 - 0.38 * s) * (1.0 + 0.10 * np.exp(-((s - 0.08) / 0.08) ** 2))
        return r * np.sqrt(np.maximum(1 - ((s - 0.93) / 0.07).clip(0, 1) ** 2, 0))     # bout arrondi
    # loup : touffue, plus épaisse au milieu, bout en pointe de mèche
    r = r_base * (1.0 + 1.25 * np.sin(math.pi * np.clip(s / 0.9, 0, 1)) ** 0.8)
    return r * (1 - smoothstep((s - 0.72) / 0.28) ** 0.9)


def ligne_centrale(T, s):
    """Points de la ligne centrale (repère du dos : y vers l'arrière, z vers le haut)."""
    L = T["longueur"]
    a0 = T["montee"]                       # angle de départ (radians) au-dessus de l'horizontale
    courbe = T["courbe"]
    n = 400
    u = np.linspace(0, 1, n)
    ang = a0 + courbe * smoothstep(u * 1.2) * u      # la queue se relève (chat) ou se recourbe (loup)
    dl = L / (n - 1)
    pts = np.zeros((n, 3))
    pts[1:, 1] = np.cumsum(np.cos(ang[:-1]) * dl)
    pts[1:, 2] = np.cumsum(np.sin(ang[:-1]) * dl)
    return np.column_stack([np.interp(s, u, pts[:, k]) for k in range(3)])


def build_queue(nom, base, enfoncement=0.012):
    """Sommets et faces d'une queue. base : point d'attache sur le dos (monde)."""
    T = TYPES[nom]
    N = SEGMENTS
    s = np.linspace(0, 1, ANNEAUX) ** 1.15
    C = ligne_centrale(T, s)
    C[:, 1] -= enfoncement                                  # base enfoncée dans le dos
    tang = np.gradient(C, axis=0)
    tang /= np.linalg.norm(tang, axis=1)[:, None]
    # repère transporté (pas de torsion) : x vers la droite du torse au départ
    nrm = np.zeros_like(C)
    nrm[0] = np.cross(tang[0], [1.0, 0.0, 0.0])
    nrm[0] /= np.linalg.norm(nrm[0])
    for i in range(1, len(C)):
        v = nrm[i - 1] - np.dot(nrm[i - 1], tang[i]) * tang[i]
        nrm[i] = v / np.linalg.norm(v)
    bin_ = np.cross(tang, nrm)
    th = -math.pi / 2 + 2 * math.pi * np.arange(N) / N
    r = rayon_profil(T["profil"], s, T["r_base"])
    rm = RingMesh(N)
    for i in range(1, len(C) - 1):
        ri = np.full(N, r[i])
        if T["meches"]:
            # mèches : touffes en couronnes décalées, chacune s'effile vers le bout
            k = s[i] * 11.0 + 0.5 * (np.arange(N) // 5 % 2)
            dent = (1.0 - (k % 1.0)) ** 1.6
            ang = ((1 + np.cos(8 * th + 2.1 * s[i] * 11)) / 2) ** 2
            ri = ri * (1.0 + T["meches"] * 0.22 * dent * (0.5 + 0.5 * ang) * smoothstep((s[i] - 0.08) / 0.1))
        pts = C[i] + ri[:, None] * (np.cos(th)[:, None] * nrm[i] + np.sin(th)[:, None] * bin_[i])
        rm.add_ring(pts, "queue")
    q = N // 8

    def plan(i):
        return lambda R_: np.column_stack([(R_ - C[i]) @ nrm[i], (R_ - C[i]) @ bin_[i]])

    def bout(i, sens):
        def f(Q):
            rr = np.clip(np.hypot(Q[:, 0], Q[:, 1]) / max(r[i], 1e-6), 0, 1)
            h = 0.3 * r[i] * np.sqrt(1 - rr * rr) * sens
            return C[i] + Q[:, :1] * nrm[i] + Q[:, 1:2] * bin_[i] + h[:, None] * tang[i]
        return f

    R = len(rm.rings)
    rm.cap(0, plan(1), bout(1, -1), q)
    rm.cap(R - 1, plan(len(C) - 2), bout(len(C) - 2, 1), q)
    verts, faces, _ = rm.build()
    return verts + np.asarray(base), faces
