#!/usr/bin/env python3
"""Build js/data.js from data/geomorfologie.svg.

The source SVG (from the MU thematic atlas) groups the geomorphological
division of Czechia as:

    <g id="p_*">          provincie  (contains an outline <path id="Name">)
      <g id="sbp_*">      soustavy   (contains a filled <path>)
        <path fill=none>  internal lines = hranice podsoustav
        <text>            podsoustava labels (rotated, multi-line)

Levels emitted (modern terminology — the atlas still says "subprovincie"
and "oblast"):

    window.GEOMORPH_VIEWBOX = "0 0 W H";
    window.GEOMORPH = {
      "provincie":   [ {code, name, subs, path, cx, cy}, ... ],
      "soustavy":    [ {code, name, alt, accept, parent, path, cx, cy}, ... ],
      "podsoustavy": [ {code, name, alt, accept, parent, path, cx, cy}, ... ]
    };

Podsoustavy are not stored in the SVG as polygons — only as grey boundary
chords inside each soustava plus a label per region. This script therefore
rebuilds them by planar subdivision: ring + chords become a planar graph,
faces are extracted with a half-edge walk, and each face is named by the
label that falls inside it. Atlas names ending in "oblast" are renamed to
"… podsoustava" (other suffixes — hornatina, vrchovina, tabule… — stay).

No third-party dependencies — plain stdlib only.
Run:  python3 -I scripts/build_data.py
"""

import json
import math
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "data" / "geomorfologie.svg"
OUT = ROOT / "js" / "data.js"

NS = "{http://www.w3.org/2000/svg}"

# Names as used by the atlas legend (columns "Provincie" / "Subprovincie";
# the modern terms are provincie / soustava).
PROVINCES = {
    "p_ceska-vysocina": "Česká vysočina",
    "p_stredoevropska-nizina": "Středoevropská nížina",
    "p_zapadni-karpaty": "Západní Karpaty",
    "p_zapadopanonska-panev": "Západopanonská pánev",
}
SOUSTAVY = {
    "sbp_sumavska": "Šumavská",
    "sbp_poberounska": "Poberounská",
    "sbp_krusnohorska": "Krušnohorská",
    "sbp_krkonossko-jesenicka": "Krkonošsko-jesenická",
    "sbp_ceskomoravska": "Českomoravská",
    "sbp_ceska-tabule": "Česká tabule",
    "sbp_stredopolske-niziny": "Středopolské nížiny",
    "sbp_vnekarpatske-snizeniny": "Vněkarpatské sníženiny",
    "sbp_vnejsi-zapadni-karpaty": "Vnější Západní Karpaty",
    "sbp_videnska-panev": "Vídeňská pánev",
}

# Two elongated bands get their widest part right next to a neighbour's
# label (Krkonošsko-jesenická beside Středopolské nížiny, Vnější Západní
# Karpaty beside Vněkarpatské sníženiny). Restricting the label search to
# the other end of each band keeps the map readable. Coordinates are the
# source SVG's own pixel space.
LABEL_CLAMP = {
    "sbp_krkonossko-jesenicka": {"x1": 1150},
    "sbp_vnejsi-zapadni-karpaty": {"y0": 640},
    # podsoustavy: keep neighbouring labels apart at the dense level
    "vychodoceska-tabule": {"x1": 880},
    "slovensko-moravske-karpaty": {"x0": 1420},
    # the Mikulov lobe is tiny; its label sits mid-lobe, so the Vídeňská
    # pánev label moves to the southern tongue to stay on its own line
    "videnska-panev": {"y0": 830},
}

SNAP = 4.0        # max px a chord endpoint may sit off the line it lands on
SIMPLIFY_TOL = 0.8  # RDP tolerance for emitted paths (px)

# A filled soustava path may hold more than one closed subpath: an exclave
# the atlas paints in the soustava colour but draws as its own outline
# (Vnější Západní Karpaty carry the Mikulov lobe = Jihomoravské Karpaty,
# their only podsoustava the atlas never splits off with a hranice chord).
# Subpaths smaller than this are pen slips, not land.
MIN_RING_AREA = 50.0

# ---------------------------------------------------------------- path parsing

