"""Vagin de poche à vulve canine stylisée (personnage anthro/furry).

Géométrie pure (numpy, sans bpy) : le maillage est une suite d'anneaux de N sommets.

    fond du canal (cap) -> canal -> chambre du nœud -> anneau d'entrée -> vestibule
    -> fente en Y -> lèvres -> face avant -> arrondi -> flancs -> arrière (cap)

Chaque anneau a la même indexation, donc toute variante de paramètres (lèvres
gonflées, détails du canal) donne exactement la même topologie : c'est ce qui
permet d'en faire des shape keys.

Repère local : u = horizontal, v = vertical (0 = axe du manchon), d = profondeur
(0 = face avant, positif vers l'intérieur). Repère Blender : X = u, Y = d, Z = v + B.
Unités : mètres.
"""
import copy
import math

import numpy as np

from lib.geom import (RingMesh, catmull_rom_open, circle, closed_bspline, ellipse, resample_closed, resample_open,
                      smooth_periodic, smoothstep)

PARAMS = dict(
    N=96,                      # sommets par anneau (multiple de 8)
    # --- manchon
    A=0.055, B=0.065,          # demi-axes de la section (11 x 13 cm)
    L=0.24,                    # longueur totale
    Df=0.030, Db=0.025,        # profondeur des arrondis avant / arrière
    m=2.5,                     # exposant superellipse des arrondis (2 = elliptique)
    rho_rim=0.92,              # limite face avant / arrondi
    face_s=(0.05, 0.13, 0.24, 0.38, 0.54, 0.72, 1.0),
    corner_n=6, side_step=0.010, back_n=7, back_tmax=0.82,
    # --- vulve : contour en triangle inversé arrondi (points de contrôle B-spline)
    vulva_scale=0.85,
    vulva_ctrl=((0.0, -0.050), (0.014, -0.034), (0.028, -0.006), (0.036, 0.022), (0.030, 0.040),
                (0.0, 0.042), (-0.030, 0.040), (-0.036, 0.022), (-0.028, -0.006), (-0.014, -0.034)),
    # --- fente en Y (fermée) : bas de la tige, jonction, bras, demi-écart
    slit_vS=-0.031, slit_vJ=0.006, slit_ua=0.011, slit_va=0.013, slit_w=0.0004,
    # --- lèvres
    M_lip=24,                  # boucles entre la fente et le contour
    lip_h=0.75,                # hauteur max = lip_h x distance fente -> contour
    lip_dome=0.30,             # bombé global : lèvres plus hautes au milieu qu'aux extrémités
    # profil d'une lèvre (f = 0 fente -> 1 contour, h = hauteur relative) : lèvres
    # jointes au fond de la fente, qui s'enroulent largement vers le sommet, puis pente
    # bombée jusqu'au pli du contour
    lip_profile=((0.0, 0.0), (0.0, 0.22), (0.03, 0.52), (0.10, 0.78), (0.20, 0.94), (0.33, 1.0),
                 (0.55, 0.94), (0.78, 0.70), (0.94, 0.32), (1.0, 0.0)),
    fold_amp=0.0006, fold_count=4, fold_span=9,   # petits plis vers la pointe basse
    # --- canal (x = profondeur depuis la fente)
    vest_depth=0.020, M_vest=16,
    canal_keys=((0.020, 0.0065), (0.026, 0.0055), (0.034, 0.0070), (0.052, 0.0130),
                (0.072, 0.0110), (0.088, 0.0078), (0.180, 0.0075)),
    canal_step=0.00125, end_n=5,
    canal_variant=None,
)

CANAL_VARIANTS = ("Anneaux", "Nervures", "Picots", "Plis", "Anneaux_Picots", "Nervures_Plis")


# --------------------------------------------------------------------------- contours 2D
def y_slit_outline(vS, vJ, ua, va, w, n):
    """Contour fermé d'une fente en Y très fine (demi-écart w), départ en bas, anti-horaire."""
    J = np.array([0.0, vJ])
    dR = np.array([ua, va]) / math.hypot(ua, va)
    nlow = np.array([dR[1], -dR[0]])
    R = J + np.array([ua, va])

    def line(a, b, k=300):
        t = np.linspace(0, 1, k, endpoint=False)[:, None]
        return a + t * (b - a)

    def arc(c, a0, a1, k=40):
        t = np.linspace(a0, a1, k, endpoint=False)
        return np.column_stack([c[0] + w * np.cos(t), c[1] + w * np.sin(t)])

    P1 = J + w * nlow + (w * (1 - nlow[0]) / dR[0]) * dR
    notch = J - w * nlow + (w * nlow[0] / dR[0]) * dR
    a0 = math.atan2(nlow[1], nlow[0])
    right = np.vstack([
        arc(np.array([0.0, vS]), -math.pi / 2, 0.0),
        line(np.array([w, vS]), P1),
        line(P1, R + w * nlow),
        arc(R, a0, a0 + math.pi),
        line(R - w * nlow, notch),
    ])
    left = right[::-1].copy()
    left[:, 0] *= -1
    dense = np.vstack([right, notch[None], left[1:-1]])
    return resample_closed(dense, n, start=(0.0, vS - w))


