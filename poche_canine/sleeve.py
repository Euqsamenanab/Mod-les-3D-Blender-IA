"""Vagin de poche à vulve canine stylisée (personnage anthro/furry).

Géométrie pure (numpy, sans bpy) : le maillage est une suite d'anneaux de N sommets.

    fond du canal (cap) -> canal -> chambre du nœud -> anneau d'entrée -> vestibule
    -> fente en Y -> lèvres -> face avant -> arrondi -> flancs -> arrière (cap)

Chaque anneau a la même indexation, donc toute variante de paramètres (lèvres
gonflées, détails du canal) donne exactement la même topologie : c'est ce qui
permet d'en faire des shape keys (voir SHAPE_KEYS). Les contours de la fente et de
la vulve sont échantillonnés avec une paramétrisation fixe : chaque sommet garde sa
place « structurelle » quand on change une dimension, ce qui rend les shape keys
propres et combinables.

Repère local : u = horizontal, v = vertical (0 = axe du manchon), d = profondeur
(0 = face avant, positif vers l'intérieur). Repère Blender : X = u, Y = d, Z = v + B.
Unités : mètres.
"""
import copy
import functools
import math

import numpy as np

from lib.geom import RingMesh, catmull_rom_open, circle, ellipse, resample_open, smooth_periodic, smoothstep

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
    vulva_size=1.0,            # échelle de toute la vulve (contour + fente) autour de l'axe du canal
    tip=0.0,                   # pointe du bas : +1 allongée et fine, -1 courte et arrondie
    vulva_ctrl=((0.0, -0.050), (0.014, -0.034), (0.028, -0.006), (0.036, 0.022), (0.030, 0.040),
                (0.0, 0.042), (-0.030, 0.040), (-0.036, 0.022), (-0.028, -0.006), (-0.014, -0.034)),
    # --- fente en Y (fermée) : bas de la tige, jonction, bras, demi-écart
    slit_vS=-0.031, slit_vJ=0.006, slit_ua=0.011, slit_va=0.013, slit_w=0.0004,
    arm_len=1.0,               # longueur des branches du Y (multiplicateur)
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
    # profil du canal : (profondeur, rayon, rôle) ; les rôles reçoivent les réglages ci-dessous
    canal_keys=((0.020, 0.0065, "vestibule"), (0.026, 0.0055, "anneau"), (0.034, 0.0070, None),
                (0.052, 0.0130, "chambre"), (0.072, 0.0110, "chambre_fin"), (0.088, 0.0078, None),
                (0.180, 0.0075, None)),
    ring_dr=0.0,               # + : anneau d'entrée plus large (verrouillage souple), - : plus serré
    chamber_dr=0.0,            # + : chambre du nœud plus large, - : plus fine
    canal_step=0.00125, end_n=5,
    canal_variant=None,
)

CANAL_VARIANTS = ("Anneaux", "Nervures", "Picots", "Plis", "Anneaux_Picots", "Nervures_Plis")

# Shape keys : nom -> paramètres modifiés. Toutes vont de 0 (forme de base) à 1.
SHAPE_KEYS = {
    "Vulve_Grande": dict(vulva_size=1.2),
    "Vulve_Petite": dict(vulva_size=0.8),
    "Levres_Gonflees": dict(
        lip_h=0.98,
        lip_profile=((0.0, 0.0), (0.0, 0.22), (0.025, 0.55), (0.09, 0.82), (0.19, 0.97), (0.33, 1.03),
                     (0.58, 1.0), (0.86, 0.80), (1.08, 0.42), (1.0, 0.0)),
    ),
    "Levres_Fines": dict(lip_h=0.50),
    "Fente_Branches_Longues": dict(arm_len=1.6),
    "Fente_Branches_Courtes": dict(arm_len=0.45),
    "Pointe_Allongee": dict(tip=1.0),
    "Pointe_Arrondie": dict(tip=-1.0),
    "Anneau_Serre": dict(ring_dr=-0.002),
    "Anneau_Large": dict(ring_dr=0.002),
    "Chambre_Large": dict(chamber_dr=0.005),
    "Chambre_Fine": dict(chamber_dr=-0.004),
    **{f"Canal_{v}": dict(canal_variant=v) for v in CANAL_VARIANTS},
}