TOKEN = re.compile(r"([MmLlHhVvCcSsQqTtZzAa])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


def flatten(d, samples=4):
    """Flatten an SVG path `d` string into a list of polylines [[(x,y), ...]].

    Handles M/m L/l H/h V/v C/c S/s Q/q T/t Z/z; cubic/quadratic curves are
    sampled, arcs (A/a — not present in this file) raise. Open subpaths stay
    open (2-point chords are kept: some hranice oblasti are tiny nicks).
    """
    toks = []
    for m in TOKEN.finditer(d):
        toks.append(m.group(1) if m.group(1) else float(m.group(2)))

    polys, cur = [], []
    x = y = 0.0            # current point
    sx = sy = 0.0          # current subpath start
    prev_ctrl = None       # second control point of previous C/S (for S/T)
    cmd = None
    i = 0

    def next_xy(i, rel):
        nx, ny = toks[i], toks[i + 1]
        if rel:
            nx, ny = x + nx, y + ny
        return nx, ny, i + 2

    def sample_bezier(p0, p1, p2, p3):
        pts = []
        for k in range(1, samples + 1):
            t = k / samples
            u = 1 - t
            px = u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0]
            py = u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1]
            pts.append((px, py))
        return pts

    while i < len(toks):
        if isinstance(toks[i], str):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                if cur:
                    polys.append(cur)
                    cur = []
                x, y = sx, sy
                prev_ctrl = None
                cmd = None
                continue
            if cmd in "Mm":
                if cur:
                    polys.append(cur)
                cur = []
        if cmd is None:
            raise ValueError(f"number before any command at token {i}")
        rel = cmd.islower()
        C = cmd.upper()

        if C == "M":
            x, y, i = next_xy(i, rel)
            sx, sy = x, y
            cur = [(x, y)]
            cmd = "L" if cmd == "M" else "l"
            prev_ctrl = None
        elif C == "L":
            x, y, i = next_xy(i, rel)
            cur.append((x, y))
            prev_ctrl = None
        elif C == "H":
            nx = toks[i] + (x if rel else 0.0)
            i += 1
            x = nx
            cur.append((x, y))
            prev_ctrl = None
        elif C == "V":
            ny = toks[i] + (y if rel else 0.0)
            i += 1
            y = ny
            cur.append((x, y))
            prev_ctrl = None
        elif C in ("C", "Q"):
            if C == "C":
                x1, y1, i = next_xy(i, rel)
                x2, y2, i = next_xy(i, rel)
                xe, ye, i = next_xy(i, rel)
                p1, p2 = (x1, y1), (x2, y2)
                prev_ctrl = (x2, y2)
            else:  # Q — sampled as the equivalent cubic
                x1, y1, i = next_xy(i, rel)
                xe, ye, i = next_xy(i, rel)
                p1 = (x + 2/3 * (x1 - x), y + 2/3 * (y1 - y))
                p2 = (xe + 2/3 * (x1 - xe), ye + 2/3 * (y1 - ye))
                prev_ctrl = None
            cur.extend(sample_bezier((x, y), p1, p2, (xe, ye)))
            x, y = xe, ye
        elif C in ("S", "T"):
            xe, ye, i = next_xy(i, rel)
            if C == "S":
                x2, y2, i = next_xy(i, rel)
                if prev_ctrl:
                    p1 = (2 * x - prev_ctrl[0], 2 * y - prev_ctrl[1])
                else:
                    p1 = (x, y)
                p2 = (x2, y2)
                prev_ctrl = (x2, y2)
            else:
                raise ValueError("T command not expected in this file")
            cur.extend(sample_bezier((x, y), p1, p2, (xe, ye)))
            x, y = xe, ye
        else:
            raise ValueError(f"unsupported command {cmd}")

    if cur:
        polys.append(cur)
    return [p for p in polys if len(p) >= 2]


# ------------------------------------------------------------------- transforms

def _mul(A, B):
    """Compose two SVG-layout matrices [a,b,c,d,e,f] (A·B): B first, then A."""
    return [
        A[0]*B[0] + A[2]*B[1], A[1]*B[0] + A[3]*B[1],
        A[0]*B[2] + A[2]*B[3], A[1]*B[2] + A[3]*B[3],
        A[0]*B[4] + A[2]*B[5] + A[4], A[1]*B[4] + A[3]*B[5] + A[5],
    ]