def vulva_outline(P):
    ctrl = np.asarray(P["vulva_ctrl"]) * P["vulva_scale"]
    dense = closed_bspline(ctrl)
    bottom = dense[np.argmin(dense[:, 1])]
    return resample_closed(dense, P["N"], start=bottom)


# --------------------------------------------------------------------------- profils
def face_depth(P, uv):
    rho = np.sqrt((uv[:, 0] / P["A"]) ** 2 + (uv[:, 1] / P["B"]) ** 2)
    rho = np.clip(rho, 0.0, 0.999999)
    return P["Df"] * (1 - (1 - rho ** P["m"]) ** (1 / P["m"]))


def canal_radius(P, x):
    keys = P["canal_keys"]
    xs = np.array([k[0] for k in keys])
    rs = np.array([k[1] for k in keys])
    x = np.atleast_1d(x)
    out = np.empty_like(x, dtype=float)
    for i, xi in enumerate(x):
        if xi <= xs[0]:
            out[i] = rs[0]
        elif xi >= xs[-1]:
            out[i] = rs[-1]
        else:
            j = np.searchsorted(xs, xi) - 1
            t = smoothstep((xi - xs[j]) / (xs[j + 1] - xs[j]))
            out[i] = rs[j] + (rs[j + 1] - rs[j]) * t
    return out


def _bump(p, sharp=3.0):
    return ((1 + np.cos(p)) / 2) ** sharp


def canal_relief(variant, x, th):
    """Relief vers l'intérieur du canal (m), x = profondeur, th = angle autour de l'axe."""
    if not variant:
        return np.zeros_like(th)

    def anneaux(lam=0.010):
        return _bump(2 * math.pi * x / lam)

    def nervures(n=8):
        return _bump(n * th, 2.0)

    def picots(lam=0.007, n=16, shift=0.0):
        xx = x - shift
        row = math.floor(xx / lam + 0.5)
        return _bump(2 * math.pi * xx / lam) * _bump(n * th + math.pi * (row % 2))

    def plis(lam=0.009):
        ph = 2 * math.pi * x / lam + 1.4 * np.sin(3 * th + 0.7) + 0.6 * np.sin(7 * th + 2.1) + 0.8 * math.sin(x * 35)
        return ((1 + np.sin(ph)) / 2) ** 2.5 * (0.75 + 0.25 * np.sin(2 * th + x * 60))

    return {
        "Anneaux": lambda: 0.0016 * anneaux(),
        "Nervures": lambda: 0.0019 * nervures(),
        "Picots": lambda: 0.0016 * picots(),
        "Plis": lambda: 0.0013 * plis(),
        "Anneaux_Picots": lambda: 0.0015 * anneaux(0.012) + 0.0014 * picots(0.012, 12, shift=0.006),
        "Nervures_Plis": lambda: 0.0011 * nervures() + 0.0010 * plis(),
    }[variant]()