# réglage qui agit sur chaque rôle du profil du canal : (paramètre, poids)
CANAL_ROLES = {
    "vestibule": ("ring_dr", 0.75),
    "anneau": ("ring_dr", 1.0),
    "chambre": ("chamber_dr", 1.0),
    "chambre_fin": ("chamber_dr", 0.8),
}


# --------------------------------------------------------------------------- contours 2D
def _y_frame(vS, vJ, ua, va, w):
    J = np.array([0.0, vJ])
    dR = np.array([ua, va]) / math.hypot(ua, va)
    nlow = np.array([dR[1], -dR[0]])
    R = J + np.array([ua, va])
    P1 = J + w * nlow + (w * (1 - nlow[0]) / dR[0]) * dR
    notch = J - w * nlow + (w * nlow[0] / dR[0]) * dR
    return R, nlow, P1, notch


def slit_counts(vS, vJ, ua, va, w, n):
    """Nombre de sommets par tronçon de la fente (calculé une fois, sur la forme de base)."""
    R, nlow, P1, _ = _y_frame(vS, vJ, ua, va, w)
    stem = np.linalg.norm(P1 - np.array([w, vS]))
    arm = np.linalg.norm(R + w * nlow - P1)
    rest = n // 2 - 1 - 2  # demi-boucle moins l'arc du bas (1) et l'arc du bout de bras (2)
    c_arm = round(rest * arm / (stem + 2 * arm))
    return 1, rest - 2 * c_arm, c_arm, 2


def y_slit_outline(vS, vJ, ua, va, w, counts):
    """Contour fermé d'une fente en Y très fine (demi-écart w), départ en bas, anti-horaire.

    `counts` fixe le nombre de sommets de chaque tronçon : tige, bras, bouts arrondis.
    """
    c_bot, c_stem, c_arm, c_tip = counts
    R, nlow, P1, notch = _y_frame(vS, vJ, ua, va, w)

    def seg(a, b, k):
        return a + (np.arange(k) / k)[:, None] * (b - a)

    def arc(c, a0, a1, k):
        t = a0 + (a1 - a0) * np.arange(k) / k
        return np.column_stack([c[0] + w * np.cos(t), c[1] + w * np.sin(t)])

    a0 = math.atan2(nlow[1], nlow[0])
    right = np.vstack([
        arc(np.array([0.0, vS]), -math.pi / 2, 0.0, c_bot),
        seg(np.array([w, vS]), P1, c_stem),
        seg(P1, R + w * nlow, c_arm),
        arc(R, a0 + math.pi / (2 * c_tip), a0 + math.pi, c_tip),
        seg(R - w * nlow, notch, c_arm),
    ])
    left = right[1:][::-1].copy()
    left[:, 0] *= -1
    return np.vstack([right, notch[None], left])


def bspline_eval(ctrl, t):
    """B-spline cubique uniforme fermée évaluée aux paramètres t (dans [0, n))."""
    c = np.asarray(ctrl, float)
    n = len(c)
    i = np.floor(t).astype(int)
    u = (t - i)[:, None]
    b0 = (1 - u) ** 3 / 6
    b1 = (3 * u**3 - 6 * u**2 + 4) / 6
    b2 = (-3 * u**3 + 3 * u**2 + 3 * u + 1) / 6
    b3 = u**3 / 6
    return b0 * c[(i - 1) % n] + b1 * c[i % n] + b2 * c[(i + 1) % n] + b3 * c[(i + 2) % n]


@functools.lru_cache(maxsize=8)
def vulva_params(ctrl, n):
    """Paramètres B-spline de n points équidistants sur la forme de base, départ à la pointe."""
    m = len(ctrl)
    t = np.linspace(0, m, m * 400, endpoint=False)
    pts = bspline_eval(ctrl, t)
    i0 = int(np.argmin(pts[:, 1]))
    t = np.concatenate([t[i0:], t[:i0] + m, [t[i0] + m]])
    pts = bspline_eval(ctrl, t % m)
    cum = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    return np.interp(np.linspace(0, cum[-1], n, endpoint=False), cum, t) % m


