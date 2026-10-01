"""Vagin de poche à vulve canine stylisée (personnage anthro/furry), et ses variantes.

Géométrie pure (numpy, sans bpy) : le maillage est une suite d'anneaux de N sommets.

    fond du canal (cap) -> canal -> chambre du nœud -> anneau d'entrée -> vestibule
    -> ouverture (fente en Y ou anus) -> lèvres / bourrelet -> face avant -> arrondi
    -> flancs -> arrière (cap)

Chaque anneau a la même indexation, donc toute variante de paramètres (lèvres
gonflées, détails du canal) donne exactement la même topologie : c'est ce qui
permet d'en faire des shape keys (voir SHAPE_KEYS). Les contours de la fente et de
la vulve sont échantillonnés avec une paramétrisation fixe : chaque sommet garde sa
place « structurelle » quand on change une dimension, ce qui rend les shape keys
propres et combinables.

Blocs réutilisables :
- entrées : `vulve` (plusieurs styles de lèvres par les paramètres) et `anus` ;
- canal : `canal` (vestibule, canal à chambre du nœud, fond) ;
- corps : `face_depth` (face avant, fesses éventuelles) et `anneaux_corps`
  (arrondi, flancs avec taille resserrée, arrière en œuf ou arrondi).
`build` assemble une entrée unique ; `build_double` assemble vulve + anus sur une
même face (deux canaux), en fusionnant trois maillages en anneaux.

Repère local : u = horizontal, v = vertical (0 = axe du manchon), d = profondeur
(0 = face avant, positif vers l'intérieur). Repère Blender : X = u, Y = d, Z = v + B.
Unités : mètres.
"""
import copy
import functools
import math

import numpy as np

from lib.geom import (RingMesh, catmull_rom_open, circle, ellipse, fusionner, resample_open, smooth_periodic,
                      smoothstep)

