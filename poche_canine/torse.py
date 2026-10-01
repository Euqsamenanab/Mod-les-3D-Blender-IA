"""Onahole torse : torse anthro féminin sans bras, jambes ni tête (moignons arrondis),
avec la vulve et l'anus à l'entrejambe, deux canaux séparés.

Construction (réutilise `build_double` de sleeve.py) :
- l'entrejambe, vue de dessous, est une « face » : région de la vulve (devant), région de
  l'anus (derrière), puis l'anneau commun qui s'élargit jusqu'au bord du bassin, avec les
  moignons de cuisses et le bas des fesses en relief ;
- au-dessus, le torse est une suite d'anneaux horizontaux (N_corps sommets chacun, angle
  régulier) jusqu'au moignon de cou, fermé par une grille.

Chaque section du torse est un rayon polaire R(phi, z) autour de l'axe vertical : une
superellipse (largeur, profondeur avant / arrière) plus des bosses (seins, tétons, fesses,
ventre, moignons de bras, omoplates) et des sillons (colonne, ligne blanche, abdominaux,
nombril, plis de l'aine). Les réglages du corps ne changent jamais la topologie : ce sont
des shape keys, comme ceux de la vulve et de l'anus.

Repère du torse : x = gauche-droite, y = avant (-) / arrière (+), z = haut. phi = -pi/2
devant, 0 côté +x, +pi/2 derrière. Unités : mètres, grandeur nature (l'échelle de tout
l'objet se règle avec la propriété « Echelle »).
"""
import math

import numpy as np

from lib.geom import smoothstep
from poche_canine.sleeve import PARAMS, smax
from poche_canine.variantes import CLES_CANAL, CLES_ANUS, LEVRES, cles_anus, cles_vulve

DECALAGE_Z = 0.08          # hauteur ajoutée pour poser le bas des moignons de cuisses vers z = 0
DEVANT = -math.pi / 2

# --------------------------------------------------------------------------- profil du corps
# hauteur z : demi-largeur, demi-profondeur avant, demi-profondeur arrière, exposant
PROFIL = (
    (0.085, 0.168, 0.099, 0.102, 2.4),     # bas du bassin (bord de l'entrejambe)
    (0.120, 0.176, 0.100, 0.104, 2.3),     # hanches
    (0.190, 0.165, 0.094, 0.092, 2.3),
    (0.250, 0.136, 0.088, 0.076, 2.2),     # creux des reins
    (0.295, 0.122, 0.086, 0.074, 2.2),     # taille
    (0.360, 0.128, 0.094, 0.082, 2.2),     # sous les seins
    (0.425, 0.136, 0.100, 0.088, 2.3),     # poitrine
    (0.475, 0.143, 0.094, 0.090, 2.5),     # aisselles
    (0.515, 0.152, 0.080, 0.084, 2.7),     # épaules
    (0.550, 0.118, 0.064, 0.070, 2.4),
    (0.575, 0.070, 0.052, 0.058, 2.1),     # base du cou
    (0.598, 0.056, 0.050, 0.052, 2.0),
    (0.635, 0.053, 0.048, 0.050, 2.0),     # haut du cou
)
Z_BAS, Z_HAUT = PROFIL[0][0], PROFIL[-1][0]

CORPS = dict(
    t_hanches=1.0, t_taille=1.0, t_epaules=1.0,
    t_seins=1.0, t_seins_haut=0.0, t_tetons=1.0,
    t_fesses=1.0, t_fesses_haut=0.0,
    t_ventre=1.0, t_muscles=1.0, t_cuisses=1.0,
)


