"""Modificateur « Vue en coupe » réutilisable : supprime la moitié x > 0 (repère de l'objet)
et pose l'attribut « coupe », que le matériau latex rend comme une face de coupe sombre."""
from lib.nodes import NodeBuilder, add_socket, new_tree

NOM = "Vue_en_coupe"


def arbre_coupe():
    import bpy

    tree = bpy.data.node_groups.get(NOM)
    if tree:
        return tree
    tree = new_tree(NOM)
    add_socket(tree, "Geometry", "GEO")
    add_socket(tree, "Vue en coupe", "BOOL", False)
    add_socket(tree, "Geometry", "GEO", out=True)
    nb = NodeBuilder(tree)
    gi = nb.node("NodeGroupInput")
    go = nb.node("NodeGroupOutput")
    x, _, _ = nb.xyz(nb.position())
    suppr = nb.node("GeometryNodeDeleteGeometry", domain="POINT")
    nb.set(suppr.inputs["Geometry"], gi.outputs["Geometry"])
    nb.set(suppr.inputs["Selection"], nb.gt(x, 0.0))
    store = nb.node("GeometryNodeStoreNamedAttribute", data_type="FLOAT", domain="POINT")
    nb.set(store.inputs["Geometry"], suppr.outputs["Geometry"])
    store.inputs["Name"].default_value = "coupe"
    store.inputs["Value"].default_value = 1.0
    nb.set(go.inputs["Geometry"], nb.switch("GEOMETRY", gi.outputs["Vue en coupe"], gi.outputs["Geometry"],
                                            store.outputs["Geometry"]))
    return tree


def ajouter(ob, actif=False):
    mod = ob.modifiers.new(NOM, "NODES")
    mod.node_group = arbre_coupe()
    sid = next(s.identifier for s in mod.node_group.interface.items_tree
               if s.item_type == "SOCKET" and s.in_out == "INPUT" and s.name == "Vue en coupe")
    mod[sid] = actif
    return mod


def regler(ob, actif):
    mod = ob.modifiers[NOM]
    sid = next(s.identifier for s in mod.node_group.interface.items_tree
               if s.item_type == "SOCKET" and s.in_out == "INPUT" and s.name == "Vue en coupe")
    mod[sid] = actif
    ob.data.update()
