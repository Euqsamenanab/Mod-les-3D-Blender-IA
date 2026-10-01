"""Cuisson de textures (Cycles) : couleur, masques, occlusion ambiante, normal map.

Chaque cuisson remplace temporairement les matériaux de l'objet par un matériau dédié,
cuit dans une image (nœud Image Texture actif) puis enregistre un PNG 8 bits.
Les cartes de données (normal, AO, masques) sont en espace « Non-Color ».
"""
import os

import bpy


def nouvelle_image(nom, res, couleur=True):
    img = bpy.data.images.new(nom, res, res, alpha=False)
    img.colorspace_settings.name = "sRGB" if couleur else "Non-Color"
    return img


def cuire(ob, img, chemin, type_cuisson, materiau=None, echantillons=1, marge=16):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = echantillons
    b = scene.render.bake
    b.margin = marge
    b.margin_type = "EXTEND"
    b.use_clear = True
    b.normal_space = "TANGENT"
    b.target = "IMAGE_TEXTURES"

    anciens = [s.material for s in ob.material_slots]
    if materiau:
        for s in ob.material_slots:
            s.material = materiau
    noeuds = []
    for m in {s.material for s in ob.material_slots}:
        n = m.node_tree.nodes.new("ShaderNodeTexImage")
        n.image = img
        m.node_tree.nodes.active = n
        noeuds.append((m, n))

    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.view_layer.objects:
        o.select_set(o == ob)
    bpy.ops.object.bake(type=type_cuisson)

    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    img.filepath_raw = chemin
    img.file_format = "PNG"
    img.save()
    for m, n in noeuds:
        m.node_tree.nodes.remove(n)
    for s, m in zip(ob.material_slots, anciens):
        s.material = m
    return chemin


def materiau_emission(nom, couleur_socket_builder):
    """Matériau d'émission dont la couleur est construite par `couleur_socket_builder(nt)`."""
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(couleur_socket_builder(nt), em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m
