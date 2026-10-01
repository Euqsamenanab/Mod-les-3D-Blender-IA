"""Construction d'arbres Geometry Nodes depuis Python, avec une écriture proche des formules.

    nb = NodeBuilder(tree)
    r = nb.sqrt(nb.max(0.0, nb.sub(1.0, nb.mul(x, x))))

Chaque fonction accepte des sockets ou des constantes et renvoie le socket de sortie.
"""
import math

import bpy

SOCKET_TYPES = {
    "GEO": "NodeSocketGeometry",
    "FLOAT": "NodeSocketFloat",
    "INT": "NodeSocketInt",
    "BOOL": "NodeSocketBool",
    "VEC": "NodeSocketVector",
    "OBJ": "NodeSocketObject",
    "MAT": "NodeSocketMaterial",
}


def new_tree(name):
    tree = bpy.data.node_groups.new(name, "GeometryNodeTree")
    tree.is_modifier = True
    return tree


def add_socket(tree, name, kind, default=None, lo=None, hi=None, subtype=None, out=False, tip=""):
    s = tree.interface.new_socket(name, in_out="OUTPUT" if out else "INPUT", socket_type=SOCKET_TYPES[kind])
    if subtype:
        s.subtype = subtype
    if default is not None:
        s.default_value = default
    if lo is not None:
        s.min_value = lo
    if hi is not None:
        s.max_value = hi
    if tip:
        s.description = tip
    return s


class NodeBuilder:
    def __init__(self, tree):
        self.tree = tree
        self.nodes = tree.nodes
        self.links = tree.links
        self.count = 0

    # ------------------------------------------------------------------ bas niveau
    def node(self, idname, **props):
        n = self.nodes.new(idname)
        for k, v in props.items():
            setattr(n, k, v)
        n.location = (220 * (self.count // 30), -170 * (self.count % 30))
        self.count += 1
        return n

    def set(self, socket, value):
        if value is None:
            return
        if isinstance(value, bpy.types.NodeSocket):
            self.links.new(value, socket)
        else:
            socket.default_value = value

    def connect(self, node, **inputs):
        for name, value in inputs.items():
            self.set(node.inputs[name.replace("_", " ")], value)
        return node

    # ------------------------------------------------------------------ maths scalaires
    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            self.set(n.inputs[i], v)
        return n.outputs[0]

    def add(self, a, b):
        return self.math("ADD", a, b)

    def sub(self, a, b):
        return self.math("SUBTRACT", a, b)

    def mul(self, a, b):
        return self.math("MULTIPLY", a, b)

    def div(self, a, b):
        return self.math("DIVIDE", a, b)

    def max(self, a, b):
        return self.math("MAXIMUM", a, b)

    def min(self, a, b):
        return self.math("MINIMUM", a, b)

    def smax(self, a, b, k):
        return self.math("SMOOTH_MAX", a, b, k)

    def sqrt(self, a):
        return self.math("SQRT", a)

    def pow(self, a, b):
        return self.math("POWER", a, b)

    def sin(self, a):
        return self.math("SINE", a)

    def cos(self, a):
        return self.math("COSINE", a)

    def exp(self, a):
        return self.math("EXPONENT", a)

    def gt(self, a, b):
        return self.math("GREATER_THAN", a, b)

    def lt(self, a, b):
        return self.math("LESS_THAN", a, b)

    def clamp01(self, a):
        return self.math("ADD", a, 0.0, clamp=True)

    def lerp(self, a, b, t):
        return self.add(a, self.mul(self.sub(b, a), t))

    def smoothstep(self, edge0, edge1, x):
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP", clamp=True)
        self.set(n.inputs["Value"], x)
        self.set(n.inputs["From Min"], edge0)
        self.set(n.inputs["From Max"], edge1)
        return n.outputs["Result"]

    def ellipsoid(self, z, center, radius, half_length):
        """Rayon d'un ellipsoïde de révolution à la hauteur z (0 en dehors)."""
        q = self.div(self.sub(z, center), half_length)
        return self.mul(radius, self.sqrt(self.max(0.0, self.sub(1.0, self.mul(q, q)))))

    def between(self, x, lo, hi):
        """1 si lo <= x <= hi, sinon 0."""
        return self.mul(self.math("GREATER_THAN", x, self.sub(lo, 1e-7)), self.math("LESS_THAN", x, self.add(hi, 1e-7)))

    # ------------------------------------------------------------------ vecteurs
    def vmath(self, op, a, b=None, scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        if scale is not None:
            self.set(n.inputs[3], scale)
        if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE"):
            return n.outputs["Value"]
        return n.outputs["Vector"]

    def vec(self, x, y, z):
        n = self.node("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self.set(n.inputs[i], v)
        return n.outputs[0]

    def xyz(self, v):
        n = self.node("ShaderNodeSeparateXYZ")
        self.set(n.inputs[0], v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def position(self):
        return self.node("GeometryNodeInputPosition").outputs[0]

    def index(self):
        return self.node("GeometryNodeInputIndex").outputs[0]

    def named(self, name, data_type="FLOAT"):
        n = self.node("GeometryNodeInputNamedAttribute", data_type=data_type)
        n.inputs["Name"].default_value = name
        return n.outputs["Attribute"]

    def switch(self, kind, cond, false, true):
        n = self.node("GeometryNodeSwitch", input_type=kind)
        self.set(n.inputs["Switch"], cond)
        self.set(n.inputs["False"], false)
        self.set(n.inputs["True"], true)
        return n.outputs["Output"]

    def set_position(self, geo, position=None, offset=None, selection=None):
        n = self.node("GeometryNodeSetPosition")
        self.set(n.inputs["Geometry"], geo)
        self.set(n.inputs["Position"], position)
        self.set(n.inputs["Offset"], offset)
        self.set(n.inputs["Selection"], selection)
        return n.outputs["Geometry"]

    def stat(self, geo, value, out="Max"):
        n = self.node("GeometryNodeAttributeStatistic", data_type="FLOAT", domain="POINT")
        self.set(n.inputs["Geometry"], geo)
        self.set(n.inputs["Attribute"], value)
        return n.outputs[out]

    def raycast(self, target, source, direction, length=0.2):
        n = self.node("GeometryNodeRaycast")
        self.set(n.inputs["Target Geometry"], target)
        self.set(n.inputs["Source Position"], source)
        self.set(n.inputs["Ray Direction"], direction)
        self.set(n.inputs["Ray Length"], length)
        return n.outputs["Is Hit"], n.outputs["Hit Normal"], n.outputs["Hit Distance"]

    def object_info(self, obj_socket, space="ORIGINAL"):
        n = self.node("GeometryNodeObjectInfo", transform_space=space)
        self.set(n.inputs["Object"], obj_socket)
        return n.outputs["Geometry"]


PI = math.pi
