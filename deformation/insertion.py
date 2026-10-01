"""Test d'insertion en Geometry Nodes : déformation instantanée, propre et réglable.

Un objet « Test_Insertion » lit le vagin de poche (maillage de base, sans
subdivision) et un jouet, place le jouet dans l'axe du canal, puis déforme les deux.

Modèle de déformation (dans chaque direction radiale autour de l'axe du canal) :
- r_c : rayon du canal au repos (lancer de rayon depuis l'axe sur la poche),
  r_t : rayon du jouet (lancer de rayon depuis l'axe sur le jouet).
- Là où r_t > r_c, poche et jouet se rencontrent au rayon de contact
  r_f = r_c + a (r_t - r_c), avec a = k_jouet / (k_poche + k_jouet) d'après les rigidités.
- La poche se dilate à aire conservée (latex incompressible) :
  rho' = sqrt(rho² + r_f² - r_c²). La paroi du canal va exactement à r_f, la matière
  autour suit, la surface extérieure gonfle un peu, les lèvres s'écartent.
- La dilatation est diffusée le long du maillage (rigidité du latex), sans jamais
  descendre sous le contact exact.
- Au-delà du fond du canal, le jouet pousse le fond (part a) et se tasse (part 1 - a) :
  compression avec renflement dans le canal, et flexion de la partie restée dehors.
"""
import math

from lib.nodes import NodeBuilder, add_socket, new_tree

JEU = 0.0004  # jeu entre la paroi du canal et le jouet (évite les surfaces confondues)

ENTREES = [
    # nom, type, défaut, min, max, sous-type, info-bulle
    ("Poche", "OBJ", None, None, None, None, "Objet vagin de poche (maillage de base, sans subdivision)"),
    ("Jouet", "OBJ", None, None, None, None, "Jouet à insérer (axe Z local, base à z = 0)"),
    ("Insertion", "FLOAT", 0.10, -0.2, 0.5, "DISTANCE", "Profondeur de la pointe du jouet depuis la fente"),
    ("Rigidité poche", "FLOAT", 0.3, 0.0, 1.0, "FACTOR", "0 = latex très souple, 1 = rigide"),
    ("Rigidité jouet", "FLOAT", 1.0, 0.0, 1.0, "FACTOR", "0 = jouet très souple, 1 = rigide"),
    ("Diffusion", "FLOAT", 1.0, 0.0, 4.0, None, "Étalement de la déformation dans le latex"),
    ("Flexion", "FLOAT", 0.6, 0.0, 1.0, "FACTOR", "Part du tassement d'un jouet souple absorbée en flexion"),
    ("Axe canal Z", "FLOAT", 0.0525, None, None, "DISTANCE", "Hauteur de l'axe du canal"),
    ("Fond du canal", "FLOAT", 0.1875, None, None, "DISTANCE", "Profondeur du fond du canal"),
    ("Subdivision", "INT", 1, 0, 3, None, "Niveau de subdivision de la poche"),
    ("Afficher jouet", "BOOL", True, None, None, None, ""),
    ("Vue en coupe", "BOOL", False, None, None, None, "Supprime la moitié x > 0 pour voir le canal"),
]


