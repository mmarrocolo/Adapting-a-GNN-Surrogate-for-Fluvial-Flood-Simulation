"""Snap a weir polyline onto the SFINCS flux grid as a leak-proof cell-side cut, instead of
handing the raw digitized line to setup_structures.

Why: sampling points along the original line and recording which cell edges it happens to cross
does not guarantee a continuous barrier -- a straight line that stays inside one row while
advancing across several columns only blocks east-west flow there, leaving north-south flow
free through the same row. The fix: classify every nearby cell as being on one side or the other
of the line (a left/right test relative to the line's own local direction), then block every
pair of touching cells whose sides disagree. That is a graph cut -- no path between the two
sides can avoid a blocked edge, regardless of the line's angle or wiggle. See
model_results_Marg_infra_southonly_dz5m.ipynb sections 7b-7d for the diagnostic this was
developed against.
"""
from collections import defaultdict

import numpy as np
from shapely.geometry import LineString, Point


def leak_proof_weir_edges(line, x0, y0, dx, dy, max_perp=150.0):
    """Return the set of flux-grid edges forming a leak-proof cut along `line`.

    Only considers cells within `max_perp` metres of the line and within its own along-length
    span (so a partial-length levee stays open at its ends, as intended). Each edge is a tuple
    ('v', row, col) -- vertical grid line x = x0+col*dx spanning row -> row+1 -- or
    ('h', row, col) -- horizontal grid line y = y0+row*dy spanning col -> col+1.
    """
    length = line.length
    minx, miny, maxx, maxy = line.bounds
    c0 = int(np.floor((minx - max_perp - x0) / dx))
    c1 = int(np.ceil((maxx + max_perp - x0) / dx))
    r0 = int(np.floor((miny - max_perp - y0) / dy))
    r1 = int(np.ceil((maxy + max_perp - y0) / dy))

    side = {}
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            cx, cy = x0 + (c + 0.5) * dx, y0 + (r + 0.5) * dy
            t = line.project(Point(cx, cy))
            if t <= 0 or t >= length:
                continue
            nearest = line.interpolate(t)
            eps = min(1.0, length * 1e-4)
            p_fwd = line.interpolate(min(length, t + eps))
            p_bwd = line.interpolate(max(0, t - eps))
            tx, ty = p_fwd.x - p_bwd.x, p_fwd.y - p_bwd.y
            dxp, dyp = cx - nearest.x, cy - nearest.y
            if np.hypot(dxp, dyp) > max_perp:
                continue
            side[(r, c)] = 1 if (tx * dyp - ty * dxp) > 0 else -1

    edges = set()
    for (r, c), s in side.items():
        if (r, c + 1) in side and side[(r, c + 1)] != s:
            edges.add(('v', r, c + 1))
        if (r + 1, c) in side and side[(r + 1, c)] != s:
            edges.add(('h', r + 1, c))
    return edges


def edge_endpoints(edge, x0, y0, dx, dy):
    kind, a, b = edge
    if kind == 'v':
        x = x0 + b * dx
        return (round(x, 3), round(y0 + a * dy, 3)), (round(x, 3), round(y0 + (a + 1) * dy, 3))
    else:
        y = y0 + a * dy
        return (round(x0 + b * dx, 3), round(y, 3)), (round(x0 + (b + 1) * dx, 3), round(y, 3))


def stitch_edges_to_line(edges, x0, y0, dx, dy):
    """Order a set of grid edges into a single connected polyline (as an (N,2) array).

    The edge set from leak_proof_weir_edges forms a simple open path (a graph cut has no
    branches for a single dividing line) -- exactly two endpoints of degree 1, everything else
    degree 2. Raises if that assumption doesn't hold (e.g. a corridor wide/wiggly enough to
    produce a branching cut), since a branching structure can't be represented as one LineString.
    """
    adj = defaultdict(list)
    for e in edges:
        p1, p2 = edge_endpoints(e, x0, y0, dx, dy)
        adj[p1].append(p2)
        adj[p2].append(p1)

    ends = [pt for pt, nbrs in adj.items() if len(nbrs) == 1]
    if len(ends) != 2:
        raise ValueError(
            f'expected a simple open path (2 endpoints), got {len(ends)} -- '
            'the cut has branches and needs a different stitching strategy '
            '(e.g. a smaller max_perp corridor width)')

    path = [ends[0]]
    visited = set()
    cur, prev = ends[0], None
    while True:
        nxt = None
        for n in adj[cur]:
            key = tuple(sorted([cur, n]))
            if key not in visited:
                nxt = n
                visited.add(key)
                break
        if nxt is None:
            break
        path.append(nxt)
        prev, cur = cur, nxt
    return np.array(path)


def snap_line_to_grid(line, x0, y0, dx, dy, max_perp=150.0):
    """Full pipeline: digitized line -> leak-proof edge cut -> single stitched LineString."""
    edges = leak_proof_weir_edges(line, x0, y0, dx, dy, max_perp=max_perp)
    path = stitch_edges_to_line(edges, x0, y0, dx, dy)
    return LineString(path)