def pchip(x, y, xq):
    """Interpolation cubique monotone (Fritsch-Carlson) : courbe lisse, sans dépassement."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    h = np.diff(x)
    dl = np.diff(y) / h
    m = np.zeros_like(y)
    for i in range(1, len(y) - 1):
        if dl[i - 1] * dl[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / dl[i - 1] + w2 / dl[i])
    m[0], m[-1] = 0.0, dl[-1]           # tangente verticale en bas : raccord sans pli avec l'entrejambe
    xq = np.clip(xq, x[0], x[-1])
    i = np.clip(np.searchsorted(x, xq) - 1, 0, len(h) - 1)
    t = (xq - x[i]) / h[i]
    h00, h10 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t
    h01, h11 = -2 * t**3 + 3 * t**2, t**3 - t**2
    return h00 * y[i] + h10 * h[i] * m[i] + h01 * y[i + 1] + h11 * h[i] * m[i + 1]


_COLS = np.array(PROFIL)


def profil(z):
    """Demi-largeur, demi-profondeurs avant / arrière et exposant à la hauteur z."""
    return [pchip(_COLS[:, 0], _COLS[:, j], z) for j in range(1, 5)]


def _dome(x, galbe=0.55, adoucir=0.35):
    """Dôme de hauteur 1 au centre (x = distance normalisée au carré), raccord adouci au bord."""
    r = np.maximum(1.0 - x, 0.0)
    return r ** galbe * smoothstep(r / adoucir)


def _ecart_phi(phi, phi0):
    return np.angle(np.exp(1j * (phi - phi0)))


def _bosse(phi, z, R0, phi0, z0, rh, r_haut, r_bas, h, galbe=0.55, adoucir=0.35, galbe_haut=None):
    """Bosse sur le torse : rh = rayon horizontal (longueur d'arc), r_haut / r_bas = rayons
    vertical au-dessus / en dessous du centre, h = saillie (m). galbe_haut : profil de la
    moitié haute (> 1 : pente concave, comme le haut d'un sein)."""
    sh = _ecart_phi(phi, phi0) * R0 / rh
    rv = np.where(z >= z0, r_haut, r_bas)
    sv = (z - z0) / rv
    g = galbe
    if galbe_haut is not None:
        g = galbe + (galbe_haut - galbe) * smoothstep(sv / 0.45)
    return h * _dome(sh * sh + sv * sv, g, adoucir)


def _sillon(phi, z, R0, a, b, largeur, prof):
    """Sillon le long du segment a -> b, en coordonnées (longueur d'arc depuis l'avant, z)."""
    s = _ecart_phi(phi, DEVANT) * R0
    p = np.stack([s, z], axis=-1)
    a, b = np.array(a, float), np.array(b, float)
    ab = b - a
    t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
    d = np.linalg.norm(p - (a + t[..., None] * ab), axis=-1)
    fin = np.sin(math.pi * t) ** 0.4                     # s'efface aux deux bouts
    return -prof * np.exp(-(d / largeur) ** 2) * fin


def z_raccord(z, w=0.03):
    """Hauteur « aplatie » près du bas du torse : dz'/dz = 0 en Z_BAS, donc toute la section
    (profil et bosses) arrive à la verticale, comme l'arrondi de l'entrejambe : pas de pli."""
    t = np.clip(z - Z_BAS, 0, None)
    return Z_BAS + np.where(t < w, t * t / (2 * w), t - w / 2)


def rayon(P, phi, z):
    """Rayon polaire du torse R(phi, z) (tableaux de même forme)."""
    z = z_raccord(z)
    a, bf, bb, ex = profil(z)
    # largeur des hanches, finesse de la taille, carrure
    a = a * (1 + 0.10 * (P["t_hanches"] - 1) * np.exp(-((z - 0.13) / 0.07) ** 2))
    taille = 1 - 0.09 * (P["t_taille"] - 1) * np.exp(-((z - 0.29) / 0.06) ** 2)
    a, bf, bb = a * taille, bf * taille, bb * taille
    a = a * (1 + 0.10 * (P["t_epaules"] - 1) * np.exp(-((z - 0.51) / 0.04) ** 2))
    c, s = np.cos(phi), np.sin(phi)
    b = np.where(s < 0, bf, bb)
    R0 = 1.0 / ((np.abs(c) / a) ** ex + (np.abs(s) / b) ** ex) ** (1 / ex)

    R = R0.copy()
    # seins (paire, sillon entre les deux) : haut en pente douce depuis le haut de la poitrine,
    # bas bien rond ; tétons
    ks, kh = P["t_seins"], P["t_seins_haut"]
    zs = 0.418 + 0.012 * kh
    seins = [_bosse(phi, z, R0, DEVANT + sx * 0.43, zs, 0.090 * ks ** 0.35, 0.120 * ks ** 0.25,
                    (0.058 - 0.006 * kh) * ks ** 0.3, 0.060 * ks, galbe=0.5, adoucir=0.55, galbe_haut=1.7)
             for sx in (1, -1)]
    R = R + smax(seins[0], seins[1], 0.009)
    kt = P["t_tetons"]
    for sx in (1, -1):
        phi_t, z_t = DEVANT + sx * 0.45, zs - 0.004
        R = R + _bosse(phi, z, R0, phi_t, z_t, 0.017 * kt ** 0.5, 0.017 * kt ** 0.5, 0.017 * kt ** 0.5,
                       0.0022 * kt, galbe=0.25, adoucir=0.25) * smoothstep(ks * 4)
        R = R + _bosse(phi, z, R0, phi_t, z_t, 0.0055 * kt ** 0.5, 0.0055 * kt ** 0.5, 0.0055 * kt ** 0.5,
                       0.0065 * kt, galbe=0.45, adoucir=0.4)
    # fesses (paire, sillon entre les deux)
    kf, kfh = P["t_fesses"], P["t_fesses_haut"]
    zf = 0.140 + 0.018 * kfh
    fesses = [_bosse(phi, z, R0, -DEVANT + sx * 0.46, zf, 0.112 * kf ** 0.3, 0.130 * kf ** 0.25,
                     0.072, 0.060 * kf, galbe=0.55, adoucir=0.6, galbe_haut=1.5) for sx in (1, -1)]
    R = R + smax(fesses[0], fesses[1], 0.016)
    # ventre (un peu de gras : large et doux), nombril
    kv = P["t_ventre"]
    R = R + _bosse(phi, z, R0, DEVANT, 0.195, 0.16, 0.12, 0.10, 0.014 * kv, galbe=1.8, adoucir=1.0)
    R = R + _bosse(phi, z, R0, DEVANT, 0.258, 0.009, 0.010, 0.008, -0.007, galbe=0.6, adoucir=0.5)
    # muscles : ligne blanche, abdominaux, plis de l'aine, colonne, omoplates, clavicules
    km = P["t_muscles"]
    R = R + _sillon(phi, z, R0, (0, 0.27), (0, 0.375), 0.006, 0.0022 * km)
    for za in (0.305, 0.34):
        R = R + _sillon(phi, z, R0, (-0.045, za), (0.045, za), 0.005, 0.0014 * km)
    for sx in (1, -1):
        R = R + _sillon(phi, z, R0, (sx * 0.095, 0.165), (sx * 0.03, 0.075), 0.009, 0.0035 * km)
        R = R + _bosse(phi, z, R0, -DEVANT + sx * 0.42, 0.455, 0.06, 0.05, 0.05, 0.007 * km, galbe=0.8)
        R = R + _sillon(phi, z, R0, (sx * 0.02, 0.538), (sx * 0.11, 0.548), 0.008, -0.0035)   # clavicule
    dos = _ecart_phi(phi, -DEVANT) * R0
    R = R - (0.0045 + 0.002 * km) * np.exp(-(dos / 0.011) ** 2) * smoothstep((z - 0.17) / 0.06) \
        * smoothstep((0.56 - z) / 0.05)
    # moignons de bras : bout arrondi, raccord adouci (deltoïde)
    for phi_b in (0.0, math.pi):
        R = R + _bosse(phi, z, R0, phi_b, 0.490, 0.066, 0.058, 0.070, 0.072 * P["t_epaules"] ** 0.5,
                       galbe=0.5, adoucir=0.5)
    return R


# --------------------------------------------------------------------------- entrejambe
def rho_bas(P):
    """rho de la face de l'entrejambe : 1 sur la section du bas du bassin."""
    def f(uv):
        phi = np.arctan2(uv[:, 1], uv[:, 0])
        return np.hypot(uv[:, 0], uv[:, 1]) / rayon(P, phi, np.full(len(uv), Z_BAS))
    return f


def section_bas(P):
    def f():
        phi = DEVANT + 2 * math.pi * np.arange(4000) / 4000
        R = rayon(P, phi, np.full(4000, Z_BAS))
        return np.column_stack([R * np.cos(phi), R * np.sin(phi)])
    return f


def bosses_bas(P):
    """Relief de l'entrejambe (vers le bas) : moignons de cuisses, bas des fesses."""
    kc, kf = P["t_cuisses"], P["t_fesses"]
    # cuisses : le bord extérieur du dôme tombe sur le bord de l'entrejambe, avec une tangente
    # verticale qui continue celle du bas des hanches (pas de pli entre hanche et cuisse)
    return [dict(cu=0.090, cv=-0.010, ru=0.068 * kc ** 0.4, rv=0.090 * kc ** 0.3, h=0.100 * kc, k=0.026,
                 galbe=0.5, adoucir=0.06, fondu=0.93),
            dict(cu=0.064, cv=0.078, ru=0.072, rv=0.066, h=0.040 * kf, k=0.020, galbe=0.6, adoucir=0.5)]


# --------------------------------------------------------------------------- torse (anneaux)
def hauteurs():
    """Hauteurs des anneaux du torse (fixes : la topologie ne dépend d'aucun réglage)."""
    z, out = Z_BAS, []
    while z < Z_HAUT - 1e-9:
        pas = 0.0042 if 0.38 < z < 0.585 else 0.0058
        z = min(z + pas, Z_HAUT)
        out.append(z)
    return np.array(out)


def anneaux_torse(P, section, Nc):
    """Anneaux au-dessus de la face : arrondi du bassin (glisse vers un angle régulier), torse,
    dôme du moignon de cou, et la fonction du cap du cou."""
    m = P["m"]
    phi_k = DEVANT + 2 * math.pi * np.arange(Nc) / Nc
    a0 = np.unwrap(np.arctan2(section[:, 1], section[:, 0]))
    a1 = phi_k + 2 * math.pi * np.round((a0[0] - phi_k[0]) / (2 * math.pi))
    out = []
    t_rim = math.acos(P["rho_rim"] ** (m / 2))
    ts = np.linspace(t_rim, 0, P["corner_n"] + 1)[1:]
    for i, t in enumerate(ts):
        a = a0 + (a1 - a0) * (i + 1) / len(ts)
        rho = math.cos(t) ** (2 / m)
        R = rayon(P, a, np.full(Nc, Z_BAS))
        d = P["Df"] * (1 - math.sin(t) ** (2 / m))
        out.append((np.column_stack([rho * R * np.cos(a), rho * R * np.sin(a), np.full(Nc, d)]), "bassin"))
    zs = hauteurs()
    i_taille = i_cou = None
    for z in zs:
        R = rayon(P, phi_k, np.full(Nc, z))
        out.append((np.column_stack([R * np.cos(phi_k), R * np.sin(phi_k), np.full(Nc, z)]), "torse"))
        if i_taille is None and z >= 0.30:
            i_taille = len(out) - 1
        if i_cou is None and z >= 0.578:
            i_cou = len(out) - 1
    # dôme du moignon de cou
    R_cou = rayon(P, phi_k, np.full(Nc, Z_HAUT))
    r_d = 0.8 * float(R_cou.mean())
    for t in np.linspace(0, 0.84 * math.pi / 2, 9)[1:]:
        out.append((np.column_stack([math.cos(t) * R_cou * np.cos(phi_k), math.cos(t) * R_cou * np.sin(phi_k),
                                     np.full(Nc, Z_HAUT + r_d * math.sin(t))]), "cou"))

    def cap_cou(Q):
        phi = np.arctan2(Q[:, 1], Q[:, 0])
        rho = np.clip(np.hypot(Q[:, 0], Q[:, 1]) / rayon(P, phi, np.full(len(Q), Z_HAUT)), 0, 0.999999)
        return np.column_stack([Q, Z_HAUT + r_d * np.sqrt(1 - rho * rho)])

    info = dict(boucles=(i_taille, i_cou), ligne=Nc // 2,
                zones=(("bassin_torse", i_taille), ("poitrine", i_cou)))
    return out, cap_cou, info


def monde(verts):
    return np.column_stack([verts[:, 0], verts[:, 1], verts[:, 2] + DECALAGE_Z])


# --------------------------------------------------------------------------- paramètres et shape keys
STYLES = ("classique", "bulbe", "coeur", "fente")
CLES_STYLE = sorted({k for s in STYLES for k in LEVRES[s]})


def style(nom):
    """Tous les réglages de lèvres d'un style (valeurs d'origine pour ceux qu'il ne change pas)."""
    return {k: LEVRES[nom].get(k, PARAMS[k]) for k in CLES_STYLE}


def parametres(levres="bulbe"):
    """Paramètres et shape keys du torse."""
    P = {**PARAMS, **CORPS, **style(levres)}
    P.update(
        entree="double", N=144, anus_N=88, A=0.16, B=0.10,
        Df=Z_BAS, m=1.8, rho_rim=0.97, corner_n=5,
        vulve_v=-0.030, milieu_v=0.045, milieu_w=0.066, vulve_bas=-0.097,
        anus_centre_v=0.077, anus_haut=0.112,
        face_s_regions=(0.16, 0.36, 0.58, 0.80, 1.0),
        face_s=(0.05, 0.11, 0.18, 0.26, 0.35, 0.45, 0.55, 0.64, 0.72, 0.79, 0.85, 0.90, 0.95, 1.0),
        replat_vulve=(0.050, 0.078), d_entree=None,
    )
    P["rho_fn"] = rho_bas(P)
    P["section_dense"] = section_bas(P)
    P["fesses"] = bosses_bas(P)
    P["corps_double"] = anneaux_torse
    P["monde"] = monde

    cles = {}
    for s in STYLES:
        if s != levres:
            cles[f"Style_{s.capitalize()}"] = style(s)
    cles.update(cles_vulve(P, levres))
    cles.update(CLES_CANAL)
    cles.update(cles_anus(P))
    corps = {
        "Seins_Gros": dict(t_seins=1.45), "Seins_Petits": dict(t_seins=0.55),
        "Seins_Hauts": dict(t_seins_haut=1.0), "Seins_Bas": dict(t_seins_haut=-1.0),
        "Tetons_Gros": dict(t_tetons=1.8), "Tetons_Petits": dict(t_tetons=0.45),
        "Fesses_Grosses": dict(t_fesses=1.4), "Fesses_Petites": dict(t_fesses=0.6),
        "Fesses_Rebondies": dict(t_fesses_haut=1.0),
        "Hanches_Larges": dict(t_hanches=1.8), "Hanches_Etroites": dict(t_hanches=0.3),
        "Taille_Fine": dict(t_taille=2.0), "Taille_Large": dict(t_taille=0.0),
        "Ventre_Rond": dict(t_ventre=2.6), "Ventre_Plat": dict(t_ventre=0.0),
        "Muscles_Marques": dict(t_muscles=2.2), "Muscles_Doux": dict(t_muscles=0.2),
        "Epaules_Larges": dict(t_epaules=1.6), "Cuisses_Grosses": dict(t_cuisses=1.3),
    }
    # les réglages du corps qui touchent l'entrejambe (cuisses, fesses) recalculent son relief
    for nom, ov in corps.items():
        Q = {**P, **ov}
        ov = dict(ov, fesses=bosses_bas(Q), rho_fn=rho_bas(Q), section_dense=section_bas(Q))
        cles[nom] = ov
    return P, cles