PARAMS = dict(
    N=96,                      # sommets par anneau (multiple de 8)
    entree="vulve",            # "vulve", "anus" ou "double" (vulve + anus)
    # --- manchon
    A=0.055, B=0.065,          # demi-axes de la section (11 x 13 cm)
    L=0.24,                    # longueur totale
    Df=0.030, Db=0.025,        # profondeur des arrondis avant / arrière
    m=2.5,                     # exposant superellipse des arrondis (2 = elliptique)
    m_back=None,               # exposant de l'arrondi arrière (None = m)
    rho_rim=0.92,              # limite face avant / arrondi
    face_s=(0.05, 0.13, 0.24, 0.38, 0.54, 0.72, 1.0),
    corner_n=6, side_step=0.010, back_n=7, back_tmax=0.82,
    waist=0.0, waist_d=0.13, waist_s=0.045,   # taille resserrée (sablier) : creux, position, largeur
    fesses=None,               # mini fessier : dict de réglages des fesses (voir `fesses`)
    d_entree=0.0,              # profondeur de référence de l'entrée (None = profondeur de la face)
    # --- vulve : contour en triangle inversé arrondi (points de contrôle B-spline)
    vulva_scale=0.85,
    vulva_size=1.0,            # échelle de toute la vulve (contour + fente) autour de l'axe du canal
    tip=0.0,                   # pointe du bas : +1 allongée et fine, -1 courte et arrondie
    vulva_ctrl=((0.0, -0.050), (0.014, -0.034), (0.028, -0.006), (0.036, 0.022), (0.030, 0.040),
                (0.0, 0.042), (-0.030, 0.040), (-0.036, 0.022), (-0.028, -0.006), (-0.014, -0.034)),
    # --- fente en Y (fermée) : bas de la tige, jonction, bras, demi-écart
    slit_vS=-0.031, slit_vJ=0.006, slit_ua=0.011, slit_va=0.013, slit_w=0.0004,
    arm_len=1.0,               # longueur des branches du Y (multiplicateur)
    slit_open=0.0,             # Y entrouvert : demi-écart ajouté autour de la jonction
    slit_open_span=0.005,      # portée de cette ouverture le long des branches
    slit_lens=0.0,             # fente entrouverte en lentille le long de la tige
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
    # --- anus : ouverture fermée, bourrelet (anneau gonflé <-> plissé en étoile), canal
    anus_v=-0.008,             # hauteur de l'axe du canal anal (entrée « anus » seule)
    anus_M=16,                 # boucles entre l'ouverture et le contour du bourrelet
    anus_r_open=0.0017,        # rayon de l'ouverture
    anus_R=0.017,              # rayon du contour du bourrelet
    anus_h=0.0100,             # hauteur du bourrelet
    anus_pli=0.0,              # 0 = anneau gonflé, 1 = plissé en étoile
    anus_plis_n=10,            # nombre de plis rayonnants
    anus_ouvert=0.0,           # 0 = fermé, 1 = entrouvert
    anus_vest_depth=0.012, anus_M_vest=12,
    anus_canal_keys=((0.012, 0.0055, "vestibule"), (0.018, 0.0045, "anneau"), (0.026, 0.0062, None),
                     (0.044, 0.0112, "chambre"), (0.062, 0.0095, "chambre_fin"), (0.078, 0.0070, None),
                     (0.150, 0.0068, None)),
    anus_ring_dr=0.0, anus_chamber_dr=0.0, anus_canal_variant=None,
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
CANAL_PARAMS = ("canal_keys", "vest_depth", "M_vest", "ring_dr", "chamber_dr", "canal_variant")


def params_canal(P, prefixe=""):
    """Réglages du canal : ceux du vagin, ou ceux préfixés (« anus_ ») pour le canal anal."""
    Pc = dict(P)
    if prefixe:
        Pc.update({k: P[prefixe + k] for k in CANAL_PARAMS})
    return Pc


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


def ouvrir_fente(slit, vS, vJ, ua, va, ouverture, portee, lentille):
    """Écarte les bords de la fente : en lentille le long de la tige (`lentille`), puis en un
    trou rond autour de la jonction du Y (rayon `ouverture`, effet limité à `portee`).

    L'ouverture de la jonction pousse chaque point à l'écart de la jonction, le long de son
    rayon : r -> sqrt(r² + R² exp(-(r / portee)²)). Cette fonction est croissante (R < portee),
    donc les points gardent leur angle et leur ordre : le contour ne peut pas se croiser, et
    la pointe des trois coussinets s'arrondit au lieu de se replier.
    """
    J = np.array([0.0, vJ])
    out = slit.copy()
    if lentille:
        S = np.array([0.0, vS])
        tige = J - S
        for i, p in enumerate(slit):
            t = float(np.clip(np.dot(p - S, tige) / np.dot(tige, tige), 0, 1))
            q = S + t * tige
            # seulement les points du bord de la tige (plus proches de la tige que des bras)
            bras = min(abs(np.cross(np.array([ua * sx, va]), p - J)) / math.hypot(ua, va)
                       if np.dot(p - J, np.array([ua * sx, va])) > 0 else np.inf for sx in (1, -1))
            dist = np.linalg.norm(p - q)
            if dist <= bras and dist > 1e-12:
                out[i] = p + lentille * max(0.0, math.sin(math.pi * t)) ** 1.5 * (p - q) / dist
    if ouverture:
        R = min(ouverture, 0.95 * portee)
        d = out - J
        r = np.linalg.norm(d, axis=1)
        f = np.sqrt(r * r + R * R * np.exp(-(r / portee) ** 2))
        out = J + d * (f / np.maximum(r, 1e-12))[:, None]
    return out


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


@functools.lru_cache(maxsize=32)
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


# --------------------------------------------------------------------------- face avant
def smax(a, b, k):
    """Maximum lissé (k = largeur de l'arrondi) : le creux entre deux bosses s'arrondit."""
    return 0.5 * (a + b + np.sqrt((a - b) ** 2 + k * k)) - 0.5 * k


def fesses(F, uv, rho, rho_rim):
    """Relief des fesses (vers l'avant, m) : deux dômes séparés par un sillon arrondi.

    F : réglages d'une paire de dômes, ou liste de paires (cuisses, fesses...) réunies par
    un maximum lissé ; le relief s'efface vers le bord de la face (`fondu` de la première).
    """
    u, v = uv[:, 0], uv[:, 1]
    total = None
    for G in (F if isinstance(F, (list, tuple)) else [F]):
        def joue(cu):
            x = ((u - cu) / G["ru"]) ** 2 + ((v - G["cv"]) / G["rv"]) ** 2
            r = np.maximum(1.0 - x, 0.0)
            return G["h"] * r ** G.get("galbe", 0.5) * smoothstep(r / G.get("adoucir", 0.35))

        paire = smax(joue(G["cu"]), joue(-G["cu"]), G["k"])         # max lissé : sillon arrondi
        total = paire if total is None else smax(total, paire, G["k"])
    F0 = F[0] if isinstance(F, (list, tuple)) else F
    return np.maximum(total, 0.0) * (1.0 - smoothstep((rho - F0["fondu"]) / (rho_rim - F0["fondu"])))


def face_depth(P, uv):
    if P.get("rho_fn"):                    # section de la face non elliptique (torse)
        rho = P["rho_fn"](uv)
    else:
        rho = np.sqrt((uv[:, 0] / P["A"]) ** 2 + (uv[:, 1] / P["B"]) ** 2)
    rho = np.clip(rho, 0.0, 0.999999)
    d = P["Df"] * (1 - (1 - rho ** P["m"]) ** (1 / P["m"]))
    if P["fesses"]:
        d = d - fesses(P["fesses"], uv, rho, P["rho_rim"])
        # replats : la face devient plane autour d'une entrée (r < r1), puis rejoint le relief (r2)
        for (cu, cv), r1, r2 in P.get("replats", ()):
            plan = face_depth({**P, "replats": ()}, np.array([[cu, cv]]))[0]
            w = 1.0 - smoothstep((np.hypot(uv[:, 0] - cu, uv[:, 1] - cv) - r1) / (r2 - r1))
            d = d + w * (plan - d)
    return d


# --------------------------------------------------------------------------- canal
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


def canal(Pc, ouverture, d_ouv, axe, d0, plat):
    """Anneaux du vestibule, du canal et du fond, de l'ouverture vers le fond.

    ouverture (N,2), d_ouv (N,) : bord de l'entrée ; axe (2,) : axe du canal dans la face ;
    d0 : profondeur où commence le canal (x = 0) ; plat : le vestibule se termine à
    profondeur constante (sinon il suit le relief de l'ouverture, comme le modèle d'origine).
    Retourne (anneaux [(pts3d, tag, vulve, interieur)], cap_fond(Q) -> (m,3), infos).
    """
    N = len(ouverture)
    profile = canal_profile(Pc)
    th = -math.pi / 2 + 2 * math.pi * np.arange(N) / N  # angle des anneaux circulaires
    anneaux = []
    xv = Pc["vest_depth"]
    r_v = canal_radius(profile, xv)[0]
    circ_v = circle(r_v, N, axe)
    for j in range(1, Pc["M_vest"] + 1):
        t = j / Pc["M_vest"]
        e = smoothstep(t) ** 0.8
        uv = ouverture + e * (circ_v - ouverture)
        d = d_ouv + (d0 + xv - d_ouv) * t if plat else d_ouv + xv * t
        anneaux.append((np.column_stack([uv, d]), "vestibule", 1.0, 1.0))

    x_end = profile[0][-1]
    xs = np.arange(xv + Pc["canal_step"], x_end + 1e-9, Pc["canal_step"])
    for x in xs:
        r = canal_radius(profile, x)[0]
        mask = float(smoothstep((x - 0.032) / 0.010) * smoothstep((x_end + 0.004 - x) / 0.012))
        rr = np.maximum(r - mask * canal_relief(Pc["canal_variant"], x, th), 0.002)
        uv = np.column_stack([axe[0] + rr * np.cos(th), axe[1] + rr * np.sin(th)])
        anneaux.append((np.column_stack([uv, np.full(N, d0 + x)]), "canal", 0.0, 1.0))

    r_end = canal_radius(profile, x_end)[0]
    alphas = np.linspace(0, 0.38 * math.pi, Pc["end_n"] + 1)[1:]
    for a in alphas:
        r = r_end * math.cos(a)
        uv = np.column_stack([axe[0] + r * np.cos(th), axe[1] + r * np.sin(th)])
        anneaux.append((np.column_stack([uv, np.full(N, d0 + x_end + r_end * math.sin(a))]), "fond", 0.0, 1.0))

    def cap_fond(Q):
        rr = np.hypot(Q[:, 0] - axe[0], Q[:, 1] - axe[1])
        return np.column_stack([Q, d0 + x_end + np.sqrt(np.maximum(r_end**2 - rr**2, 0.0))])

    # coupe UV après la chambre du nœud : profondeur du point qui suit « chambre_fin », + 7 mm
    roles = [k[2] for k in Pc["canal_keys"]]
    x_coupe = Pc["canal_keys"][roles.index("chambre_fin") + 1][0] + 0.007
    i_canal = [i for i, a in enumerate(anneaux) if a[1] == "canal"]
    i_coupe = min(i_canal, key=lambda i: abs(anneaux[i][0][0, 2] - d0 - x_coupe))
    infos = dict(profondeur=d0 + x_end + r_end, coupe=len(anneaux) - 1 - i_coupe)   # coupe : index après inversion
    return anneaux, cap_fond, infos


# --------------------------------------------------------------------------- entrées
def vulve(P, N, decalage=(0.0, 0.0), base=None):
    """Fente en Y, lèvres et contour de la vulve.

    Retourne dict : axe (2,), ouverture (N,2), h_ouverture (N,), anneaux [(uv, h, attrs)],
    contour (N,2). `base` : paramètres de la forme de base (topologie de la fente).
    """
    base = base or P
    dec = np.asarray(decalage, float)
    base_slit = (base["slit_vS"], base["slit_vJ"], base["slit_ua"], base["slit_va"], base["slit_w"])
    counts = slit_counts(*base_slit, N)
    v_c = 0.5 * (P["slit_vS"] + P["slit_vJ"])          # axe du canal (fixe pour toutes les shape keys)
    vS = P["slit_vS"] - 0.006 * P["tip"]
    ua, va = P["slit_ua"] * P["arm_len"], P["slit_va"] * P["arm_len"]
    slit = y_slit_outline(vS, P["slit_vJ"], ua, va, P["slit_w"], counts)
    if P["slit_open"] or P["slit_lens"]:
        slit = ouvrir_fente(slit, vS, P["slit_vJ"], ua, va, P["slit_open"], P["slit_open_span"], P["slit_lens"])
    tri = vulva_outline(P)
    slit_unscaled = slit.copy()
    center = np.array([0.0, v_c])
    slit = center + P["vulva_size"] * (slit - center) + dec
    tri = center + P["vulva_size"] * (tri - center) + dec

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
    anneaux = []
    for i in range(1, Ml + 1):
        f, hn = prof[i]
        t = i / Ml
        uv = slit + f * (tri - slit)
        h = H * hn - P["fold_amp"] * fold_mask * math.sin(math.pi * t) * max(0.0, math.sin(2 * P["fold_count"] * math.pi * t))
        inner = 1.0 - float(smoothstep((t - 0.22) / 0.15))
        # attributs pour les textures : position radiale sur la lèvre, angle, zone de la pointe
        anneaux.append((uv, h, dict(vulve=1.0, interieur=inner, levre_t=t, levre_k=np.arange(N) / N, pointe=fold_mask)))
    return dict(axe=center + dec, ouverture=slit, h_ouverture=np.zeros(N), anneaux=anneaux, contour=tri)


def anus(P, N, centre=None, angles=None):
    """Ouverture, bourrelet et contour de l'anus.

    La forme passe de l'anneau gonflé (anus_pli = 0) au plissé en étoile (anus_pli = 1)
    sans changer la topologie. `angles` : angle de chaque sommet autour du centre
    (par défaut réguliers, départ en bas).
    """
    c = np.array(centre if centre is not None else (0.0, P["anus_v"]), float)
    th = -math.pi / 2 + 2 * math.pi * np.arange(N) / N if angles is None else np.asarray(angles, float)
    pli, n = P["anus_pli"], P["anus_plis_n"]
    vallee = ((1 + np.cos(n * (th + math.pi / 2))) / 2) ** 3        # 1 dans l'axe de chaque pli (un pli en bas)

    # ouverture : petit trou rond (anneau) ou petite étoile (plissé), qui s'entrouvre
    r_o = P["anus_r_open"] * (1 + 1.8 * P["anus_ouvert"])
    r_open = r_o * ((1 - pli) + pli * (0.35 + 0.45 * (1 - vallee)))
    # contour : rond (anneau) ou losange vertical aux bords arrondis (plissé)
    R = P["anus_R"]
    a, b, p = 0.92 * R, 1.25 * R, 1.4
    losange = 1.0 / ((np.abs(np.cos(th)) / a) ** p + (np.abs(np.sin(th)) / b) ** p) ** (1 / p)
    R_out = (1 - pli) * R + pli * losange

    # anneau gonflé : cratère autour du trou, bourrelet rond à mi-rayon, pied concave
    prof_d = catmull_rom_open(((0.0, -0.10), (0.07, 0.18), (0.15, 0.47), (0.26, 0.76), (0.39, 0.94),
                               (0.53, 1.0), (0.66, 0.91), (0.78, 0.64), (0.89, 0.28), (1.0, 0.0)))

    def hauteur(t):
        h_anneau = np.interp(t, prof_d[:, 0], prof_d[:, 1])
        creux = 0.75 * (1 - t) ** 0.7 * vallee
        h_plisse = 0.55 * (1 - t * t) ** 1.2 * (0.25 + 0.75 * smoothstep(t / 0.18)) * (1 - creux)
        return P["anus_h"] * ((1 - pli) * h_anneau + pli * h_plisse)

    def point(t):
        r = r_open + (R_out - r_open) * t ** 1.35
        r = r * (1 - 0.10 * pli * vallee * (1 - t))       # les plis tirent légèrement vers le centre
        return np.column_stack([c[0] + r * np.cos(th), c[1] + r * np.sin(th)])

    M = P["anus_M"]
    anneaux = []
    for i in range(1, M + 1):
        t = i / M
        inner = 1.0 - float(smoothstep((t - 0.08) / 0.18))
        anneaux.append((point(t), hauteur(t),
                        dict(vulve=1.0, interieur=inner, levre_t=t, levre_k=np.arange(N) / N, pointe=0.0)))
    return dict(axe=c, ouverture=point(0.0), h_ouverture=hauteur(0.0), anneaux=anneaux, contour=point(1.0))


# --------------------------------------------------------------------------- corps
def echelle_corps(P, d):
    """Échelle de la section à la profondeur d (taille resserrée du sablier)."""
    return 1.0 - P["waist"] * math.exp(-((d - P["waist_d"]) / P["waist_s"]) ** 2)


def anneaux_corps(P, section, transition=None, face_arriere=False):
    """Arrondi avant, flancs et arrière : liste de (pts3d (N,3), tag), et la fonction du cap arrière.

    section (N,2) : section de référence (rho = 1) ; transition (N,2) : section ellipse
    régulière vers laquelle on glisse dans l'arrondi avant (sections non régulières).
    face_arriere : l'arrondi arrière s'arrête au bord de la face arrière (rho_rim), qui
    porte une seconde entrée (poche traversante) ; sinon il descend jusqu'au cap.
    """
    m = P["m"]
    mb = P["m_back"] or m
    out = []
    t_rim = math.acos(P["rho_rim"] ** (m / 2))
    ts = np.linspace(t_rim, 0, P["corner_n"] + 1)[1:]
    for i, t in enumerate(ts):
        rho = math.cos(t) ** (2 / m)
        sec = section
        if transition is not None:
            sec = glisser(section, transition, P["A"], P["B"], (i + 1) / len(ts))
        out.append((np.column_stack([rho * sec, np.full(len(sec), P["Df"] * (1 - math.sin(t) ** (2 / m)))]),
                    "arrondi_avant"))
    if transition is not None:
        section = transition
    L, Db = P["L"], P["Db"]
    n_side = round((L - Db - P["Df"]) / P["side_step"])
    for d in np.linspace(P["Df"], L - Db, n_side + 1)[1:] if n_side >= 1 else []:
        out.append((np.column_stack([echelle_corps(P, d) * section, np.full(len(section), d)]), "flanc"))
    s_dos = echelle_corps(P, L - Db)
    if face_arriere:
        ts_dos = np.linspace(0, math.acos(P["rho_rim"] ** (mb / 2)), P["corner_n"] + 1)[1:-1]
    else:
        ts_dos = np.linspace(0, P["back_tmax"] * math.pi / 2, P["back_n"] + 1)[1:]
    for t in ts_dos:
        rho = s_dos * math.cos(t) ** (2 / mb)
        out.append((np.column_stack([rho * section, np.full(len(section), L - Db * (1 - math.sin(t) ** (2 / mb)))]),
                    "arriere"))

    def cap_dos(Q):
        rho = np.clip(np.sqrt((Q[:, 0] / (s_dos * P["A"])) ** 2 + (Q[:, 1] / (s_dos * P["B"])) ** 2), 0, 0.999999)
        return np.column_stack([Q, L - Db * (1 - (1 - rho**mb) ** (1 / mb))])

    return out, cap_dos


def glisser(section, cible, A, B, w):
    """Points sur l'ellipse (A, B) dont l'angle passe de celui de `section` à celui de `cible`."""
    a0 = np.unwrap(np.arctan2(section[:, 1] / B, section[:, 0] / A))
    a1 = np.unwrap(np.arctan2(cible[:, 1] / B, cible[:, 0] / A))
    a1 += 2 * math.pi * np.round((a0[0] - a1[0]) / (2 * math.pi))
    a = (1 - w) * a0 + w * a1
    return np.column_stack([A * np.cos(a), B * np.sin(a)])


# --------------------------------------------------------------------------- assemblage
def _parametres(P, overrides):
    base = copy.deepcopy(P or PARAMS)
    P = copy.deepcopy(base)
    P.update(overrides)
    return base, P


def _entree(P, N, base, **kw):
    if P["entree"] == "anus":
        return anus(P, N, **kw), params_canal(P, "anus_")
    return vulve(P, N, base=base, **kw), params_canal(P)


def _region_entree(rm, P, ent, Pc, couronne):
    """Ajoute à `rm` le canal, l'ouverture, les lèvres / le bourrelet, puis la couronne de
    face (anneaux uv sans relief, jusqu'à la dernière). Retourne (cap_fond, infos du canal,
    index des anneaux remarquables)."""
    N = len(ent["ouverture"])
    d_ouv = face_depth(P, ent["ouverture"]) - ent["h_ouverture"]
    plat = P["d_entree"] is None
    d0 = float(face_depth(P, ent["axe"][None])[0]) if plat else P["d_entree"]
    anneaux, cap_fond, ic = canal(Pc, ent["ouverture"], d_ouv, ent["axe"], d0, plat)
    for pts, tag, vu, it in reversed(anneaux):
        rm.add_ring(pts, tag, vulve=vu, interieur=it)
    r = dict(fond=0, coupe=ic["coupe"], ouverture=len(rm.rings))
    rm.add_ring(np.column_stack([ent["ouverture"], d_ouv]), "fente", vulve=1.0, interieur=1.0)
    for uv, h, at in ent["anneaux"]:
        rm.add_ring(np.column_stack([uv, face_depth(P, uv) - h]), "levres", **at)
    r["bord"] = len(rm.rings) - 1
    for i, uv in enumerate(couronne):
        rm.add_ring(np.column_stack([uv, face_depth(P, uv)]), "face", vulve=0.35 if i == 0 else 0.0, interieur=0.0)
    r["couronne"] = len(rm.rings) - 1
    return cap_fond, ic, r


def _boucles(N, rings, ligne):
    """Arêtes de couture : boucles complètes des anneaux `rings` et ligne k = 0 de ligne[0] à ligne[1]."""
    c = [(r * N + k, r * N + (k + 1) % N) for r in rings for k in range(N)]
    c += [(r * N, (r + 1) * N) for r in range(ligne[0], ligne[1])]
    return c


def _zones(N, bornes):
    """Faces par zone pour un maillage en anneaux : bornes = [(zone, anneau_fin)], puis les caps."""
    zones, r0 = {}, 0
    for zone, r1 in bornes:
        zones.setdefault(zone, []).extend(range(r0 * N, r1 * N))
        r0 = r1
    return zones


def build(P=None, **overrides):
    """Retourne (verts_monde (V,3), faces, attrs, infos)."""
    base, P = _parametres(P, overrides)
    if P["entree"] == "double":
        return build_double(base, P)
    if P["entree"] == "traversant":
        return build_traversant(base, P)
    N = P["N"]
    A, B = P["A"], P["B"]
    rm = RingMesh(N)

    ent, Pc = _entree(P, N, base)
    rim = ellipse(P["rho_rim"] * A, P["rho_rim"] * B, N)
    couronne = [ent["contour"] + s * (rim - ent["contour"]) for s in P["face_s"]]
    cap_fond, ic, r = _region_entree(rm, P, ent, Pc, couronne)

    # ---- arrondi avant, flancs, arrondi arrière
    corps, cap_dos = anneaux_corps(P, ellipse(A, B, N))
    for pts, tag in corps:
        rm.add_ring(pts, tag)
    ring_dos = len(rm.rings) - 1

    # ---- caps (grilles de quads)
    q = N // 8  # index de l'anneau à -45° (départ en bas, anti-horaire)
    rm.cap(0, lambda R_: R_[:, :2], cap_fond, q, vulve=0.0, interieur=1.0)
    rm.cap(ring_dos, lambda R_: R_[:, :2], cap_dos, q, vulve=0.0, interieur=0.0)

    verts, faces, attrs = rm.build()
    world = np.column_stack([verts[:, 0], verts[:, 2], verts[:, 1] + B])
    R = len(rm.rings)
    n_fond = len(rm.cap_faces[0][3])
    zones = _zones(N, [("canal", r["coupe"]), ("entree", r["ouverture"]), ("levres", r["bord"]),
                       ("face", r["couronne"]), ("corps", R - 1)])
    zones["canal"].extend(range((R - 1) * N, (R - 1) * N + n_fond))
    zones["corps"].extend(range((R - 1) * N + n_fond, len(faces)))
    infos = dict(axe_canal_z=float(ent["axe"][1] + B), profondeur_canal=ic["profondeur"], n_anneaux=R,
                 tags=rm.tags, N=N, profondeurs=[float(x[:, 2].mean()) for x in rm.rings],
                 coutures=_boucles(N, (0, r["coupe"], r["ouverture"], r["bord"], r["couronne"], ring_dos),
                                   (0, ring_dos)),
                 zones_faces=zones, echelles_uv={"levres": 2.0, "face": 1.2})
    return world, faces, attrs, infos


# --------------------------------------------------------------------------- poche traversante
def face_arriere(P, uv):
    """Profondeur de la face arrière (seconde entrée) : l'arrondi arrière vu de derrière."""
    L, Db = P["L"], P["Db"]
    mb = P["m_back"] or P["m"]
    s = echelle_corps(P, L - Db)
    rho = np.clip(np.sqrt((uv[:, 0] / (s * P["A"])) ** 2 + (uv[:, 1] / (s * P["B"])) ** 2), 0, 0.999999)
    return L - Db * (1 - (1 - rho ** mb) ** (1 / mb))


def canal_traversant(P, ent_v, d_ouv_v, d0_v, ent_a, d_ouv_a, d0_a):
    """Canal unique de la vulve (profondeur d0_v) à l'anus (d0_a), avec l'anneau d'entrée et
    la chambre du nœud de chaque côté : chaque entrée peut servir d'entrée ou de sortie.

    Retourne (anneaux de l'anus vers la vulve, sans les ouvertures [(pts3d, tag, vulve,
    interieur)], index de l'anneau de coupe UV, longueur entre les deux vestibules).
    """
    N = len(ent_v["ouverture"])
    Pv, Pa = params_canal(P), params_canal(P, "anus_")
    th = -math.pi / 2 + 2 * math.pi * np.arange(N) / N

    def cote(Pc):
        """Profil d'un côté, de l'entrée jusqu'au point qui suit la chambre du nœud."""
        xs, rs = canal_profile(Pc)
        n = [k[2] for k in Pc["canal_keys"]].index("chambre_fin") + 2
        return xs[:n], rs[:n]

    xs_v, rs_v = cote(Pv)
    xs_a, rs_a = cote(Pa)
    profil = (np.concatenate([d0_v + xs_v, (d0_a - xs_a)[::-1]]), np.concatenate([rs_v, rs_a[::-1]]))
    assert np.all(np.diff(profil[0]) > 0), "poche trop courte pour une chambre du nœud de chaque côté"
    dv, da = d0_v + Pv["vest_depth"], d0_a - Pa["vest_depth"]

    def axe(d):
        w = smoothstep((d - dv) / (da - dv))
        return ent_v["axe"] + w * (ent_a["axe"] - ent_v["axe"])

    def vestibule(ent, d_ouv, d_fin, M):
        circ = circle(canal_radius(profil, d_fin)[0], N, axe(d_fin))
        out = []
        for j in range(1, M + 1):
            t = j / M
            e = smoothstep(t) ** 0.8
            uv = ent["ouverture"] + e * (circ - ent["ouverture"])
            out.append((np.column_stack([uv, d_ouv + (d_fin - d_ouv) * t]), "vestibule", 1.0, 1.0))
        return out

    n = max(2, round((da - dv) / P["canal_step"]))
    tube = []
    for d in np.linspace(dv, da, n + 1)[1:-1]:
        r = canal_radius(profil, d)[0]
        mask = float(smoothstep((d - d0_v - 0.032) / 0.010) * smoothstep((d0_a - d - 0.028) / 0.010))
        rr = np.maximum(r - mask * canal_relief(P["canal_variant"], d - d0_v, th), 0.002)
        c = axe(d)
        tube.append((np.column_stack([c[0] + rr * np.cos(th), c[1] + rr * np.sin(th), np.full(N, d)]),
                     "canal", 0.0, 1.0))
    vest_a = vestibule(ent_a, d_ouv_a, da, Pa["M_vest"])
    vest_v = vestibule(ent_v, d_ouv_v, dv, Pv["M_vest"])
    return vest_a + tube[::-1] + vest_v[::-1], len(vest_a) + len(tube) // 2, da - dv


def build_traversant(base, P):
    """Poche traversante : vulve devant, anus derrière, un seul canal entre les deux.

    Chaîne fermée d'anneaux (un tore, sans cap) : fente -> lèvres -> face avant -> arrondi
    avant -> flancs -> arrondi arrière -> face arrière -> bourrelet de l'anus -> ouverture
    de l'anus -> vestibule -> canal -> vestibule -> retour à la fente.
    """
    N = P["N"]
    A, B = P["A"], P["B"]
    rm = RingMesh(N)
    ent_v = vulve(P, N, base=base)
    ent_a = anus(P, N)
    d0_v = float(face_depth(P, ent_v["axe"][None])[0])
    d0_a = float(face_arriere(P, ent_a["axe"][None])[0])
    d_ouv_v = face_depth(P, ent_v["ouverture"]) - ent_v["h_ouverture"]
    d_ouv_a = face_arriere(P, ent_a["ouverture"]) + ent_a["h_ouverture"]

    r = {}
    rm.add_ring(np.column_stack([ent_v["ouverture"], d_ouv_v]), "fente", vulve=1.0, interieur=1.0)
    for uv, h, at in ent_v["anneaux"]:
        rm.add_ring(np.column_stack([uv, face_depth(P, uv) - h]), "levres", **at)
    r["bord_vulve"] = len(rm.rings) - 1
    section = ellipse(A, B, N)
    rim = P["rho_rim"] * section
    for i, s in enumerate(P["face_s"]):
        uv = ent_v["contour"] + s * (rim - ent_v["contour"])
        rm.add_ring(np.column_stack([uv, face_depth(P, uv)]), "face", vulve=0.35 if i == 0 else 0.0, interieur=0.0)
    r["bord_face"] = len(rm.rings) - 1
    corps, _ = anneaux_corps(P, section, face_arriere=True)
    for pts, tag in corps:
        rm.add_ring(pts, tag)
    rim_b = P["rho_rim"] * echelle_corps(P, P["L"] - P["Db"]) * section
    r["bord_arriere"] = len(rm.rings)
    for s in P["face_s"][::-1]:
        uv = ent_a["contour"] + s * (rim_b - ent_a["contour"])
        rm.add_ring(np.column_stack([uv, face_arriere(P, uv)]), "face_arriere",
                    vulve=0.35 if s == P["face_s"][0] else 0.0, interieur=0.0)
    r["bord_anus"] = len(rm.rings)
    for uv, h, at in ent_a["anneaux"][::-1]:
        rm.add_ring(np.column_stack([uv, face_arriere(P, uv) + h]), "anus", **at)
    r["ouverture_anus"] = len(rm.rings)
    rm.add_ring(np.column_stack([ent_a["ouverture"], d_ouv_a]), "anus", vulve=1.0, interieur=1.0)
    tube, i_coupe, longueur = canal_traversant(P, ent_v, d_ouv_v, d0_v, ent_a, d_ouv_a, d0_a)
    r["coupe"] = len(rm.rings) + i_coupe
    for pts, tag, vu, it in tube:
        rm.add_ring(pts, tag, vulve=vu, interieur=it)

    verts, faces, attrs = rm.build(ferme=True)
    world = np.column_stack([verts[:, 0], verts[:, 2], verts[:, 1] + B])
    R = len(rm.rings)
    boucles = (0, r["bord_vulve"], r["bord_face"], r["bord_arriere"], r["bord_anus"], r["ouverture_anus"], r["coupe"])
    coutures = _boucles(N, boucles, (0, R - 1)) + [((R - 1) * N, 0)]
    zones = _zones(N, [("levres", r["bord_vulve"]), ("face", r["bord_face"]), ("corps", r["bord_arriere"]),
                       ("face_arriere", r["bord_anus"]), ("anus", r["ouverture_anus"]), ("canal", R)])
    infos = dict(axe_canal_z=float(ent_v["axe"][1] + B), axe_anus_z=float(ent_a["axe"][1] + B),
                 profondeur_canal=d0_a - d0_v, profondeur_anus=d0_a - d0_v, longueur_tube=longueur,
                 n_anneaux=R, tags=rm.tags, N=N, profondeurs=[float(x[:, 2].mean()) for x in rm.rings],
                 coutures=coutures, zones_faces=zones,
                 echelles_uv={"levres": 2.0, "anus": 2.0, "face": 1.2, "face_arriere": 1.2})
    return world, faces, attrs, infos


# --------------------------------------------------------------------------- double entrée
def rayon_vers(centre, angles, courbe):
    """Intersections des rayons partant de `centre` aux `angles` avec une polyligne fermée dense."""
    seg_a, seg_b = courbe, np.roll(courbe, -1, axis=0)
    out = []
    for a in angles:
        d = np.array([math.cos(a), math.sin(a)])
        e = seg_b - seg_a
        w = seg_a - centre
        den = d[0] * e[:, 1] - d[1] * e[:, 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / den
            s = (w[:, 0] * d[1] - w[:, 1] * d[0]) / den
        ok = (np.abs(den) > 1e-15) & (s >= -1e-9) & (s <= 1 + 1e-9) & (t > 0)
        out.append(centre + t[ok].min() * d)
    return np.array(out)


def _demi_ellipse(cu, cv, a, b, bas, n=4000):
    """Demi-ellipse dense (du côté bas ou haut), de (+a, cv) à (-a, cv)."""
    t = np.linspace(0, math.pi, n)
    sgn = -1.0 if bas else 1.0
    return np.column_stack([cu + a * np.cos(t), cv + sgn * b * np.sin(t)])


@functools.lru_cache(maxsize=8)
def _topologie_double(cle):
    """Bords des deux régions (vulve en bas, anus en haut), calculés sur la forme de base.

    Retourne (BV (Nv,2), k_J, BA (Na,2), angles de l'anus (Na,)).
    """
    P = dict(cle)
    Nv = P["N"]
    ent = vulve(P, Nv, decalage=(0.0, P["vulve_v"] - 0.5 * (P["slit_vS"] + P["slit_vJ"])))
    c_v = ent["axe"]
    tri = ent["contour"]
    vm, wm = P["milieu_v"], P["milieu_w"]
    # bord de la vulve : demi-ellipse basse + segment du milieu
    bas = _demi_ellipse(0.0, vm, wm, vm - P["vulve_bas"], True)
    bord_v = np.vstack([bas[::-1], np.column_stack([np.linspace(wm, -wm, 400)[1:-1], np.full(398, vm)])])
    ang_v = np.arctan2(tri[:, 1] - c_v[1], tri[:, 0] - c_v[0])
    BV = rayon_vers(c_v, ang_v, bord_v)
    # jonctions : le rayon le plus proche de chaque coin devient exactement le coin
    a_jr = math.atan2(vm - c_v[1], wm - c_v[0])
    k_J = int(np.argmin(np.abs(np.angle(np.exp(1j * (ang_v - a_jr))))))
    BV[k_J] = (wm, vm)
    BV[Nv - k_J] = (-wm, vm)
    milieu = BV[k_J:Nv - k_J + 1][::-1]                # de J_L à J_R (gauche -> droite), c + 1 points
    c = len(milieu) - 1
    assert c % 2 == 0, "le milieu doit avoir un nombre pair de segments"
    # bord de l'anus : milieu (partagé) + demi-ellipse haute échantillonnée en angle depuis l'anus
    c_a = np.array([0.0, P["anus_centre_v"]])
    Na = P["anus_N"]
    while Na % 4 or (Nv + Na - 2 * c) % 8:
        Na += 1
    haut = _demi_ellipse(0.0, vm, wm, P["anus_haut"] - vm, False)
    a0 = math.atan2(vm - c_a[1], wm)
    a1 = math.atan2(vm - c_a[1], -wm) % (2 * math.pi)
    n_haut = Na - c - 1
    angs = a0 + (a1 - a0) * np.arange(1, n_haut + 1) / (n_haut + 1)
    arc = rayon_vers(c_a, angs, haut)
    h = c // 2
    BA = np.vstack([milieu[h:], arc, milieu[:h]])
    ang_a = np.unwrap(np.arctan2(BA[:, 1] - c_a[1], BA[:, 0] - c_a[0]))
    ang_a = ang_a - 2 * math.pi * np.round((ang_a[0] + math.pi / 2) / (2 * math.pi))
    return BV, k_J, BA, ang_a, Na


def build_double(base, P):
    """Vulve (en bas) et anus (en haut) sur une même face, deux canaux séparés.

    Trois maillages en anneaux, fusionnés : région de la vulve (Nv), région de l'anus (Na),
    corps (Nc = 4 k_J + Na - Nv). Les bords des régions et la topologie sont fixés par la
    forme de base, donc les shape keys gardent la même topologie.
    """
    Nv = P["N"]
    replats = (((0.0, P["anus_centre_v"]), 0.8 * P["anus_R"], P["anus_R"] + 0.013),)
    if P.get("replat_vulve"):              # (r1, r2) : face aussi aplanie sous la vulve (torse)
        replats += (((0.0, P["vulve_v"]),) + tuple(P["replat_vulve"]),)
    P = dict(P, replats=replats)
    cle = tuple(sorted((k, v) for k, v in base.items() if not isinstance(v, (dict, list)) and not callable(v)))
    BV, k_J, BA, ang_a, Na = _topologie_double(cle)
    c = Nv - 2 * k_J
    h = c // 2
    A, B = P["A"], P["B"]

    # ---- région de la vulve
    rv = RingMesh(Nv)
    ent_v = vulve(P, Nv, decalage=(0.0, P["vulve_v"] - 0.5 * (P["slit_vS"] + P["slit_vJ"])), base=base)
    couronne_v = [ent_v["contour"] + s * (BV - ent_v["contour"]) for s in P["face_s_regions"]]
    fond_v, ic_v, r_v = _region_entree(rv, P, ent_v, params_canal(P), couronne_v)
    rv.cap(0, lambda R_: R_[:, :2], fond_v, Nv // 8, vulve=0.0, interieur=1.0)

    # ---- région de l'anus
    ra = RingMesh(Na)
    ent_a = anus(P, Na, centre=(0.0, P["anus_centre_v"]), angles=ang_a)
    couronne_a = [ent_a["contour"] + s * (BA - ent_a["contour"]) for s in P["face_s_regions"]]
    fond_a, ic_a, r_a = _region_entree(ra, P, ent_a, params_canal(P, "anus_"), couronne_a)
    ra.cap(0, lambda R_: R_[:, :2], fond_a, Na // 8, vulve=0.0, interieur=1.0)

    # ---- corps : bord commun C, face jusqu'à l'arrondi, flancs, arrière
    Cv = rv.rings[-1]
    Ca = ra.rings[-1]
    C = np.vstack([Cv[:k_J + 1], Ca[h + 1:Na - h], Cv[Nv - k_J:]])
    Nc = len(C)
    rc = RingMesh(Nc)
    rc.add_ring(C, "face", vulve=0.0, interieur=0.0)
    centre_c = np.array([0.0, 0.5 * (C[:, 1].min() + C[:, 1].max())])
    # bord de la face : ellipse (A, B), ou section fournie (polyligne dense, rho = 1)
    rim_dense = P["rho_rim"] * (P["section_dense"]() if P.get("section_dense") else ellipse(A, B, 4000))
    rim = rayon_vers(centre_c, np.arctan2(C[:, 1] - centre_c[1], C[:, 0]), rim_dense)
    for s in P["face_s"]:
        uv = C[:, :2] + s * (rim - C[:, :2])
        rc.add_ring(np.column_stack([uv, face_depth(P, uv)]), "face", vulve=0.0, interieur=0.0)
    ring_bord = len(rc.rings) - 1
    # corps au-dessus de la face : fourni (torse) ou manchon (arrondi, flancs, arrière)
    if P.get("corps_double"):
        corps, cap_dos, info_corps = P["corps_double"](P, rim / P["rho_rim"], Nc)
    else:
        corps, cap_dos = anneaux_corps(P, rim / P["rho_rim"], transition=ellipse(A, B, Nc))
        info_corps = dict(boucles=(), ligne=0, zones=())
    debut_corps = len(rc.rings)
    for pts, tag in corps:
        rc.add_ring(pts, tag)
    ring_dos = len(rc.rings) - 1
    rc.cap(ring_dos, lambda R_: R_[:, :2], cap_dos, Nc // 8, vulve=0.0, interieur=0.0)

    # ---- fusion : C = sommets des bords des régions ; milieu de l'anus = milieu de la vulve
    parties = [rv.build(), ra.build(), rc.build()]
    Rv, Ra = len(rv.rings), len(ra.rings)
    bv = (Rv - 1) * Nv
    ba = (Ra - 1) * Na
    liens = []
    for j in range(h + 1):                               # BA[j] = M[h + j] = BV[k_J + h - j]
        liens.append((1, ba + j, 0, bv + k_J + h - j))
    for j in range(Na - h, Na):                          # BA[j] = M[j - (Na - h)] = BV[k_J + c - m]
        liens.append((1, ba + j, 0, bv + k_J + c - (j - (Na - h))))
    for i in range(Nc):
        if i <= k_J:
            liens.append((2, i, 0, bv + i))
        elif i < k_J + Na - c:
            liens.append((2, i, 1, ba + h + (i - k_J)))
        else:
            liens.append((2, i, 0, bv + Nv - k_J + (i - (k_J + Na - c))))
    verts, faces, attrs, idx, f_off = fusionner(parties, liens)
    world = P["monde"](verts) if P.get("monde") else np.column_stack([verts[:, 0], verts[:, 2], verts[:, 1] + B])

    # ---- coutures et zones (indices globaux)
    coutures = []
    boucles_corps = (ring_bord, ring_dos) + tuple(debut_corps + b for b in info_corps["boucles"])
    k_ligne = info_corps["ligne"]          # ligne de couture verticale du corps (0 = bas de la vulve)
    for p, (N_, rings, ligne) in enumerate([
            (Nv, (0, r_v["coupe"], r_v["ouverture"], r_v["bord"], r_v["couronne"]), (0, r_v["couronne"])),
            (Na, (0, r_a["coupe"], r_a["ouverture"], r_a["bord"], r_a["couronne"]), (0, r_a["couronne"])),
            (Nc, boucles_corps, None)]):
        if ligne is None:
            liste = _boucles(N_, rings, (0, 0)) + [(r * N_ + k_ligne, (r + 1) * N_ + k_ligne) for r in range(ring_dos)]
        else:
            liste = _boucles(N_, rings, ligne)
        coutures += [(int(idx[p][a]), int(idx[p][b])) for a, b in liste]
    coutures = sorted({tuple(sorted(e)) for e in coutures if e[0] != e[1]})

    zones = {}

    def ajouter(zone, p, faces_locales):
        zones.setdefault(zone, []).extend(f_off[p] + f for f in faces_locales)

    for p, (N_, r_, R_) in enumerate([(Nv, r_v, Rv), (Na, r_a, Ra)]):
        suffixe = "" if p == 0 else "_anus"
        ajouter("canal" + suffixe, p, range(0, r_["coupe"] * N_))
        ajouter("entree" + suffixe, p, range(r_["coupe"] * N_, r_["ouverture"] * N_))
        ajouter("levres" if p == 0 else "anus", p, range(r_["ouverture"] * N_, r_["bord"] * N_))
        ajouter("face" if p == 0 else "face_anus", p, range(r_["bord"] * N_, (R_ - 1) * N_))
        ajouter("canal" + suffixe, p, range((R_ - 1) * N_, len(parties[p][1])))
    ajouter("face_fesses", 2, range(0, ring_bord * Nc))
    r0 = ring_bord
    for zone, fin in info_corps["zones"]:  # zones du corps fourni (torse, épaules, cou...)
        ajouter(zone, 2, range(r0 * Nc, (debut_corps + fin) * Nc))
        r0 = debut_corps + fin
    ajouter("corps", 2, range(r0 * Nc, len(parties[2][1])))

    infos = dict(axe_canal_z=float(ent_v["axe"][1] + B), axe_anus_z=float(ent_a["axe"][1] + B),
                 profondeur_canal=ic_v["profondeur"], profondeur_anus=ic_a["profondeur"],
                 n_anneaux=Rv + Ra + len(rc.rings), N=Nv, N_anus=Na, N_corps=Nc, tags=None,
                 coutures=coutures, zones_faces=zones,
                 echelles_uv={"levres": 2.0, "anus": 2.0, "face": 1.2, "face_anus": 1.2})
    return world, faces, attrs, infos
