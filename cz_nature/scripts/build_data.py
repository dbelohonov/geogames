#!/usr/bin/env python3
"""Build js/data.js from data/CR_VZCHU_2025.svg.

The source SVG (velkoplošná zvláště chráněná území ČR, stav 2025 — including
CHKO Soutok declared in 2025) is an Illustrator export with three layers:

    <g id="Vrstva_1">  grey country silhouette (polygon.cls-5),
                       4 národní parky (path/polygon.cls-6, brown),
                       2 legend swatches (tiny 6-point polygons)
    <g id="Vrstva_2">  27 CHKO (polygon/path.cls-2 or .cls-3, green)
    <g id="Vrstva_6">  31 region <text> labels (cls-20 = NP, cls-21 = CHKO;
                       two legend texts), one duplicate NP polygon

Names are NOT read from the labels — the kerning tspans lose spaces
("CHKOLitovelskéPomoraví") — they come from the hardcoded tables below.
The labels only tell us *which shape is which*: each label's anchor and
points along its baseline are tested with point-in-polygon until exactly
one shape of the same category contains one of them.

Quirks handled here:
  • NP Krkonoše is one evenodd path whose 3 inner rings are enclaves
    (holes) — kept verbatim, the game CSS sets fill-rule: evenodd.
  • 6 CHKO consist of several disjoint fragments (Labské pískovce,
    Český ráj, Šumava, Český les, České středohoří, Soutok) — one region,
    one record, all fragments in a single path.
  • CHKO Šumava / Labské pískovce partly overlap their NP; the game
    draws NPs on top, so nothing is lost.
  • legend swatches are filtered by vertex count, the Vrstva_6 duplicate
    by layer, legend texts by content.

Emitted:
    window.NATURE_VIEWBOX = "0 0 W H";
    window.NATURE = {
      base: "<country silhouette path>",
      np:   [ {code, name, alt, accept, cat, path, cx, cy}, ... ],
      chko: [ {code, name, alt, accept, cat, path, cx, cy}, ... ]
    };

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
SRC = ROOT / "data" / "CR_VZCHU_2025.svg"
OUT = ROOT / "js" / "data.js"

NS = "{http://www.w3.org/2000/svg}"

# ------------------------------------------------------------------- names

# (short name, extra accepted spellings). Display form adds the category
# prefix ("NP …" / "CHKO …"); the typed quiz also accepts the short name
# and the spelled-out category form.
NPS = [
    ("Šumava", []),
    ("Krkonoše", ["Krkonošský NP", "Krkonošský národní park", "KRNAP"]),
    ("České Švýcarsko", []),
    ("Podyjí", []),
]
CHKOS = [
    ("Beskydy", []),
    ("Bílé Karpaty", []),
    ("Blaník", []),
    ("Blanský les", []),
    ("Brdy", []),
    ("Broumovsko", []),
    ("Český kras", []),
    ("Český les", []),
    ("České středohoří", []),
    ("Český ráj", []),
    ("Jeseníky", []),
    ("Jizerské hory", []),
    ("Kokořínsko – Máchův kraj", ["Kokořínsko"]),
    ("Křivoklátsko", []),
    ("Labské pískovce", []),
    ("Litovelské Pomoraví", []),
    ("Lužické hory", []),
    ("Moravský kras", []),
    ("Orlické hory", []),
    ("Pálava", []),
    ("Poodří", []),
    ("Soutok", []),
    ("Slavkovský les", []),
    ("Šumava", []),
    ("Třeboňsko", []),
    ("Žďárské vrchy", []),
    ("Železné hory", []),
]
CATEGORIES = {
    "np": {"prefix": "NP", "full": "Národní park", "cat": "národní park"},
    "chko": {"prefix": "CHKO", "full": "Chráněná krajinná oblast",
             "cat": "chráněná krajinná oblast"},
}

# Manual label anchors for regions whose pole of inaccessibility lands in
# a crowded corner of the map (the dense north and central Bohemia). The
# override is used only if it really falls inside the region; otherwise
# the pole stands. Coords are source-SVG pixel space.
LABEL_OVERRIDE = {
    # the north: three two-line labels stacked in a 40×25 unit corner —
    # anchors verified label-box-disjoint (scripts grid-searched them)
    "np-ceske-svycarsko": (183.0, 19.5),
    "chko-labske-piskovce": (152.5, 34.0),
    "chko-luzicke-hory": (207.0, 36.0),
    # central Bohemia: neighbours whose poles face each other
    "chko-krivoklatsko": (138.0, 128.0),
    "chko-cesky-kras": (176.5, 129.5),
    # the south-west: CHKO Šumava pole sat against Blanský les
    "chko-sumava": (136.0, 250.0),
}

# source-SVG classes
BASE_CLASS = "cls-5"      # grey country silhouette
NP_FILL = {"cls-6"}       # brown protected areas
CHKO_FILL = {"cls-2", "cls-3"}  # green protected areas
NP_LABEL = "cls-20"       # brown label text
CHKO_LABEL = "cls-21"     # green label text
MIN_SHAPE_PTS = 30        # legend swatches have 6 points; regions ≥ 50

# ---------------------------------------------------------------- path parsing
# (shared with cz_geomorphology/scripts/build_data.py)

TOKEN = re.compile(r"([MmLlHhVvCcSsQqTtZzAa])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


def flatten(d, samples=4):
    """Flatten an SVG path `d` string into a list of closed/open polylines."""
    toks = []
    for m in TOKEN.finditer(d):
        toks.append(m.group(1) if m.group(1) else float(m.group(2)))

    polys, cur = [], []
    x = y = 0.0
    sx = sy = 0.0
    prev_ctrl = None
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
            else:
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


def parse_translate(tr):
    """The label transforms are plain translate(x y)."""
    m = re.fullmatch(r"\s*translate\(\s*([-\d.]+)[ ,]+([-\d.]+)\s*\)\s*", tr or "")
    if not m:
        raise ValueError(f"unexpected label transform: {tr!r}")
    return float(m.group(1)), float(m.group(2))


# ------------------------------------------------------------------ geometry

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
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2


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


def point_in_shape(px, py, rings):
    """Even-odd containment across all rings of one shape (holes count)."""
    return sum(1 for r in rings if point_in_poly(px, py, r)) % 2 == 1


def nudge_inside(pt, rings, max_r=8.0):
    """Nearest interior point to `pt` on a spiral — manual label anchors
    sometimes aim at a notch of a thin polygon; nudge keeps the intent."""
    if point_in_shape(pt[0], pt[1], rings):
        return pt
    r = 0.5
    while r <= max_r:
        for k in range(12):
            a = math.pi * k / 6
            q = (pt[0] + r * math.cos(a), pt[1] + r * math.sin(a))
            if point_in_shape(q[0], q[1], rings):
                return q
        r += 0.5
    return None


def label_point(polys, grid=100):
    """Pole of inaccessibility: interior raster cell farthest from the
    border (chamfer 2-pass distance transform). Guaranteed inside — unlike
    a centroid, which for fragmented/crescent regions can fall outside."""
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cell = max((x1 - x0), (y1 - y0)) / grid
    if cell <= 0:
        return round((x0 + x1) / 2, 1), round((y0 + y1) / 2, 1)
    w = int((x1 - x0) / cell) + 1
    h = int((y1 - y0) / cell) + 1

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
        # even-odd across ALL rings of the shape: pair crossings globally
        row = gy * w
        for k in range(0, len(xints) - 1, 2):
            ga = max(0, math.ceil((xints[k] - x0) / cell - 0.5))
            gb = min(w - 1, math.floor((xints[k + 1] - x0) / cell - 0.5))
            for gx in range(ga, gb + 1):
                inside[row + gx] = 1

    INF = 1 << 30
    dist = [0 if not inside[i] else INF for i in range(w * h)]
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

    best_i, best_d = -1, -1
    for i, dv in enumerate(dist):
        if inside[i] and dv > best_d:
            best_i, best_d = i, dv
    if best_i < 0:
        return round((x0 + x1) / 2, 1), round((y0 + y1) / 2, 1)
    gx, gy = best_i % w, best_i // w
    return round(x0 + (gx + 0.5) * cell, 1), round(y0 + (gy + 0.5) * cell, 1)


# ------------------------------------------------------------------- helpers

def slug(name):
    s = unicodedata.normalize("NFD", name.lower())
    s = re.sub(r"[\u0300-\u036f]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def norm_key(s):
    """Diacritics/space/punctuation-insensitive key (mirrors js/normalize.js)."""
    s = unicodedata.normalize("NFD", s)
    s = re.sub(r"[\u0300-\u036f]", "", s)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def rings_of(el):
    if el.tag == NS + "polygon":
        nums = [float(v) for v in re.findall(r"-?\d*\.?\d+", el.get("points"))]
        return [list(zip(nums[0::2], nums[1::2]))]
    return [r for r in flatten(el.get("d")) if len(r) >= 3]


def shape_path(rings, tol):
    out = []
    for r in rings:
        s = rdp(r, tol)
        out.append("M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in s) + " Z")
    return " ".join(out)


# ------------------------------------------------------------------- extraction

def collect_shapes(layer, classes):
    """Region shapes of one layer, legend swatches filtered by vertex count."""
    shapes = []
    for el in layer:
        if el.tag not in (NS + "path", NS + "polygon"):
            continue
        if el.get("class") not in classes:
            continue
        rings = rings_of(el)
        if sum(len(r) for r in rings) < MIN_SHAPE_PTS:
            continue  # legend swatch
        shapes.append({
            "rings": rings,
            "area": sum(poly_area(r) for r in rings),
            "pts": [p for r in rings for p in r],
        })
    return shapes


def collect_labels(layer):
    out = []
    for t in layer.iter(NS + "text"):
        raw = "".join(ts.text or "" for ts in t.iter(NS + "tspan")).strip()
        if not raw:
            continue
        key = norm_key(raw)
        if key in ("narodnipark", "chranenakrajinnaoblast"):
            continue  # legend texts
        kind = "np" if t.get("class") == NP_LABEL else (
            "chko" if t.get("class") == CHKO_LABEL else None)
        if kind is None:
            raise SystemExit(f"label with unknown class {t.get('class')}: {raw}")
        x, y = parse_translate(t.get("transform"))
        out.append({"raw": raw, "key": key, "kind": kind, "x": x, "y": y})
    return out


def match_names(labels, table, kind):
    """Map each label to its canonical entry via normalized name variants."""
    meta = CATEGORIES[kind]
    lookup = {}
    for short, extra in table:
        display = f"{meta['prefix']} {short}"
        full = f"{meta['full']} {short}"
        rec = {"short": short, "display": display,
               "accept": [display, short, full] + extra}
        for v in rec["accept"]:
            k = norm_key(v)
            if k in lookup and lookup[k]["short"] != short:
                raise SystemExit(f"ambiguous name variant {v!r}")
            lookup[k] = rec
    used = {}
    for lab in labels:
        rec = lookup.get(lab["key"])
        if rec is None:
            raise SystemExit(f"{kind} label {lab['raw']!r} matches no known name")
        if rec["short"] in used:
            raise SystemExit(f"{kind} name {rec['short']} matched twice")
        used[rec["short"]] = True
        lab["rec"] = rec
    if len(used) != len(table):
        missing = [s for s, _ in table if s not in used]
        raise SystemExit(f"{kind}: no label for {missing}")
    return [lab for lab in labels]


def pair(labels, shapes, kind):
    """Assign each label to the shape it belongs to (weighted probe votes).

    Labels are left-anchored text with tricky placement: they are often
    wider than their region, may start far outside it ("CHKO Labské
    pískovce" begins ~25 units west of the shape, its text crossing over
    NP České Švýcarsko) or sit entirely above it ("CHKO Lužické hory").
    So instead of a single anchor test we scatter probe points over the
    whole text box — along the baseline, above and below it — and score
    every shape by the probes it contains. Probes near the text start and
    on the baseline row weigh most (cartographers start labels inside
    "their" region); rows below the baseline catch labels set above a
    small region. Pairs are then assigned greedily by descending score,
    which resolves overlaps between neighbouring labels.
    """
    X_FRACS = [0.02 + 0.12 * i for i in range(9)]
    Y_ROWS = [(-8, 0.4), (-4, 1.0), (3, 0.8), (12, 0.45), (20, 0.3)]

    def probe_list(lab):
        # ~0.46 em average glyph advance at font-size 11; probes decay
        # exponentially with distance from the text start — cartographers
        # begin a label inside "their" region, but long names run far
        # over neighbours ("CHKO Blanský les" ends above Třeboňsko)
        w = len(lab["raw"]) * 5.1
        pts = []
        for fx in X_FRACS:
            xw = math.exp(-3.0 * fx)
            for dy, yw in Y_ROWS:
                pts.append((lab["x"] + w * fx, lab["y"] + dy, xw * yw))
        return pts

    probes = {id(lab): probe_list(lab) for lab in labels}
    bboxes = {}
    for si, s in enumerate(shapes):
        xs = [p[0] for p in s["pts"]]
        ys = [p[1] for p in s["pts"]]
        bboxes[si] = (min(xs), min(ys), max(xs), max(ys))

    def score(lab, si):
        s = shapes[si]
        x0, y0, x1, y1 = bboxes[si]
        tot = 0.0
        for px, py, wt in probes[id(lab)]:
            if px < x0 or px > x1 or py < y0 or py > y1:
                continue
            if point_in_shape(px, py, s["rings"]):
                tot += wt
        return tot

    assigned, taken = {}, set()
    pool = list(labels)
    while pool:
        ranked = []          # (best, second, lab, best_si)
        for lab in pool:
            sc = sorted(((score(lab, si), si)
                         for si in range(len(shapes)) if si not in assigned),
                        reverse=True)
            sc = [(v, si) for v, si in sc if v > 0]
            if not sc:
                continue
            second = sc[1][0] if len(sc) > 1 else 0.0
            ranked.append((sc[0][0], second, lab, sc[0][1]))
        if not ranked:
            break
        # confident pairs: clear winner (≥ 2× runner-up); assign those
        # first (highest score wins a contested shape), then re-score the
        # rest with the taken shapes out of the pool — that resolves
        # label-over-neighbour ambiguities round by round
        ranked.sort(key=lambda t: -t[0])
        confident = [t for t in ranked if t[0] >= 2 * t[1]]
        batch = confident or [ranked[0]]   # stall-breaker: global best
        progressed = False
        for best, second, lab, si in batch:
            if si in assigned or id(lab) in taken:
                continue
            assigned[si] = lab
            taken.add(id(lab))
            pool.remove(lab)
            progressed = True
        if not progressed:       # all batched pairs raced away — loop again
            continue

    # fallback: nearest shape by anchor distance for labels whose probes
    # missed everything (e.g. "NP Šumava" starts far west of its crescent)
    for lab in labels:
        if id(lab) in taken:
            continue
        ax, ay = lab["x"], lab["y"]
        best = min((i for i in range(len(shapes)) if i not in assigned),
                   key=lambda i: min(math.dist((ax, ay), p)
                                     for p in shapes[i]["pts"][::5]),
                   default=None)
        if best is None:
            raise SystemExit(f"{kind}: no shape left for {lab['raw']!r}")
        print(f"  warning: {kind} label {lab['raw']!r} paired by distance")
        assigned[best] = lab
        taken.add(id(lab))
    if len(assigned) != len(shapes) or len(taken) != len(labels):
        raise SystemExit(f"{kind}: {len(assigned)} paired vs {len(shapes)} shapes")
    return assigned


def main():
    tree = ET.parse(SRC)
    root = tree.getroot()
    vb = root.get("viewBox")
    layers = {g.get("id"): g for g in root.findall(NS + "g")}

    # ---- country base (decorative silhouette, not interactive)
    base = None
    for el in layers["Vrstva_1"]:
        if el.tag == NS + "polygon" and el.get("class") == BASE_CLASS:
            base = el
    if base is None:
        raise SystemExit("no country base polygon (cls-5)")
    base_path = shape_path(rings_of(base), 0.7)

    # ---- region shapes
    np_shapes = collect_shapes(layers["Vrstva_1"], NP_FILL)
    chko_shapes = collect_shapes(layers["Vrstva_2"], CHKO_FILL)
    if len(np_shapes) != len(NPS):
        raise SystemExit(f"{len(np_shapes)} NP shapes vs {len(NPS)} names")
    if len(chko_shapes) != len(CHKOS):
        raise SystemExit(f"{len(chko_shapes)} CHKO shapes vs {len(CHKOS)} names")

    # ---- labels → names → shapes
    labels = collect_labels(layers["Vrstva_6"])
    np_labels = match_names([l for l in labels if l["kind"] == "np"], NPS, "np")
    chko_labels = match_names([l for l in labels if l["kind"] == "chko"],
                              CHKOS, "chko")
    np_pairs = pair(np_labels, np_shapes, "np")
    chko_pairs = pair(chko_labels, chko_shapes, "chko")

    def emit(pairs, shapes, kind):
        meta = CATEGORIES[kind]
        recs = []
        for si, lab in sorted(pairs.items(),
                              key=lambda kv: kv[1]["rec"]["short"]):
            s = shapes[si]
            short = lab["rec"]["short"]
            code = f"{kind}-{slug(short)}"
            cx, cy = label_point(s["rings"])
            ov = LABEL_OVERRIDE.get(code)
            if ov:
                pt = nudge_inside(ov, s["rings"])
                if pt:
                    cx, cy = round(pt[0], 1), round(pt[1], 1)
                else:
                    print(f"  warning: override for {code} outside its shape")
            recs.append({
                "code": code,
                "name": short,
                "alt": lab["rec"]["display"],
                "accept": lab["rec"]["accept"],
                "cat": meta["cat"],
                "path": shape_path(s["rings"], 0.2),
                "cx": cx,
                "cy": cy,
                "_raw": lab["raw"],
                "_area": round(s["area"], 1),
            })
        return recs

    nps = emit(np_pairs, np_shapes, "np")
    # NPs read best biggest-first; CHKO stay alphabetical
    nps.sort(key=lambda r: -r["_area"])
    chkos = emit(chko_pairs, chko_shapes, "chko")

    for r in nps + chkos:
        print(f"  pair: {r['_raw']:30s} → {r['name']:24s}"
              f" @ {r['cx']:6.1f} {r['cy']:6.1f}  area={r['_area']}")

    # ---- write js/data.js
    for r in nps + chkos:
        r.pop("_raw"), r.pop("_area")
    js = [
        "// Auto-generated by scripts/build_data.py — do not edit by hand.",
        "// Source: data/CR_VZCHU_2025.svg (velkoplošná zvláště chráněná území",
        "//         ČR, stav 2025: 4 národní parky + 27 CHKO včetně Soutoku).",
        "// Regions keep the source geometry (fill-rule: evenodd — NP Krkonoše",
        "//         has 3 enclave holes; 6 CHKO are multi-fragment).",
        f"window.NATURE_VIEWBOX = {json.dumps(vb)};",
        "window.NATURE = " + json.dumps(
            {"base": base_path, "np": nps, "chko": chkos},
            ensure_ascii=False) + ";",
    ]
    OUT.write_text("\n".join(js) + "\n", encoding="utf-8")

    print(f"wrote {OUT} — {len(nps)} NP + {len(chkos)} CHKO, "
          f"{OUT.stat().st_size} bytes; viewBox {vb}")


if __name__ == "__main__":
    main()
