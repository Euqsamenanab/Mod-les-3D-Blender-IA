"""Variantes du vagin de poche : formes extérieures, styles de lèvres, anus.

Une variante = PARAMS du modèle d'origine + une forme extérieure + une entrée (style de
lèvres, anus, ou les deux), avec ses shape keys et les réglages de son matériau.
Toutes les combinaisons sont possibles avec `parametres(forme, levres, anus)`.
"""
from poche_canine.sleeve import CANAL_VARIANTS, PARAMS

# --------------------------------------------------------------------------- formes extérieures
FORMES = {
    "cylindre": {},
    # œuf couché : face avant en dôme, plus large à l'avant, arrière effilé
    "oeuf": dict(A=0.062, B=0.068, L=0.235, Df=0.052, m=2.0, rho_rim=0.80, corner_n=9,
                 face_s=(0.06, 0.15, 0.27, 0.42, 0.60, 0.80, 1.0),
                 Db=0.175, m_back=2.0, back_n=17, back_tmax=0.86, d_entree=None),
    # sablier : taille resserrée au milieu pour la prise en main, bouts renflés
    "sablier": dict(A=0.058, B=0.068, L=0.24, m=2.4, waist=0.17, waist_d=0.135, waist_s=0.05, d_entree=None),
    # mini fessier : deux fesses rondes et un sillon, vulve en bas et anus au-dessus
    "fessier": dict(A=0.088, B=0.088, L=0.20, Df=0.030, Db=0.030, m=2.5, rho_rim=0.92,
                    face_s=(0.07, 0.15, 0.24, 0.34, 0.45, 0.57, 0.70, 0.84, 1.0),
                    fesses=dict(cu=0.047, cv=0.014, ru=0.056, rv=0.076, h=0.050, k=0.012, fondu=0.70),
                    d_entree=None),
}

# --------------------------------------------------------------------------- styles de lèvres
LEVRES = {
    "classique": {},
    # bulbe très saillant et rond ; la fente en Y profonde découpe trois coussinets
    "bulbe": dict(
        vulva_ctrl=((0.0, -0.054), (0.021, -0.042), (0.036, -0.018), (0.042, 0.010), (0.036, 0.035),
                    (0.0, 0.047), (-0.036, 0.035), (-0.042, 0.010), (-0.036, -0.018), (-0.021, -0.042)),
        slit_vS=-0.034, slit_vJ=0.003, slit_ua=0.0165, slit_va=0.019,
        lip_h=1.05, lip_dome=0.42,
        lip_profile=((0.0, 0.0), (0.0, 0.30), (0.025, 0.62), (0.09, 0.86), (0.21, 0.98), (0.40, 1.03),
                     (0.62, 1.0), (0.84, 0.86), (1.02, 0.52), (1.05, 0.20), (1.0, 0.0)),
    ),
    # cœur charnu large : grandes lèvres épaisses, Y entrouvert au centre
    "coeur": dict(
        vulva_ctrl=((0.0, -0.058), (0.019, -0.042), (0.038, -0.013), (0.049, 0.017), (0.036, 0.049),
                    (0.0, 0.036), (-0.036, 0.049), (-0.049, 0.017), (-0.038, -0.013), (-0.019, -0.042)),
        slit_vS=-0.036, slit_vJ=0.006, slit_ua=0.012, slit_va=0.0145,
        slit_open=0.0028, slit_open_span=0.0055,
        lip_h=0.92, lip_dome=0.25,
        lip_profile=((0.0, 0.0), (0.0, 0.24), (0.025, 0.56), (0.09, 0.83), (0.19, 0.97), (0.33, 1.03),
                     (0.58, 1.0), (0.86, 0.80), (1.07, 0.42), (1.0, 0.0)),
    ),
    # petite fente discrète : vulve ovale plus petite et plate, fente entrouverte, petit pli en bas
    "fente": dict(
        vulva_ctrl=((0.0, -0.044), (0.013, -0.036), (0.021, -0.016), (0.023, 0.004), (0.019, 0.022),
                    (0.0, 0.030), (-0.019, 0.022), (-0.023, 0.004), (-0.021, -0.016), (-0.013, -0.036)),
        vulva_scale=0.80,
        slit_vS=-0.026, slit_vJ=0.010, slit_ua=0.0050, slit_va=0.0060, slit_lens=0.0011,
        lip_h=0.55, lip_dome=0.20,
        fold_amp=0.0010, fold_count=3, fold_span=8,
    ),
}

# --------------------------------------------------------------------------- double entrée
DOUBLE = dict(entree="double", anus_N=80, vulve_v=-0.036, milieu_v=0.004, milieu_w=0.030,
              vulve_bas=-0.074, anus_centre_v=0.036, anus_haut=0.067,
              face_s_regions=(0.22, 0.48, 0.75, 1.0))
