"""Simulation physique (Cloth) : poche en latex tenue par l'arrière, jouet qui s'insère.

- Poche simulée sur un maillage allégé (proxy) en Cloth : ressorts de surface
  (tension, compression, cisaillement, flexion), ressorts internes qui relient les
  parois à travers la matière (comportement de solide), pression à volume cible
  (latex incompressible). Pas de gravité : la poche est tenue en main par l'arrière
  (groupe de sommets « Maintien »).
- Jouet rigide : modificateur Collision (frottement réglable), animé le long de l'axe.
- Jouet souple : Cloth avec ressorts internes, base tenue (groupe « Maintien »), qui
  plie et se tasse au contact ; il entre en collision avec la poche (Collision).
- La rigidité se règle par des propriétés de l'objet « Reglages_Physique » reliées
  par drivers aux réglages Cloth.
"""
import bmesh
import bpy
import numpy as np


def volume(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume(signed=False)
    bm.free()
    return v


def groupe(ob, name, weights):
    vg = ob.vertex_groups.new(name=name)
    for i, w in enumerate(weights):
        if w > 0:
            vg.add([i], float(w), "REPLACE")
    return vg


def cloth_latex(ob, pin_group, controle, prefixe, masse_totale, longueur_ressorts):
    """Cloth « solide » : ressorts de surface + internes + pression, rigidité pilotée par driver."""
    mod = ob.modifiers.new("Cloth", "CLOTH")
    s = mod.settings
    s.quality = 16
    s.mass = masse_totale / len(ob.data.vertices)
    s.air_damping = 2.0
    s.tension_damping = s.compression_damping = s.shear_damping = 5.0
    s.bending_model = "ANGULAR"
    s.use_internal_springs = True
    s.internal_spring_max_length = longueur_ressorts
    s.internal_spring_max_diversion = 0.6
    s.internal_spring_normal_check = True
    s.use_dynamic_mesh = True   # les ressorts suivent la forme cible : la simulation ajoute la dynamique
    s.use_pressure = False
    s.target_volume = volume(ob)
    s.vertex_group_mass = pin_group
    s.pin_stiffness = 10.0
    s.effector_weights.gravity = 0.0
    c = mod.collision_settings
    c.collision_quality = 5
    c.distance_min = 0.0008
    c.use_collision = True
    c.use_self_collision = False

    # rigidité : k = base * (0.05 + 4 r²), r = propriété « <prefixe> » du contrôleur (0 à 1)
    for attr, base in (("tension_stiffness", 15.0), ("compression_stiffness", 15.0), ("shear_stiffness", 8.0),
                       ("bending_stiffness", 0.5), ("internal_tension_stiffness", 15.0),
                       ("internal_compression_stiffness", 15.0), ("pin_stiffness", 10.0)):
        fc = s.driver_add(attr)
        drv = fc.driver
        drv.type = "SCRIPTED"
        var = drv.variables.new()
        var.name = "r"
        var.targets[0].id = controle
        var.targets[0].data_path = f'["{prefixe}"]'
        drv.expression = f"{base} * (0.05 + 4 * r * r)"
    return mod


def collision(ob, friction=1.5, epaisseur=0.0008):
    mod = ob.modifiers.new("Collision", "COLLISION")
    ob.collision.thickness_outer = epaisseur
    ob.collision.cloth_friction = friction
    ob.collision.damping = 0.0
    return mod


def deplacer_avant(ob, nom_mod, avant):
    """Place le modificateur `nom_mod` juste avant `avant` dans la pile."""
    mods = ob.modifiers
    mods.move(mods.find(nom_mod), mods.find(avant))


def poids_maintien_poche(verts, axe_z, souple=0.12):
    """Rappel vers la forme de repos (« mémoire » du latex) :
    faible dans le canal, le vestibule et les lèvres (ils cèdent au jouet et reviennent),
    fort sur la surface extérieure tenue en main (sauf la face avant, plus libre)."""
    y = verts[:, 1]
    rho = np.hypot(verts[:, 0], verts[:, 2] - axe_z)
    exterieur = np.clip((rho - 0.030) / 0.015, 0.0, 1.0)          # 0 près du canal -> 1 en surface
    prise = np.clip((y - 0.02) / 0.04, 0.0, 1.0)                    # la main tient à partir de 2 cm
    fond = np.clip((y - 0.20) / 0.02, 0.0, 1.0)
    w = souple + (1.0 - souple) * np.maximum(exterieur * prise, fond)
    return w
