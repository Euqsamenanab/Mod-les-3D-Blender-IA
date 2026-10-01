"""Matériau latex réglable.

Tous les réglages sont des entrées du groupe de nœuds « Latex_Reglages ».
Dans Blender : Propriétés > Matériau > Surface, les curseurs apparaissent
directement. Chaque objet a son propre matériau, donc ses propres réglages.

Les zones teintées viennent de l'attribut de couleur « Masques » du maillage :
R = vulve (et anus), G = intérieur, B = aréoles (torse).

Vue en coupe : quand la géométrie porte l'attribut « coupe » (posé par le test
d'insertion), les faces vues de dos (l'intérieur exposé par la coupe) sont rendues
dans une teinte sombre, comme une face de coupe.
"""
import bpy

GROUP_NAME = "Latex_Reglages"

INPUTS = [
    # nom, type, défaut, min, max
    ("Couleur", "NodeSocketColor", (0.95, 0.86, 0.80, 1.0), None, None),
    ("Transparence", "NodeSocketFloat", 0.9, 0.0, 1.0),
    ("Reflet", "NodeSocketFloat", 0.8, 0.0, 1.0),
    ("Couleur Vulve", "NodeSocketColor", (0.10, 0.02, 0.03, 1.0), None, None),
    ("Teinte Vulve", "NodeSocketFloat", 0.85, 0.0, 1.0),
    ("Couleur Interieur", "NodeSocketColor", (0.75, 0.18, 0.25, 1.0), None, None),
    ("Teinte Interieur", "NodeSocketFloat", 0.8, 0.0, 1.0),
    ("Couleur Areoles", "NodeSocketColor", (0.55, 0.24, 0.26, 1.0), None, None),
    ("Teinte Areoles", "NodeSocketFloat", 0.7, 0.0, 1.0),
]


def latex_group():
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(GROUP_NAME, "ShaderNodeTree")
    for name, stype, default, lo, hi in INPUTS:
        s = ng.interface.new_socket(name, in_out="INPUT", socket_type=stype)
        s.default_value = default
        if lo is not None:
            s.min_value, s.max_value = lo, hi
            s.subtype = "FACTOR"
    ng.interface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")

    N, L = ng.nodes, ng.links
    gi = N.new("NodeGroupInput")
    go = N.new("NodeGroupOutput")
    gi.location, go.location = (-900, 0), (500, 0)

    attr = N.new("ShaderNodeAttribute")
    attr.attribute_name = "Masques"
    attr.location = (-900, 300)
    sep = N.new("ShaderNodeSeparateColor")
    sep.location = (-700, 300)
    L.new(attr.outputs["Color"], sep.inputs["Color"])

    def mul(a, b, loc):
        m = N.new("ShaderNodeMath")
        m.operation = "MULTIPLY"
        m.use_clamp = True
        m.location = loc
        L.new(a, m.inputs[0])
        L.new(b, m.inputs[1])
        return m.outputs[0]

    def mix(fac, a, b, loc):
        m = N.new("ShaderNodeMix")
        m.data_type = "RGBA"
        m.location = loc
        L.new(fac, m.inputs[0])
        L.new(a, m.inputs[6])
        L.new(b, m.inputs[7])
        return m.outputs[2]

    f_vulve = mul(sep.outputs["Red"], gi.outputs["Teinte Vulve"], (-500, 250))
    f_int = mul(sep.outputs["Green"], gi.outputs["Teinte Interieur"], (-500, 100))
    f_are = mul(sep.outputs["Blue"], gi.outputs["Teinte Areoles"], (-500, 400))
    c0 = mix(f_are, gi.outputs["Couleur"], gi.outputs["Couleur Areoles"], (-400, 400))
    c1 = mix(f_vulve, c0, gi.outputs["Couleur Vulve"], (-300, 250))
    base = mix(f_int, c1, gi.outputs["Couleur Interieur"], (-100, 200))

    # Reflet 0 -> mat, 1 -> très brillant
    rough = N.new("ShaderNodeMapRange")
    rough.location = (-300, -100)
    rough.inputs["To Min"].default_value = 0.55
    rough.inputs["To Max"].default_value = 0.02
    L.new(gi.outputs["Reflet"], rough.inputs["Value"])
    coat = mul(gi.outputs["Reflet"], gi.outputs["Reflet"], (-300, -250))

    # un peu de diffusion sous-surface quand le latex devient opaque
    inv = N.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    inv.location = (-300, -400)
    L.new(gi.outputs["Transparence"], inv.inputs[1])
    sss = N.new("ShaderNodeMath")
    sss.operation = "MULTIPLY"
    sss.inputs[1].default_value = 0.25
    sss.location = (-100, -400)
    L.new(inv.outputs[0], sss.inputs[0])

    p = N.new("ShaderNodeBsdfPrincipled")
    p.location = (150, 0)
    p.inputs["IOR"].default_value = 1.5
    p.inputs["Coat Roughness"].default_value = 0.05
    p.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.35)
    p.inputs["Subsurface Scale"].default_value = 0.004
    L.new(base, p.inputs["Base Color"])
    L.new(gi.outputs["Transparence"], p.inputs["Transmission Weight"])
    L.new(rough.outputs["Result"], p.inputs["Roughness"])
    L.new(coat, p.inputs["Coat Weight"])
    L.new(sss.outputs[0], p.inputs["Subsurface Weight"])

    # vue en coupe : faces de dos assombries quand l'attribut « coupe » vaut 1
    coupe = N.new("ShaderNodeAttribute")
    coupe.attribute_name = "coupe"
    coupe.location = (150, -450)
    geo = N.new("ShaderNodeNewGeometry")
    geo.location = (150, -600)
    f_coupe = mul(coupe.outputs["Fac"], geo.outputs["Backfacing"], (350, -500))
    sombre = N.new("ShaderNodeMix")
    sombre.data_type = "RGBA"
    sombre.blend_type = "MULTIPLY"
    sombre.inputs[0].default_value = 1.0
    sombre.inputs[7].default_value = (0.10, 0.10, 0.11, 1.0)
    sombre.location = (150, -750)
    L.new(base, sombre.inputs[6])
    face = N.new("ShaderNodeBsdfDiffuse")
    face.location = (350, -700)
    L.new(sombre.outputs[2], face.inputs["Color"])
    mix = N.new("ShaderNodeMixShader")
    mix.location = (550, -200)
    L.new(f_coupe, mix.inputs["Fac"])
    L.new(p.outputs["BSDF"], mix.inputs[1])
    L.new(face.outputs["BSDF"], mix.inputs[2])
    L.new(mix.outputs["Shader"], go.inputs["Shader"])
    go.location = (750, 0)
    return ng


def latex_material(name, **settings):
    """Crée un matériau latex ; `settings` surcharge les valeurs par défaut (noms avec _ ou espaces)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    g = nt.nodes.new("ShaderNodeGroup")
    g.node_tree = latex_group()
    g.label = "Réglages Latex"
    g.width = 240
    nt.links.new(g.outputs["Shader"], out.inputs["Surface"])
    for key, val in settings.items():
        g.inputs[key.replace("_", " ")].default_value = val
    return m


def latex_controls(mat):
    """Nœud de réglages d'un matériau latex (pour modifier les curseurs par script)."""
    return next(n for n in mat.node_tree.nodes if n.type == "GROUP")


def simple_material(name, color, rough=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1.0)
    p.inputs["Roughness"].default_value = rough
    return m