ANUS_SEUL = dict(entree="anus", anus_v=-0.006, anus_R=0.024, anus_h=0.0135)

# --------------------------------------------------------------------------- shape keys
CLES_CANAL = {
    "Anneau_Serre": dict(ring_dr=-0.002),
    "Anneau_Large": dict(ring_dr=0.002),
    "Chambre_Large": dict(chamber_dr=0.005),
    "Chambre_Fine": dict(chamber_dr=-0.004),
    **{f"Canal_{v}": dict(canal_variant=v) for v in CANAL_VARIANTS},
}
CLES_ANUS = {
    "Anus_Plisse": dict(anus_pli=1.0),
    "Anus_Gonfle": "gonfle",
    "Anus_Ouvert": dict(anus_ouvert=1.0),
    "Anus_Anneau_Serre": dict(anus_ring_dr=-0.0015),
    "Anus_Anneau_Large": dict(anus_ring_dr=0.0015),
    "Anus_Chambre_Large": dict(anus_chamber_dr=0.004),
    "Anus_Chambre_Fine": dict(anus_chamber_dr=-0.003),
    **{f"Anus_Canal_{v}": dict(anus_canal_variant=v) for v in CANAL_VARIANTS},
}


def cles_vulve(P, levres):
    """Shape keys de la vulve, relatives à la forme de base de la variante."""
    cles = {
        "Vulve_Grande": dict(vulva_size=1.2),
        "Vulve_Petite": dict(vulva_size=0.8),
        "Levres_Gonflees": dict(lip_h=P["lip_h"] * 1.3),
        "Levres_Fines": dict(lip_h=P["lip_h"] * 0.65),
        "Fente_Branches_Longues": dict(arm_len=1.6),
        "Fente_Branches_Courtes": dict(arm_len=0.45),
        "Pointe_Allongee": dict(tip=1.0),
        "Pointe_Arrondie": dict(tip=-1.0),
    }
    if levres == "coeur":
        cles["Fente_Ouverte"] = dict(slit_open=P["slit_open"] * 1.8)
        cles["Fente_Fermee"] = dict(slit_open=0.0)
    if levres == "fente":
        cles["Fente_Ouverte"] = dict(slit_lens=P["slit_lens"] * 2.5)
        cles["Fente_Fermee"] = dict(slit_lens=0.0)
    return cles


def cles_anus(P):
    return {nom: (dict(anus_h=P["anus_h"] * 1.5, anus_R=P["anus_R"] * 1.1) if ov == "gonfle" else ov)
            for nom, ov in CLES_ANUS.items()}


def parametres(forme="cylindre", levres="classique", anus=None):
    """Paramètres et shape keys d'une combinaison. anus : None, "seul" ou "double"."""
    P = {**PARAMS, **FORMES[forme]}
    cles = {}
    if anus != "seul":
        P.update(LEVRES[levres])
        cles.update(cles_vulve(P, levres))
        cles.update(CLES_CANAL)
    if anus == "double":
        P.update(DOUBLE)
    if anus == "seul":
        P.update(ANUS_SEUL)
    if anus:
        cles.update(cles_anus(P))
    return P, cles


# --------------------------------------------------------------------------- variantes livrées
VARIANTES = {
    "Poche_Oeuf_Bulbe": dict(
        forme="oeuf", levres="bulbe", anus=None,
        description="Œuf, vulve en bulbe à 3 lobes",
        materiau={"Couleur Vulve": (0.035, 0.022, 0.024, 1.0), "Teinte Vulve": 0.95,
                  "Couleur Interieur": (0.70, 0.16, 0.22, 1.0)},
    ),
    "Poche_Sablier_Coeur": dict(
        forme="sablier", levres="coeur", anus=None,
        description="Sablier, vulve en cœur charnu, Y entrouvert",
        materiau={"Couleur Vulve": (0.16, 0.05, 0.06, 1.0), "Teinte Vulve": 0.9,
                  "Couleur Interieur": (0.85, 0.22, 0.30, 1.0)},
    ),
    "Poche_Fessier_Double": dict(
        forme="fessier", levres="fente", anus="double",
        description="Mini fessier, petite fente + anus (deux canaux)",
        materiau={"Couleur Vulve": (0.72, 0.30, 0.32, 1.0), "Teinte Vulve": 0.75,
                  "Couleur Interieur": (0.85, 0.25, 0.32, 1.0)},
    ),
    "Poche_Sablier_Anus": dict(
        forme="sablier", levres=None, anus="seul",
        description="Sablier, anus seul",
        materiau={"Couleur Vulve": (0.62, 0.20, 0.24, 1.0), "Teinte Vulve": 0.8,
                  "Couleur Interieur": (0.80, 0.22, 0.30, 1.0)},
    ),
}
