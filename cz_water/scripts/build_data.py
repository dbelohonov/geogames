#!/usr/bin/env python3
"""Generátor js/data.js — silueta z atlasu, řeky z OpenStreetMap.

Zdroje:
- data/07-vodstvo.svg — vektorová mapa z Tematického atlasu České republiky
  (Masarykova univerzita, PedF, J. Svobodova; is.muni.cz), vrstva: silueta
  státu. Odtud pochází podklad mapy.
- data/osm_rivers.json — 24 ptaných řek a říční síť na pozadí z exportu
  vodstva ČR z OpenStreetMap (© přispěvatelé OpenStreetMap, licence ODbL;
  HOT export hotosm_cze_waterways_osm_shp, snapshot 2026-11-03), promítnuté
  do souřadnic atlasu. JSON generuje scripts/extract_osm.py ze shapefilu
  v images/hotosm_cze_waterways_osm_shp/ (neverzionováno, viz kořenový
  .gitignore); bez shapefilu ho nelze znovu vytvořit, proto je JSON uložený
  v repozitáři.

Ptáme se 24 řek (Vltava, Labe, Morava, Ohře, Sázava, Dyje, Jihlava, Svratka,
Jizera, Lužnice, Berounka, Odra, Otava, Opava, Radbuza, Chrudimka, Úhlava,
Želivka, Mže, Svitava, Úpa, Olše, Bečva, Vlára).

Výstup: window.WATER = { base, ctx, river[] } ve viewBox 517 × ~367.
Spuštění: python3 -I scripts/build_data.py
"""
import json
import math
import os
import re
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "data", "07-vodstvo.svg")
OSM_JSON = os.path.join(HERE, "..", "data", "osm_rivers.json")
OUT = os.path.join(HERE, "..", "js", "data.js")

NS = "{http://www.w3.org/2000/svg}"
TOKEN = re.compile(r"([MmLlHhVvCcSsQqTtZzAa])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


# ---- SVG path flattening (shared parser, cz_nature/cz_geomorphology) -------
def flatten(d, samples=4):
    toks = []
    for m in TOKEN.finditer(d):
        toks.append(m.group(1) if m.group(1) else float(m.group(2)))
    polys, cur = [], []
    x = y = sx = sy = 0.0
    prev_ctrl = None
    cmd = None
    i = 0

    def next_xy(i, rel):
        nx, ny = toks[i], toks[i + 1]
        if rel:
            nx, ny = x + nx, y + ny
        return nx, ny, i + 2

    def bez(p0, p1, p2, p3):
        pts = []
        for k in range(1, samples + 1):
            t = k / samples
            u = 1 - t
            pts.append((u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0],
                        u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1]))
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
        rel = cmd.islower()
        C = cmd.upper()
        if C == "M":
            x, y, i = next_xy(i, rel)
            sx, sy = x, y
            cur = [(x, y)]
            cmd = "L" if cmd == "M" else "l"
        elif C == "L":
            x, y, i = next_xy(i, rel)
            cur.append((x, y))
        elif C == "H":
            x = toks[i] + (x if rel else 0.0)
            i += 1
            cur.append((x, y))
        elif C == "V":
            y = toks[i] + (y if rel else 0.0)
            i += 1
            cur.append((x, y))
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
                p1 = (x + 2/3*(x1-x), y + 2/3*(y1-y))
                p2 = (xe + 2/3*(x1-xe), ye + 2/3*(y1-ye))
                prev_ctrl = None
            cur.extend(bez((x, y), p1, p2, (xe, ye)))
            x, y = xe, ye
        elif C in ("S", "T"):
            xe, ye, i = next_xy(i, rel)
            if C == "S":
                x2, y2, i = next_xy(i, rel)
                p1 = (2*x - prev_ctrl[0], 2*y - prev_ctrl[1]) if prev_ctrl else (x, y)
                p2 = (x2, y2)
                prev_ctrl = (x2, y2)
            else:
                raise ValueError("T not expected")
            cur.extend(bez((x, y), p1, p2, (xe, ye)))
            x, y = xe, ye
        else:
            raise ValueError(f"unsupported {cmd}")
    if cur:
        polys.append(cur)
    return [p for p in polys if len(p) >= 2]


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    ax, ay = pts[0]
    bx, by = pts[-1]
    dx, dy = bx - ax, by - ay
    ln = math.hypot(dx, dy) or 1e-9
    best, bi = -1.0, -1
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = abs(dy * (px - ax) - dx * (py - ay)) / ln
        if d > best:
            best, bi = d, i
    if best <= eps:
        return [pts[0], pts[-1]]
    return rdp(pts[:bi + 1], eps)[:-1] + rdp(pts[bi:], eps)


