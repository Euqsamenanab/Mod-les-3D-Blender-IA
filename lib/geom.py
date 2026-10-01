"""Outils géométriques : courbes 2D fermées, ré-échantillonnage, caps en grille de quads.

Tout le maillage est construit par « anneaux » : des boucles fermées de N sommets
qui partagent la même indexation (index 0 en bas, sens anti-horaire). Deux anneaux
consécutifs sont reliés par des quads ; les extrémités sont fermées par une grille.
"""
import math

import numpy as np


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def signed_area(pts):
    p = np.asarray(pts)
    return 0.5 * float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]))


def resample_closed(pts, n, start=None):
    """Ré-échantillonne une polyligne fermée en n points équidistants (abscisse curviligne).

    La sortie est anti-horaire et commence au point le plus proche de `start`.
    """
    p = np.asarray(pts, float)
    if signed_area(p) < 0:
        p = p[::-1]
    if start is not None:
        i0 = int(np.argmin(np.linalg.norm(p - np.asarray(start, float), axis=1)))
        p = np.roll(p, -i0, axis=0)
    closed = np.vstack([p, p[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.linspace(0.0, cum[-1], n, endpoint=False)
    return np.column_stack([np.interp(t, cum, closed[:, 0]), np.interp(t, cum, closed[:, 1])])


def closed_bspline(ctrl, per_seg=200):
    """B-spline cubique uniforme fermée (approximante) -> polyligne dense."""
    c = np.asarray(ctrl, float)
    n = len(c)
    t = np.linspace(0.0, 1.0, per_seg, endpoint=False)[:, None]
    b0 = (1 - t) ** 3 / 6
    b1 = (3 * t**3 - 6 * t**2 + 4) / 6
    b2 = (-3 * t**3 + 3 * t**2 + 3 * t + 1) / 6
    b3 = t**3 / 6
    out = [b0 * c[(i - 1) % n] + b1 * c[i] + b2 * c[(i + 1) % n] + b3 * c[(i + 2) % n] for i in range(n)]
    return np.vstack(out)


def catmull_rom_open(pts, per_seg=60):
    """Courbe Catmull-Rom ouverte passant par tous les points -> polyligne dense."""
    p = np.asarray(pts, float)
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    t = np.linspace(0, 1, per_seg, endpoint=False)[:, None]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t**2
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t**3))
    out.append(p[-2][None])
    return np.vstack(out)


def resample_open(pts, n, metric=(1.0, 1.0)):
    """n points équidistants (abscisse curviligne, axes pondérés par `metric`) sur une polyligne ouverte."""
    p = np.asarray(pts, float)
    seg = np.linalg.norm(np.diff(p, axis=0) * np.asarray(metric), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.linspace(0, cum[-1], n)
    return np.column_stack([np.interp(t, cum, p[:, k]) for k in range(p.shape[1])])


def ellipse(a, b, n, center=(0.0, 0.0)):
    """Ellipse échantillonnée à abscisse curviligne constante, départ en bas, anti-horaire."""
    th = np.linspace(0, 2 * math.pi, 4000, endpoint=False)
    dense = np.column_stack([center[0] + a * np.cos(th), center[1] + b * np.sin(th)])
    return resample_closed(dense, n, start=(center[0], center[1] - b))


def circle(r, n, center=(0.0, 0.0)):
    th = -math.pi / 2 + 2 * math.pi * np.arange(n) / n
    return np.column_stack([center[0] + r * np.cos(th), center[1] + r * np.sin(th)])


def smooth_periodic(values, window=5, passes=2):
    v = np.asarray(values, float)
    for _ in range(passes):
        acc = np.zeros_like(v)
        for s in range(-(window // 2), window // 2 + 1):
            acc += np.roll(v, s)
        v = acc / window
    return v


def grid_cap(ring2d, iters=80):
    """Grille de quads n x n qui ferme une boucle de 4n points.

    ring2d[0] doit être le « coin » à -45° (en bas à droite), sens anti-horaire.
    Retourne (interior (m, 2), faces) ; dans faces, un index >= 0 désigne un point
    de la boucle, un index < 0 désigne l'intérieur (-1 - j).
    """
    ring2d = np.asarray(ring2d, float)
    m = len(ring2d)
    n = m // 4
    assert n * 4 == m, "la boucle doit avoir un multiple de 4 sommets"

    def ring_index(i, j):
        if i == n:
            return j % m
        if j == n:
            return (n + (n - i)) % m
        if i == 0:
            return (2 * n + (n - j)) % m
        return (3 * n + i) % m

    # patch de Coons comme point de départ, puis relaxation laplacienne
    P = np.zeros((n + 1, n + 1, 2))
    for i in range(n + 1):
        for j in range(n + 1):
            if i in (0, n) or j in (0, n):
                P[i, j] = ring2d[ring_index(i, j)]
    for i in range(1, n):
        for j in range(1, n):
            u, v = i / n, j / n
            P[i, j] = ((1 - v) * P[i, 0] + v * P[i, n] + (1 - u) * P[0, j] + u * P[n, j]
                       - ((1 - u) * (1 - v) * P[0, 0] + u * (1 - v) * P[n, 0]
                          + (1 - u) * v * P[0, n] + u * v * P[n, n]))
    for _ in range(iters):
        P[1:n, 1:n] = 0.25 * (P[:n - 1, 1:n] + P[2:, 1:n] + P[1:n, :n - 1] + P[1:n, 2:])

    ref = {}
    interior = []
    for i in range(n + 1):
        for j in range(n + 1):
            if i in (0, n) or j in (0, n):
                ref[i, j] = ring_index(i, j)
            else:
                ref[i, j] = -1 - len(interior)
                interior.append(P[i, j])
    faces = [(ref[i, j], ref[i + 1, j], ref[i + 1, j + 1], ref[i, j + 1])
             for i in range(n) for j in range(n)]
    return np.array(interior).reshape(-1, 2), faces


class RingMesh:
    """Accumule des anneaux 3D (N sommets chacun) et leurs attributs, puis ferme les bouts."""

    def __init__(self, n):
        self.n = n
        self.rings = []      # liste de (N, 3)
        self.attrs = []      # liste de dict nom -> (N,)
        self.tags = []       # étiquette de zone par anneau
        self.extra_verts = []
        self.extra_attrs = []   # un dict nom -> (m,) par cap
        self.cap_faces = []

    def add_ring(self, pts3d, tag, **attrs):
        assert len(pts3d) == self.n
        self.rings.append(np.asarray(pts3d, float))
        self.attrs.append({k: np.broadcast_to(np.asarray(v, float), (self.n,)).copy() for k, v in attrs.items()})
        self.tags.append(tag)

    def cap(self, ring_id, to2d, to3d, quarter_offset, **attrs):
        """Ferme l'anneau `ring_id` avec une grille.

        to2d : (N,3) -> (N,2) projection dans le plan du cap.
        to3d : (m,2) -> (m,3) placement des sommets intérieurs.
        quarter_offset : index de l'anneau qui se trouve à -45° dans ce plan.
        attrs : valeur constante, ou fonction (m,2) -> (m,) des positions 2D intérieures.
        """
        ring = self.rings[ring_id]
        order = np.roll(np.arange(self.n), -quarter_offset)
        interior2d, faces = grid_cap(to2d(ring[order]))
        base = len(self.extra_verts)
        self.extra_verts.extend(to3d(interior2d))
        m = len(interior2d)
        self.extra_attrs.append({k: (np.asarray(v(interior2d), float) if callable(v) else np.full(m, float(v)))
                                 for k, v in attrs.items()} | {"_m": m})
        self.cap_faces.append((ring_id, order, base, faces))

    def build(self, ferme=False):
        """ferme : relie aussi le dernier anneau au premier (tube refermé en tore, sans cap)."""
        n = self.n
        R = len(self.rings)
        verts = np.vstack(self.rings + ([np.asarray(self.extra_verts)] if self.extra_verts else []))
        faces = []
        for r in range(R if ferme else R - 1):
            a, b = r * n, ((r + 1) % R) * n
            for k in range(n):
                k2 = (k + 1) % n
                faces.append((a + k, a + k2, b + k2, b + k))
        offset = R * n
        for ring_id, order, base, cf in self.cap_faces:
            for f in cf:
                faces.append(tuple(ring_id * n + int(order[i]) if i >= 0 else offset + base + (-1 - i) for i in f))
        names = sorted({k for a in self.attrs for k in a})
        attrs = {}
        for name in names:
            vals = [a.get(name, np.zeros(n)) for a in self.attrs]
            vals += [e.get(name, np.zeros(e["_m"])) for e in self.extra_attrs]
            attrs[name] = np.concatenate(vals)
        return verts, faces, attrs


def fusionner(parties, liens):
    """Fusionne plusieurs maillages (verts, faces, attrs) en identifiant des sommets.

    liens : (partie, sommet, partie_cible, sommet_cible) : le sommet est remplacé par le
    sommet cible (qui est conservé). Retourne (verts, faces, attrs, index, decalages_faces) :
    index[p][i] est l'index final du sommet i de la partie p, decalages_faces[p] l'index de
    la première face de la partie p.
    """
    off = np.cumsum([0] + [len(v) for v, _, _ in parties])
    parent = np.arange(off[-1])
    for p, i, q, j in liens:
        parent[off[p] + i] = off[q] + j
    racine = parent.copy()
    for _ in range(len(parties)):
        racine = parent[racine]
    garde = racine == np.arange(off[-1])
    nouvel = np.cumsum(garde) - 1
    final = nouvel[racine]
    verts = np.vstack([v for v, _, _ in parties])[garde]
    faces, f_off = [], []
    for p, (_, fs, _) in enumerate(parties):
        f_off.append(len(faces))
        faces += [tuple(int(final[off[p] + i]) for i in f) for f in fs]
    noms = sorted({k for _, _, a in parties for k in a})
    attrs = {k: np.concatenate([a.get(k, np.zeros(len(v))) for v, _, a in parties])[garde] for k in noms}
    index = [final[off[p]:off[p + 1]] for p in range(len(parties))]
    return verts, faces, attrs, index, f_off