def parse_transform(tr):
    """SVG transform list → matrix [a,b,c,d,e,f] (x' = a x + c y + e)."""
    M = [1, 0, 0, 1, 0, 0]
    if not tr:
        return M
    for fn, arg in re.findall(r"(\w+)\(([^)]*)\)", tr):
        n = [float(v) for v in re.findall(r"[-+]?[\d.]+(?:e[-+]?\d+)?", arg)]
        if fn == "matrix":
            m = n[:6]
        elif fn == "scale":
            m = [n[0], 0, 0, n[0] if len(n) < 2 else n[1], 0, 0]
        elif fn == "translate":
            m = [1, 0, 0, 1, n[0], n[1] if len(n) > 1 else 0]
        elif fn == "rotate":
            a = math.radians(n[0])
            ca, sa = math.cos(a), math.sin(a)
            m = [ca, sa, -sa, ca, 0, 0]
            if len(n) >= 3:  # rotate about a centre
                cx, cy = n[1], n[2]
                m = _mul([1, 0, 0, 1, cx, cy], _mul(m, [1, 0, 0, 1, -cx, -cy]))
        else:
            raise ValueError(f"unsupported transform {fn}")
        M = _mul(M, m)
    return M


def apply_m(M, p):
    return (M[0]*p[0] + M[2]*p[1] + M[4], M[1]*p[0] + M[3]*p[1] + M[5])


# ------------------------------------------------------------------ simplification