def path_closed_i(pts):
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z"


def simplify_closed(loop, eps):
    i1 = max(range(len(loop)),
             key=lambda i: (loop[i][0] - loop[0][0]) ** 2
             + (loop[i][1] - loop[0][1]) ** 2)
    a = rdp(loop[:i1 + 1], eps)
    b = rdp(loop[i1:] + [loop[0]], eps)
    return a[:-1] + b[:-1]


# ---- parse the atlas svg ----------------------------------------------------
def parse_matrix(val):
    m = re.match(r"matrix\(([^)]+)\)", val)
    if m:
        return tuple(float(x) for x in m.group(1).replace(",", " ").split())
    m = re.match(r"translate\(([^)]+)\)", val)
    if m:
        p = [float(x) for x in m.group(1).replace(",", " ").split()]
        return (1, 0, 0, 1, p[0], p[1] if len(p) > 1 else 0)
    return (1, 0, 0, 1, 0, 0)


def mul(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1*a2 + c1*b2, b1*a2 + d1*b2, a1*c2 + c1*d2, b1*c2 + d1*d2,
            a1*e2 + c1*f2 + e1, b1*e2 + d1*f2 + f1)


tree = ET.parse(SRC)
silhouette = []
stack = [(1, 0, 0, 1, 0, 0)]


def walk(el, style):
    tr = el.get("transform")
    m = mul(stack[-1], parse_matrix(tr)) if tr else stack[-1]
    st = dict(style)
    for k in ("fill", "stroke", "stroke-width"):
        if el.get(k):
            st[k] = el.get(k)
    tag = el.tag.replace(NS, "")
    if tag == "path":
        d = el.get("d")
        if st.get("fill") == "#ffffbe":   # country fill (legend: pale yellow)
            silhouette.append({"d": d, "m": m})
    stack.append(m)
    for ch in el:
        walk(ch, st)
    stack.pop()


walk(tree.getroot(), {})


def xf(polys, m):
    a, b, c, d, e, f = m
    return [[(a*x + c*y + e, b*x + d*y + f) for x, y in p] for p in polys]


sil = [p for ps in silhouette for p in xf(flatten(ps["d"]), ps["m"])]
# silueta je jeden uzavřený tah; menší subpathy (ostrovy/exklávky) zahodíme
print(f"atlas: {len(sil)} silhouette tiles")

# the label anchors below were read off an untransformed dump of the same
# file: the outer <g translate(-7.84 -7.84)> is applied at use time
TR = -7.84


# ---- country silhouette -----------------------------------------------------
sil.sort(key=lambda p: -len(p))
print("country ring pts:", len(sil[0]))

# ---- emit -------------------------------------------------------------------
VB_W = 517.2
K = VB_W / 577.62243
VB_H = round(409.85852 * K, 1)
country = simplify_closed(sil[0] + [sil[0][0]], 0.4)


def sc(pts):
    return [(round(x * K, 1), round(y * K, 1)) for x, y in pts]


def path_open(pts):
    return "M " + " L ".join(f"{x} {y}" for x, y in sc(pts))


def path_closed(pts):
    return path_open(pts) + " Z"


def fmt_vb(pts):
    """cesta z bodů, které UŽ jsou ve viewBox (data z OSM)"""
    return "M " + " L ".join(f"{x:g} {y:g}" for x, y in pts)