def arbre_insertion():
    tree = new_tree("Test_Insertion")
    add_socket(tree, "Geometry", "GEO")
    for name, kind, default, lo, hi, sub, tip in ENTREES:
        add_socket(tree, name, kind, default, lo, hi, sub, tip=tip)
    add_socket(tree, "Geometry", "GEO", out=True)

    nb = NodeBuilder(tree)
    gi = nb.node("NodeGroupInput")
    go = nb.node("NodeGroupOutput")
    g = {s.name: gi.outputs[s.name] for s in tree.interface.items_tree
         if s.item_type == "SOCKET" and s.in_out == "INPUT"}
    ins, axe_z, fond = g["Insertion"], g["Axe canal Z"], g["Fond du canal"]

    poche = nb.object_info(g["Poche"])
    jouet0 = nb.object_info(g["Jouet"])

    # ------------------------------------------------------------ grandeurs globales
    _, _, pz = nb.xyz(nb.position())
    long_jouet = nb.stat(jouet0, pz)
    _, py, _ = nb.xyz(nb.position())
    arriere = nb.stat(poche, py)

    def k(r):
        return nb.add(0.02, nb.mul(50.0, nb.pow(r, 3.0)))

    kp, kj = k(g["Rigidité poche"]), k(g["Rigidité jouet"])
    a = nb.div(kj, nb.add(kp, kj))                         # part de la déformation prise par la poche
    p = nb.max(0.0, nb.sub(ins, fond))                     # dépassement du fond du canal
    p_poche = nb.mul(a, p)
    p_jouet = nb.sub(p, p_poche)
    libre = nb.max(0.0, nb.sub(long_jouet, ins))           # longueur du jouet restée dehors
    p_flex = nb.mul(nb.mul(g["Flexion"], p_jouet), nb.gt(libre, 0.005))
    p_comp = nb.sub(p_jouet, p_flex)

    # ------------------------------------------------------------ jouet placé dans l'axe
    tr = nb.node("GeometryNodeTransform")
    nb.set(tr.inputs["Geometry"], jouet0)
    nb.set(tr.inputs["Translation"], nb.vec(0.0, nb.sub(ins, long_jouet), axe_z))
    tr.inputs["Rotation"].default_value = (-math.pi / 2, 0.0, 0.0)
    jouet1 = tr.outputs["Geometry"]

    # tassement axial, renflement dans le canal, flexion de la partie libre
    x, y, z = nb.xyz(nb.position())
    f_libre = nb.clamp01(nb.div(nb.sub(y, nb.sub(ins, long_jouet)), nb.max(libre, 1e-4)))
    ins_s = nb.max(ins, 1e-3)
    f_ins = nb.clamp01(nb.div(y, ins_s))
    decal = nb.mul(-1.0, nb.add(nb.mul(p_flex, f_libre), nb.mul(p_comp, f_ins)))
    fleche = nb.mul(nb.mul(-0.64, nb.sqrt(nb.mul(libre, p_flex))), nb.sin(nb.mul(f_libre, math.pi)))
    eps = nb.div(p_comp, ins_s)
    gonfle = nb.div(1.0, nb.sqrt(nb.max(nb.sub(1.0, eps), 0.3)))
    gm = nb.lerp(1.0, gonfle, nb.gt(y, 0.0))
    jouet2 = nb.set_position(jouet1, nb.vec(nb.mul(x, gm), nb.add(y, decal),
                                            nb.add(nb.add(axe_z, nb.mul(nb.sub(z, axe_z), gm)), fleche)))

    # ------------------------------------------------------------ outils radiaux
    def radial():
        P = nb.position()
        _, Py, _ = nb.xyz(P)
        C = nb.vec(0.0, Py, axe_z)
        Dv = nb.vmath("SUBTRACT", P, C)
        rho = nb.vmath("LENGTH", Dv)
        d = nb.switch("VECTOR", nb.gt(rho, 1e-6), (0.0, 0.0, 1.0), nb.vmath("NORMALIZE", Dv))
        return P, Py, C, rho, d

    def canal_au_repos(cible, C, d):
        hit, n, dist = nb.raycast(cible, C, d, 0.25)
        dans_latex = nb.mul(hit, nb.gt(nb.vmath("DOT_PRODUCT", d, n), 0.0))
        rc = nb.switch("FLOAT", hit, 1.0, dist)
        return hit, dans_latex, rc

    def rayon_jouet(C, d):
        hit, n, dist = nb.raycast(jouet2, C, d, 0.25)
        dedans = nb.mul(hit, nb.gt(nb.vmath("DOT_PRODUCT", d, n), 0.0))
        return nb.mul(dist, dedans)

    def dilatation(cible):
        _, _, C, _, d = radial()
        _, dans_latex, rc = canal_au_repos(cible, C, d)
        rt = rayon_jouet(C, d)
        contact = nb.mul(nb.gt(rt, rc), nb.sub(1.0, dans_latex))
        rf = nb.add(nb.add(rc, nb.mul(a, nb.sub(rt, rc))), JEU)
        return nb.mul(contact, nb.sub(nb.mul(rf, rf), nb.mul(rc, rc)))

    def store(geo, name, value):
        n = nb.node("GeometryNodeStoreNamedAttribute", data_type="FLOAT", domain="POINT")
        nb.set(n.inputs["Geometry"], geo)
        n.inputs["Name"].default_value = name
        nb.set(n.inputs["Value"], value)
        return n.outputs["Geometry"]

    # ------------------------------------------------------------ poche : dilatation diffusée
    poche_d = store(poche, "dilatation", dilatation(poche))
    blur = nb.node("GeometryNodeBlurAttribute", data_type="FLOAT")
    nb.set(blur.inputs["Value"], nb.named("dilatation"))
    nb.set(blur.inputs["Iterations"], nb.mul(nb.add(20.0, nb.mul(150.0, g["Rigidité poche"])), g["Diffusion"]))
    nb.set(blur.inputs["Weight"], 1.0)
    poche_f = store(poche_d, "dilatation", nb.max(nb.named("dilatation"), blur.outputs["Value"]))

    subdiv = nb.node("GeometryNodeSubdivisionSurface")
    nb.set(subdiv.inputs["Mesh"], poche_f)
    nb.set(subdiv.inputs["Level"], g["Subdivision"])
    poche_s = subdiv.outputs["Mesh"]

    P, Py, C, rho, d = radial()
    delta = nb.max(dilatation(poche_s), nb.named("dilatation"))
    rho_n = nb.sqrt(nb.add(nb.mul(rho, rho), delta))
    w_ax = nb.mul(nb.mul(nb.smoothstep(nb.sub(fond, 0.03), fond, Py),
                         nb.sub(1.0, nb.clamp01(nb.div(nb.sub(Py, fond), nb.max(nb.sub(arriere, fond), 0.01))))),
                  nb.exp(nb.mul(-1.0, nb.pow(nb.div(rho, 0.035), 2.0))))
    pos_poche = nb.vmath("ADD", nb.vmath("ADD", C, nb.vmath("SCALE", d, scale=rho_n)),
                         nb.vec(0.0, nb.mul(p_poche, w_ax), 0.0))
    poche_def = nb.set_position(poche_s, pos_poche)

    # ------------------------------------------------------------ jouet : compression radiale
    V, _, Cj, rho_j, dj = radial()
    hit, dans_latex, rc = canal_au_repos(poche_s, Cj, dj)
    contact = nb.mul(nb.mul(hit, nb.gt(rho_j, rc)), nb.sub(1.0, dans_latex))
    rf = nb.add(rc, nb.mul(a, nb.sub(rho_j, rc)))
    cible = nb.vmath("ADD", Cj, nb.vmath("SCALE", dj, scale=rf))
    pos_jouet = nb.vmath("ADD", V, nb.vmath("SCALE", nb.vmath("SUBTRACT", cible, V), scale=contact))
    jouet_def = nb.set_position(jouet2, pos_jouet)

    join = nb.node("GeometryNodeJoinGeometry")
    nb.set(join.inputs[0], nb.switch("GEOMETRY", g["Afficher jouet"], None, jouet_def))
    nb.links.new(poche_def, join.inputs[0])

    # vue en coupe : moitié x > 0 supprimée, attribut « coupe » lu par le matériau
    cx, _, _ = nb.xyz(nb.position())
    suppr = nb.node("GeometryNodeDeleteGeometry", domain="POINT")
    nb.set(suppr.inputs["Geometry"], join.outputs[0])
    nb.set(suppr.inputs["Selection"], nb.gt(cx, 0.0))
    coupe = store(suppr.outputs["Geometry"], "coupe", 1.0)
    nb.set(go.inputs["Geometry"], nb.switch("GEOMETRY", g["Vue en coupe"], join.outputs[0], coupe))
    return tree
