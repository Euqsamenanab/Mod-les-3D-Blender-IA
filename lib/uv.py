"""UV : coutures, dépliage, densité par îlot, empaquetage, planche de contrôle."""
import bmesh
import bpy
import numpy as np


def marquer_coutures(ob, aretes):
    """Marque comme coutures les arêtes données par paires d'indices de sommets."""
    cles = {tuple(sorted(a)) for a in aretes}
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for e in bm.edges:
        e.seam = tuple(sorted((e.verts[0].index, e.verts[1].index))) in cles
    bm.to_mesh(ob.data)
    bm.free()


def _mode(ob, mode):
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.view_layer.objects:
        o.select_set(o == ob)
    bpy.ops.object.mode_set(mode=mode)


def deplier(ob, echelles=None, marge=0.003, methode="ANGLE_BASED"):
    """Déplie selon les coutures, égalise la densité, applique des facteurs d'échelle par
    îlot (dict indice_de_face -> facteur), puis empaquette dans [0, 1]²."""
    if not ob.data.uv_layers:
        ob.data.uv_layers.new(name="UVMap")
    _mode(ob, "EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method=methode, margin=marge)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")

    if echelles:
        me = ob.data
        uv = me.uv_layers.active.data
        # chaque îlot est agrandi autour de son centre (les faces d'un îlot partagent le facteur)
        par_facteur = {}
        for fi, fac in echelles.items():
            par_facteur.setdefault(fac, []).append(fi)
        for fac, faces in par_facteur.items():
            boucles = [li for fi in faces for li in me.polygons[fi].loop_indices]
            co = np.array([uv[li].uv[:] for li in boucles])
            centre = co.mean(axis=0)
            co = centre + (co - centre) * fac
            for li, c in zip(boucles, co):
                uv[li].uv = c

    _mode(ob, "EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin=marge)
    bpy.ops.object.mode_set(mode="OBJECT")


def planche_uv(ob, chemin, taille=2048, couleurs=None):
    """Dessine la disposition UV (contours des faces), colorée par zone si `couleurs`
    (liste de couleurs RGB par face) est fournie."""
    from PIL import Image, ImageDraw

    me = ob.data
    uv = np.empty(len(me.loops) * 2)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    im = Image.new("RGB", (taille, taille), (24, 24, 28))
    d = ImageDraw.Draw(im)
    for p in me.polygons:
        pts = [(uv[li, 0] * taille, (1 - uv[li, 1]) * taille) for li in p.loop_indices]
        fill = couleurs[p.index] if couleurs else (70, 70, 80)
        d.polygon(pts, fill=fill, outline=(200, 200, 210))
    im.save(chemin)
    return chemin


def materiau_damier(nom="Damier_UV", resolution=2048):
    img = bpy.data.images.new(f"{nom}_img", resolution, resolution)
    img.generated_type = "COLOR_GRID"
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6
    return m


def statistiques(ob):
    """Taux d'occupation de l'espace UV et rapport densité max/min entre faces (hors vulve)."""
    me = ob.data
    uv = np.empty(len(me.loops) * 2)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    aire_uv = 0.0
    for p in me.polygons:
        pts = uv[list(p.loop_indices)]
        x, y = pts[:, 0], pts[:, 1]
        aire_uv += 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    return {"occupation_uv": round(aire_uv, 3)}