# --------------------------------------------------------------------------- construction
def build(P=None, **overrides):
    """Retourne (verts_monde (V,3), faces, attrs, infos)."""
    P = copy.deepcopy(P or PARAMS)
    P.update(overrides)
    N = P["N"]
    A, B, m = P["A"], P["B"], P["m"]
    rm = RingMesh(N)

    slit = y_slit_outline(P["slit_vS"], P["slit_vJ"], P["slit_ua"], P["slit_va"], P["slit_w"], N)
    tri = vulva_outline(P)
    v_c = 0.5 * (P["slit_vS"] + P["slit_vJ"])          # axe du canal
    d_slit = face_depth(P, slit)
    th = -math.pi / 2 + 2 * math.pi * np.arange(N) / N  # angle des anneaux circulaires

    # ---- canal : on le construit de la fente vers le fond, puis on inverse
    canal = []  # (pts3d, tag, vulve, interieur)
    xv = P["vest_depth"]
    r_v = canal_radius(P, xv)[0]
    circ_v = circle(r_v, N, (0.0, v_c))
    for j in range(1, P["M_vest"] + 1):
        t = j / P["M_vest"]
        e = smoothstep(t) ** 0.8
        uv = slit + e * (circ_v - slit)
        d = d_slit + xv * t
        canal.append((np.column_stack([uv, d]), "vestibule", 1.0, 1.0))

    x_end = P["canal_keys"][-1][0]
    xs = np.arange(xv + P["canal_step"], x_end + 1e-9, P["canal_step"])
    for x in xs:
        r = canal_radius(P, x)[0]
        mask = float(smoothstep((x - 0.032) / 0.010) * smoothstep((x_end + 0.004 - x) / 0.012))
        rr = np.maximum(r - mask * canal_relief(P["canal_variant"], x, th), 0.002)
        uv = np.column_stack([rr * np.cos(th), v_c + rr * np.sin(th)])
        canal.append((np.column_stack([uv, np.full(N, x)]), "canal", 0.0, 1.0))

    r_end = canal_radius(P, x_end)[0]
    alphas = np.linspace(0, 0.38 * math.pi, P["end_n"] + 1)[1:]
    for a in alphas:
        r = r_end * math.cos(a)
        uv = np.column_stack([r * np.cos(th), v_c + r * np.sin(th)])
        canal.append((np.column_stack([uv, np.full(N, x_end + r_end * math.sin(a))]), "fond", 0.0, 1.0))

    for pts, tag, vu, it in reversed(canal):
        rm.add_ring(pts, tag, vulve=vu, interieur=it)
    ring_fond = 0

    # ---- fente
    rm.add_ring(np.column_stack([slit, d_slit]), "fente", vulve=1.0, interieur=1.0)

    # ---- lèvres
    dist = np.linalg.norm(tri - slit, axis=1)
    v_mid = 0.5 * (P["slit_vS"] + P["slit_vJ"] + P["slit_va"])
    half = 0.5 * (P["slit_vJ"] + P["slit_va"] - P["slit_vS"])
    dome = 1.0 + P["lip_dome"] * (1.0 - np.clip(((slit[:, 1] - v_mid) / half) ** 2, 0, 1)) - P["lip_dome"] * 0.5
    H = smooth_periodic(P["lip_h"] * dist * dome, window=7, passes=2)
    k_from_bottom = np.minimum(np.arange(N), N - np.arange(N))
    fold_mask = np.exp(-(k_from_bottom / P["fold_span"]) ** 2)
    Ml = P["M_lip"]
    prof = resample_open(catmull_rom_open(P["lip_profile"]), Ml + 1, metric=(1.0, P["lip_h"]))
    prof[-1] = (1.0, 0.0)
    for i in range(1, Ml + 1):
        f, hn = prof[i]
        t = i / Ml
        uv = slit + f * (tri - slit)
        h = H * hn - P["fold_amp"] * fold_mask * math.sin(math.pi * t) * max(0.0, math.sin(2 * P["fold_count"] * math.pi * t))
        d = face_depth(P, uv) - h
        inner = 1.0 - float(smoothstep((t - 0.22) / 0.15))
        rm.add_ring(np.column_stack([uv, d]), "levres", vulve=1.0, interieur=inner)

    # ---- face avant (du contour de la vulve au bord de l'arrondi)
    rim = ellipse(P["rho_rim"] * A, P["rho_rim"] * B, N)
    for i, s in enumerate(P["face_s"]):
        uv = tri + s * (rim - tri)
        rm.add_ring(np.column_stack([uv, face_depth(P, uv)]), "face", vulve=0.35 if i == 0 else 0.0, interieur=0.0)

    # ---- arrondi avant, flancs, arrondi arrière
    t_rim = math.acos(P["rho_rim"] ** (m / 2))
    for t in np.linspace(t_rim, 0, P["corner_n"] + 1)[1:]:
        rho = math.cos(t) ** (2 / m)
        uv = ellipse(rho * A, rho * B, N)
        rm.add_ring(np.column_stack([uv, np.full(N, P["Df"] * (1 - math.sin(t) ** (2 / m)))]), "arrondi_avant")
    L, Db = P["L"], P["Db"]
    n_side = max(1, round((L - Db - P["Df"]) / P["side_step"]))
    oval = ellipse(A, B, N)
    for d in np.linspace(P["Df"], L - Db, n_side + 1)[1:]:
        rm.add_ring(np.column_stack([oval, np.full(N, d)]), "flanc")
    for t in np.linspace(0, P["back_tmax"] * math.pi / 2, P["back_n"] + 1)[1:]:
        rho = math.cos(t) ** (2 / m)
        uv = ellipse(rho * A, rho * B, N)
        rm.add_ring(np.column_stack([uv, np.full(N, L - Db * (1 - math.sin(t) ** (2 / m)))]), "arriere")
    ring_dos = len(rm.rings) - 1

    # ---- caps (grilles de quads)
    q = N // 8  # index de l'anneau à -45° (départ en bas, anti-horaire)

    def cap_fond(Q):
        rr = np.hypot(Q[:, 0], Q[:, 1] - v_c)
        return np.column_stack([Q, x_end + np.sqrt(np.maximum(r_end**2 - rr**2, 0.0))])

    rm.cap(ring_fond, lambda R: R[:, :2], cap_fond, q, vulve=0.0, interieur=1.0)

    def cap_dos(Q):
        rho = np.clip(np.sqrt((Q[:, 0] / A) ** 2 + (Q[:, 1] / B) ** 2), 0, 0.999999)
        return np.column_stack([Q, L - Db * (1 - (1 - rho**m) ** (1 / m))])

    rm.cap(ring_dos, lambda R: R[:, :2], cap_dos, q, vulve=0.0, interieur=0.0)

    verts, faces, attrs = rm.build()
    world = np.column_stack([verts[:, 0], verts[:, 2], verts[:, 1] + B])
    infos = dict(axe_canal_z=v_c + B, profondeur_canal=x_end + r_end, n_anneaux=len(rm.rings),
                 tags=rm.tags)
    return world, faces, attrs, infos