def vulva_outline(P):
    base = tuple(map(tuple, P["vulva_ctrl"]))
    ctrl = np.array(base)
    tip = P["tip"]
    ctrl[0, 1] -= 0.014 * tip                    # pointe plus basse (+) ou remontée (-)
    for k in (1, -1):                            # flancs bas resserrés (+) ou élargis (-)
        ctrl[k, 0] *= 1 - 0.22 * tip
        ctrl[k, 1] -= 0.006 * tip
    return bspline_eval(ctrl * P["vulva_scale"], vulva_params(base, P["N"]))


# --------------------------------------------------------------------------- profils
def face_depth(P, uv):
    rho = np.sqrt((uv[:, 0] / P["A"]) ** 2 + (uv[:, 1] / P["B"]) ** 2)
    rho = np.clip(rho, 0.0, 0.999999)
    return P["Df"] * (1 - (1 - rho ** P["m"]) ** (1 / P["m"]))


def canal_profile(P):
    """Profil (profondeurs, rayons) du canal après les réglages anneau / chambre."""
    xs = np.array([k[0] for k in P["canal_keys"]])
    rs = np.array([k[1] + (P[CANAL_ROLES[k[2]][0]] * CANAL_ROLES[k[2]][1] if k[2] else 0.0)
                   for k in P["canal_keys"]])
    return xs, rs


def canal_radius(profile, x):
    xs, rs = profile
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

    base_slit = (P["slit_vS"], P["slit_vJ"], P["slit_ua"], P["slit_va"], P["slit_w"])
    counts = slit_counts(*base_slit, N)
    v_c = 0.5 * (P["slit_vS"] + P["slit_vJ"])          # axe du canal (fixe pour toutes les shape keys)
    slit = y_slit_outline(P["slit_vS"] - 0.006 * P["tip"], P["slit_vJ"], P["slit_ua"] * P["arm_len"],
                          P["slit_va"] * P["arm_len"], P["slit_w"], counts)
    tri = vulva_outline(P)
    slit_unscaled = slit.copy()
    center = np.array([0.0, v_c])
    slit = center + P["vulva_size"] * (slit - center)
    tri = center + P["vulva_size"] * (tri - center)
    d_slit = face_depth(P, slit)
    profile = canal_profile(P)
    th = -math.pi / 2 + 2 * math.pi * np.arange(N) / N  # angle des anneaux circulaires

    # ---- canal : on le construit de la fente vers le fond, puis on inverse
    canal = []  # (pts3d, tag, vulve, interieur)
    xv = P["vest_depth"]
    r_v = canal_radius(profile, xv)[0]
    circ_v = circle(r_v, N, (0.0, v_c))
    for j in range(1, P["M_vest"] + 1):
        t = j / P["M_vest"]
        e = smoothstep(t) ** 0.8
        uv = slit + e * (circ_v - slit)
        d = d_slit + xv * t
        canal.append((np.column_stack([uv, d]), "vestibule", 1.0, 1.0))

    x_end = profile[0][-1]
    xs = np.arange(xv + P["canal_step"], x_end + 1e-9, P["canal_step"])
    for x in xs:
        r = canal_radius(profile, x)[0]
        mask = float(smoothstep((x - 0.032) / 0.010) * smoothstep((x_end + 0.004 - x) / 0.012))
        rr = np.maximum(r - mask * canal_relief(P["canal_variant"], x, th), 0.002)
        uv = np.column_stack([rr * np.cos(th), v_c + rr * np.sin(th)])
        canal.append((np.column_stack([uv, np.full(N, x)]), "canal", 0.0, 1.0))

    r_end = canal_radius(profile, x_end)[0]
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
    dome = 1.0 + P["lip_dome"] * (1.0 - np.clip(((slit_unscaled[:, 1] - v_mid) / half) ** 2, 0, 1)) - P["lip_dome"] * 0.5
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