def rdp(points, tol):
    """Ramer–Douglas–Peucker; endpoints kept."""
    if len(points) < 3:
        return points[:]

    def perp_dist(p, a, b):
        if a[0] == b[0] and a[1] == b[1]:
            return math.hypot(p[0] - a[0], p[1] - a[1])
        num = abs((b[0] - a[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (b[1] - a[1]))
        return num / math.hypot(b[0] - a[0], b[1] - a[1])

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        dmax, idx = 0.0, -1
        for i in range(a + 1, b):
            if keep[i]:
                continue
            d = perp_dist(points[i], points[a], points[b])
            if d > dmax:
                dmax, idx = d, i
        if idx != -1 and dmax > tol:
            keep[idx] = True
            stack.append((a, idx))
            stack.append((idx, b))
    return [points[i] for i in range(len(points)) if keep[i]]


def poly_area(pts):
    """Shoelace area of a closed polyline (absolute value)."""
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2


# ------------------------------------------------------------ label placement

def label_point(polys, grid=180, clamp=None):
    """Pole of inaccessibility: rasterize the shape and return the interior
    cell centre farthest from any exterior cell (chamfer 2-pass DT).
    Guaranteed inside the polygon — unlike a plain centroid, which for
    crescent-shaped units (e.g. Krkonošsko-jesenická) can fall outside."""
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cell = max((x1 - x0), (y1 - y0)) / grid
    if cell <= 0:
        return round((x0 + x1) / 2, 1), round((y0 + y1) / 2, 1)
    w = int((x1 - x0) / cell) + 1
    h = int((y1 - y0) / cell) + 1

    # Scanline span-fill (even-odd): for each raster row collect edge
    # crossings, sort, and mark the cells between pairs of crossings.
    edges = []
    for poly in polys:
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i + 1) % n]
            edges.append((a[0], a[1], b[0], b[1]))

    inside = bytearray(w * h)
    for gy in range(h):
        py = y0 + (gy + 0.5) * cell
        xints = []
        for ax, ay, bx, by in edges:
            if (ay > py) != (by > py):
                xints.append(ax + (py - ay) * (bx - ax) / (by - ay))
        xints.sort()
        row = gy * w
        for k in range(0, len(xints) - 1, 2):
            # cell gx covers centre x0+(gx+0.5)*cell; mark cells whose centre
            # falls inside the span [xa, xb]
            ga = max(0, math.ceil((xints[k] - x0) / cell - 0.5))
            gb = min(w - 1, math.floor((xints[k + 1] - x0) / cell - 0.5))
            for gx in range(ga, gb + 1):
                inside[row + gx] = 1

    INF = 1 << 30
    dist = [0 if not inside[i] else INF for i in range(w * h)]
    # forward pass
    for gy in range(h):
        for gx in range(w):
            i = gy * w + gx
            if dist[i] == 0:
                continue
            best = dist[i]
            if gx:              best = min(best, dist[i - 1] + 1)
            if gy:              best = min(best, dist[i - w] + 1)
            if gx and gy:       best = min(best, dist[i - w - 1] + 2)
            if gx < w-1 and gy: best = min(best, dist[i - w + 1] + 2)
            dist[i] = best
    # backward pass
    for gy in range(h - 1, -1, -1):
        for gx in range(w - 1, -1, -1):
            i = gy * w + gx
            if dist[i] == 0:
                continue
            best = dist[i]
            if gx < w-1:          best = min(best, dist[i + 1] + 1)
            if gy < h-1:          best = min(best, dist[i + w] + 1)
            if gx < w-1 and gy < h-1: best = min(best, dist[i + w + 1] + 2)
            if gx and gy < h-1:       best = min(best, dist[i + w - 1] + 2)
            dist[i] = best

    def clamped(gx, gy):
        if not clamp:
            return True
        px, py = x0 + (gx + 0.5) * cell, y0 + (gy + 0.5) * cell
        return (px >= clamp.get("x0", -1e9) and px <= clamp.get("x1", 1e9)
                and py >= clamp.get("y0", -1e9) and py <= clamp.get("y1", 1e9))

    best_i, best_d = -1, -1
    for i, dv in enumerate(dist):
        if inside[i] and dv > best_d and clamped(i % w, i // w):
            best_i, best_d = i, dv
    if best_i < 0:  # degenerate sliver — fall back to bbox centre
        return round((x0 + x1) / 2, 1), round((y0 + y1) / 2, 1)
    gx, gy = best_i % w, best_i // w
    return round(x0 + (gx + 0.5) * cell, 1), round(y0 + (gy + 0.5) * cell, 1)


def point_in_poly(px, py, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > py) != (y1 > py):
            if px < x0 + (py - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
    return inside


# --------------------------------------------------------- planar subdivision

def split_faces(ring, chords, tag=""):
    """Split a simple ring by open chords into face polygons.

    The chords (hranice podsoustav) form a forest: each one runs from the
    ring (or from another chord, T-junction) to the ring. Processing them
    one by one — always the chord whose both endpoints already sit on a
    single face boundary — keeps every face an exact closed polygon:
    face = ring arc + chord, no angle arithmetic, no tolerance trouble
    with the near-parallel 6px nicks the atlas contains.

    Endpoints are snapped to the nearest *vertex* of the (simplified) ring
    or of another chord, so shared boundary points match exactly.
    """
    chords = [c for c in chords if len(c) >= 2]

    # 0. glue chords that meet end-to-end (one divider drawn as several
    #    paths) into single polylines, else they'd defer each other forever
    glued = True
    while glued:
        glued = False
        for i in range(len(chords)):
            for j in range(i + 1, len(chords)):
                a, b = chords[i], chords[j]
                if math.dist(a[-1], b[0]) <= 0.5:
                    new = a + b[1:]
                elif math.dist(a[-1], b[-1]) <= 0.5:
                    new = a + b[::-1][1:]
                elif math.dist(a[0], b[0]) <= 0.5:
                    new = a[::-1] + b[1:]
                elif math.dist(a[0], b[-1]) <= 0.5:
                    new = b + a[1:]
                else:
                    continue
                chords[i] = new
                del chords[j]
                glued = True
                break
            if glued:
                break

    def nearest_vertex(p, pts):
        bi = min(range(len(pts)), key=lambda i: math.dist(p, pts[i]))
        return bi, math.dist(p, pts[bi])

    # 1. snap every chord endpoint to the nearest vertex of the ring or of
    #    another chord (T-junction), on the still-dense geometry
    land = {}
    for ci, c in enumerate(chords):
        for end in (0, -1):
            i, d = nearest_vertex(c[end], ring)
            best = (d, ("ring", i))
            for cj, o in enumerate(chords):
                if cj == ci:
                    continue
                i, d = nearest_vertex(c[end], o)
                if d < best[0]:
                    best = (d, (cj, i))
            if best[0] > SNAP:
                raise SystemExit(
                    f"{tag} chord endpoint {c[end]} lands {best[0]:.1f}px off everything")
            land[(ci, end)] = best[1]

    # 2. simplify ring/chords in pieces between junction nodes, so the
    #    shared points survive RDP and neighbours stay stitch-free
    def simplify_poly(poly, closed, node_idxs):
        idxs = sorted(set(node_idxs))
        if not closed:
            idxs = [0] + [i for i in idxs if 0 < i < len(poly) - 1] + [len(poly) - 1]
        if closed and not idxs:
            return rdp(poly, SIMPLIFY_TOL)
        seq = idxs + ([idxs[0]] if closed else [])
        out = []
        for a, b in zip(seq, seq[1:]):
            chunk = poly[a:b + 1] if a < b else poly[a:] + poly[:b + 1]
            simp = rdp(chunk, SIMPLIFY_TOL)
            if out and out[-1] == simp[0]:
                out.extend(simp[1:])
            else:
                out.extend(simp)
        return out

    ring_nodes = [i for (t, i) in land.values() if t == "ring"]
    if chords and not ring_nodes:
        raise SystemExit("no chord endpoint lands on the ring")
    ring_s = simplify_poly(ring, True, ring_nodes)
    chord_nodes = {ci: [] for ci in range(len(chords))}
    for (ci, _end), (t, i) in land.items():
        if t != "ring":
            chord_nodes[t].append(i)
    snapped = [simplify_poly(c, False, chord_nodes[ci])
               for ci, c in enumerate(chords)]
    for (ci, end), (t, i) in land.items():
        q = ring[i] if t == "ring" else chords[t][i]
        if end == 0:
            snapped[ci][0] = q
        else:
            snapped[ci][-1] = q

    faces = [ring_s]
    pending = list(range(len(snapped)))
    while pending:
        progressed = False
        for ci in pending[:]:
            c = snapped[ci]
            a, b = c[0], c[-1]
            hit = None
            for fi, f in enumerate(faces):
                idx = {pt: i for i, pt in enumerate(f)}
                if a in idx and b in idx:
                    hit = (fi, idx[a], idx[b])
                    break
            if hit is None:
                continue  # T-end lives on a chord not split off yet
            fi, ia, ib = hit
            if ia == ib:
                pending.remove(ci)   # degenerate zero-length chord
                progressed = True
                continue
            f = faces[fi]
            n = len(f)
            arc_ab = f[ia:ib + 1] if ia < ib else f[ia:] + f[:ib + 1]
            arc_ba = f[ib:ia + 1] if ib < ia else f[ib:] + f[:ia + 1]
            inner = c[1:-1]
            faces[fi:fi + 1] = [arc_ab + inner[::-1], arc_ba + inner]
            pending.remove(ci)
            progressed = True
        if not progressed:
            raise SystemExit(f"{tag}: {len(snapped)} chords do not connect: {len(pending)} left")
    return faces


# ------------------------------------------------------------------- labels

def collect_labels(sg):
    """Cluster <text> elements of a soustava group into podsoustava labels.

    Multi-line names arrive as several <text> elements stacked in local
    coordinates (same rotation, x within ~12px, y step 8–30px). Returns
    [{name, points:[transformed anchors…]}].
    """
    els = []
    for t in sg.iter(f"{NS}text"):
        parts = [ts.text.strip() for ts in t.findall(f"{NS}tspan")
                 if ts.text and ts.text.strip()]
        if not parts:
            continue
        x, y = float(t.get("x")), float(t.get("y"))
        M = parse_transform(t.get("transform"))
        els.append({"tr": t.get("transform") or "", "x": x, "y": y,
                    "M": M, "text": " ".join(parts)})

    clusters = []
    for el in els:
        placed = False
        for c in clusters:
            last = c[-1]
            if (el["tr"] == last["tr"] and abs(el["x"] - last["x"]) <= 12
                    and 8 <= el["y"] - last["y"] <= 30):
                c.append(el)
                placed = True
                break
        if not placed:
            clusters.append([el])

    out = []
    for c in clusters:
        name = " ".join(el["text"] for el in c)
        M = c[0]["M"]
        x, y = c[0]["x"], c[0]["y"]
        w = len(name) * 11.0  # local font-size is 22.5 → ~11px per char
        # candidate anchor points: on the text line, and one line below —
        # the atlas sometimes sets a label above a small region (e.g.
        # Krkonošsko-jesenické podhůří), not inside it
        pts = [apply_m(M, (x, y)), apply_m(M, (x + w * 0.5, y)),
               apply_m(M, (x + w * 0.25, y)), apply_m(M, (x + w * 0.1, y + 28)),
               apply_m(M, (x + w * 0.3, y + 28))]
        out.append({"name": name, "points": pts})
    return out


def rename_oblast(name):
    """Atlas uses the old term 'oblast' for this level; modern term is
    'podsoustava'. Other suffixes (hornatina, vrchovina, tabule…) stay."""
    return re.sub(r"\boblast\b", "podsoustava", name)


def slug(name):
    s = unicodedata.normalize("NFD", name.lower())
    s = re.sub(r"[\u0300-\u036f]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


# ------------------------------------------------------------------- extraction

def main():
    tree = ET.parse(SRC)
    root = tree.getroot()
    vb = root.get("viewBox")

    provincie, soustavy, podsoustavy = [], [], []

    for pg in root.findall(f"{NS}g"):
        pid = pg.get("id") or ""
        if pid not in PROVINCES:
            continue

        # province geometry: direct child outline <path id="Capitalized">
        outline = None
        for p in pg.findall(f"{NS}path"):
            if p.get("id"):
                outline = p
        if outline is None:
            raise SystemExit(f"no outline path for province {pid}")

        subs_here = 0
        for sg in pg.findall(f"{NS}g"):
            sid = sg.get("id") or ""
            if sid not in SOUSTAVY:
                continue
            # soustava geometry: every filled path inside the group
            ds = [p.get("d") for p in sg.iter(f"{NS}path")
                  if (p.get("fill") or "none") != "none" and p.get("d")]
            if not ds:
                raise SystemExit(f"no filled path for {sid}")
            d = " ".join(ds)
            polys = flatten(d)
            # exclaves arrive as extra closed subpaths of the same fill
            rings = [p for p in polys if poly_area(p) >= MIN_RING_AREA]
            if not rings:
                raise SystemExit(f"{sid}: no usable ring in filled path")
            ring = max(rings, key=len)
            islands = [p for p in rings if p is not ring]
            cx, cy = label_point(polys, clamp=LABEL_CLAMP.get(sid))
            name = SOUSTAVY[sid]
            subs_here += 1
            # Display form: only single-word adjectival names take the level
            # word ("Šumavská" → "Šumavská soustava"); names that already
            # carry a noun ("Česká tabule", "Vídeňská pánev") show unchanged.
            # Both forms stay accepted when typed.
            full = f"{name} soustava"
            soustavy.append({
                "code": sid,
                "name": name,
                "alt": full if " " not in name else None,
                "accept": [name, full],
                "parent": PROVINCES[pid],
                "path": d,
                "cx": cx,
                "cy": cy,
            })

            # ---- podsoustavy: chords + labels → planar subdivision ----
            chords = [poly for p in sg.iter(f"{NS}path")
                      if (p.get("fill") or "none") == "none" and p.get("d")
                      for poly in flatten(p.get("d"))]
            labels = collect_labels(sg)
            if not chords:
                split_pts = [ring]
            else:
                split_pts = split_faces(ring, chords, sid)
                # sanity: chords must tile the main ring
                tot = sum(poly_area(f) for f in split_pts)
                if abs(tot - poly_area(ring)) > 0.03 * poly_area(ring):
                    raise SystemExit(
                        f"{sid}: face area {tot:.0f} != ring {poly_area(ring):.0f}")
            # Exclaves become a face of their own when the atlas labels them
            # (the Mikulov lobe = Jihomoravské Karpaty); otherwise they merge
            # into the nearest face (Frýdlant spur of Středopolské nížiny).
            # A face is a list of rings from here on.
            if len(split_pts) + len(islands) == len(labels):
                faces = [[f] for f in split_pts] + [[i] for i in islands]
            elif len(split_pts) == len(labels):
                faces = [[f] for f in split_pts]
                for isl in islands:
                    ci = (sum(p[0] for p in isl) / len(isl),
                          sum(p[1] for p in isl) / len(isl))
                    fi = min(range(len(faces)), key=lambda k: min(
                        math.dist(ci, p)
                        for r in faces[k] for p in r[::8]))
                    faces[fi].append(isl)
            else:
                raise SystemExit(f"{sid}: {len(split_pts)} faces + "
                                 f"{len(islands)} exclaves vs {len(labels)} labels")
            # assign labels to faces: anchor first, then the rest of the
            # text line, then the line below (atlas sets some labels above
            # their region), and finally nearest face centroid
            assign = {}
            avail = list(range(len(labels)))
            for which in ((0,), (0, 1, 2), (3, 4)):
                for fi, face in enumerate(faces):
                    if fi in assign:
                        continue
                    for li in avail:
                        if any(point_in_poly(labels[li]["points"][k][0],
                                             labels[li]["points"][k][1], r)
                               for r in face for k in which):
                            assign[fi] = li
                            avail.remove(li)
                            break
            cent = []
            for f in faces:
                pts = [p for r in f for p in r]
                cent.append((sum(p[0] for p in pts) / len(pts),
                             sum(p[1] for p in pts) / len(pts)))
            for fi, face in enumerate(faces):
                if fi in assign:
                    continue
                if not avail:
                    raise SystemExit(f"{sid}: face without label")
                li = min(avail, key=lambda k: math.dist(labels[k]["points"][0],
                                                        cent[fi]))
                assign[fi] = li
                avail.remove(li)
            if avail:
                raise SystemExit(f"{sid}: label {[labels[i]['name'] for i in avail]} unused")

            for fi, face in enumerate(faces):
                lab = labels[assign[fi]]
                raw = lab["name"]
                nm = rename_oblast(raw)
                fcx, fcy = label_point(face, clamp=LABEL_CLAMP.get(slug(nm)))
                rec = {
                    "code": slug(nm),
                    "name": nm,
                    "accept": [nm] + ([raw] if raw != nm else []),
                    "parent": name,
                    "path": " ".join(
                        "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in r) + " Z"
                        for r in face),
                    "cx": fcx,
                    "cy": fcy,
                }
                # the atlas' old name stays accept-only (never displayed)
                podsoustavy.append(rec)

        d = outline.get("d")
        cx, cy = label_point(flatten(d))
        provincie.append({
            "code": pid,
            "name": PROVINCES[pid],
            "subs": subs_here,
            "path": d,
            "cx": cx,
            "cy": cy,
        })

    js = [
        "// Auto-generated by scripts/build_data.py — do not edit by hand.",
        "// Source: data/geomorfologie.svg (Česká republika – Tematický atlas,",
        "//         Pedagogická fakulta Masarykovy univerzity, 2017).",
        "// Terminology: the atlas says subprovincie/oblast; modern terms are",
        "//         soustava/podsoustava (oblast→podsoustava renamed here).",
        f"window.GEOMORPH_VIEWBOX = {json.dumps(vb)};",
        "window.GEOMORPH = " + json.dumps(
            {"provincie": provincie, "soustavy": soustavy,
             "podsoustavy": podsoustavy}, ensure_ascii=False) + ";",
    ]
    OUT.write_text("\n".join(js) + "\n", encoding="utf-8")

    print(f"wrote {OUT} — {len(provincie)} provincie + {len(soustavy)} soustavy"
          f" + {len(podsoustavy)} podsoustavy, {OUT.stat().st_size} bytes;"
          f" viewBox {vb}")
    for u in podsoustavy:
        extra = f"  (atlas: {u['alt']})" if u.get("alt") else ""
        print(f"  pod: {u['name']:32s} @ {u['cx']:7.1f} {u['cy']:6.1f}"
              f"  ({u['parent']}){extra}")


if __name__ == "__main__":
    main()