# label anchors in atlas units (tuned against the reveal-all screenshot)
LABELS = {
    "vltava": (186, 292), "labe": (248, 172), "dyje": (348, 357),
    "ohre": (84, 150), "morava": (430, 272), "berounka": (152, 224),
    "sazava": (240, 231), "jihlava": (330, 296), "mze": (68, 236),
    "odra": (497, 198),
}
# ruční přepsání automaticky umístěných popisků nových řek (viewBox jednotky)
LABELS_VB = {}


# ---- rivers from the OSM extraction ------------------------------------------
osm = json.load(open(OSM_JSON, encoding="utf-8"))
assert osm["meta"]["viewbox"] == [VB_W, VB_H], "osm_rivers.json má jiný viewBox"


def chain_len(ch):
    return sum(math.dist(a, b) for a, b in zip(ch, ch[1:]))


def point_at(ch, t):
    """bod v části t délky + jednotková normála (proti směru toku doprava)"""
    L = chain_len(ch)
    target = t * L
    acc = 0.0
    for a, b in zip(ch, ch[1:]):
        d = math.dist(a, b)
        if acc + d >= target and d > 1e-9:
            f = (target - acc) / d
            p = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            n = ((b[1] - a[1]) / d, -(b[0] - a[0]) / d)
            return p, n
        acc += d
    a, b = ch[-2], ch[-1]
    d = math.dist(a, b) or 1e-9
    return ch[-1], ((b[1] - a[1]) / d, -(b[0] - a[0]) / d)


def auto_label(chains, taken):
    """kotva popisku: vedle nejdelšího řetězce, na straně dál od ostatních"""
    dom = max(chains, key=chain_len)
    best = None
    for t in (0.4, 0.55, 0.3, 0.7, 0.2):
        p, n = point_at(dom, t)
        for side in (1, -1):
            c = (p[0] + side * 7.0 * n[0], p[1] + side * 7.0 * n[1])
            s = min((math.dist(c, q) for q in taken), default=99.0)
            if best is None or s > best[0]:
                best = (s, c)
    return (round(best[1][0], 1), round(best[1][1], 1))


taken = [(((x + TR) * K), ((y + TR) * K)) for x, y in LABELS.values()]
recs_river = []
for r in sorted(osm["rivers"], key=lambda r: r["name"]):
    code = r["code"]
    name = r["name"]
    if code in LABELS:
        cx = round((LABELS[code][0] + TR) * K, 1)
        cy = round((LABELS[code][1] + TR) * K, 1)
    elif code in LABELS_VB:
        cx, cy = LABELS_VB[code]
    else:
        cx, cy = auto_label(r["chains"], taken)
        taken.append((cx, cy))
    recs_river.append({
        "code": code, "name": name, "alt": "řeka " + name,
        "accept": [name, "řeka " + name], "cat": "řeka",
        "path": " ".join(fmt_vb(ch) for ch in r["chains"]),
        "cx": cx, "cy": cy,
    })
data = {"base": path_closed(country),
        "ctx": " ".join(fmt_vb(ch) for ch in osm["ctx"]),
        "river": recs_river}
js = ("// Auto-generated by scripts/build_data.py — do not edit by hand.\n"
      "// Sources: data/07-vodstvo.svg (Česká republika – tematický atlas,\n"
      "//          Masarykova univerzita — silhouette) and\n"
      "//          data/osm_rivers.json (rivers; © OpenStreetMap contributors,\n"
      "//          ODbL — HOT OSM waterways export, see scripts/extract_osm.py).\n"
      f'window.WATER_VIEWBOX = "0 0 {VB_W} {VB_H}";\n'
      f"window.WATER = {json.dumps(data, ensure_ascii=False)};\n")
open(OUT, "w", encoding="utf-8").write(js)
print(f"wrote {OUT}: {len(recs_river)} rivers, "
      f"{len(osm['ctx'])} context lines, {os.path.getsize(OUT)} bytes")
