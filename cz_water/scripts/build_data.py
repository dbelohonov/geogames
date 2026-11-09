#!/usr/bin/env python3
"""Generátor js/data.js z vektorové mapy vodstva ČR.

Zdroje:
- data/07-vodstvo.svg — vektorová mapa z Tematického atlasu České republiky
  (Masarykova univerzita, PedF, J. Svobodova; is.muni.cz), vrstvy: silueta
  státu, říční síť (modré tahy), vodní plochy (modré výplně) a popisky.
  Z ní pochází veškerá geometrie řek a silueta — přesné vektory, žádná
  rasterizace.
- Šest nádrží, které atlas nekreslí (Fláje, Přísečnice, Hněvkovice, Římov,
  Březová, Josefov Důl — doplňují seznam 26 nádrží odsouhlasený podle
  dřívější mapy top-25), je umístěno ručně jako mini-plocha na správném
  toku; Nové Mlýny kreslí atlas jako jednu slitou plochu, která se zde
  dělí na Mušov / Věstonickou / Novomlýnskou zúžením (erozí rastru).

Ptáme se 10 řek (Vltava, Labe, Dyje, Ohře, Morava, Berounka, Sázava,
Jihlava, Mže, Odra) a 26 nádrží dohromady; ostatní řeky atlasu se kreslí
jen jako slabý kontext.

Výstup: window.WATER = { base, ctx, river[], res[] } ve viewBox 517 × ~367.
Spuštění: python3 -I scripts/build_data.py
"""
import json
import math
import os
import re
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "data", "07-vodstvo.svg")
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
silhouette, rivers_raw, res_raw = [], [], []
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
        if st.get("stroke") == "#005ce6":
            rivers_raw.append({"d": d, "m": m})
        elif st.get("fill") == "#ffffbe":   # country fill (legend: pale yellow)
            silhouette.append({"d": d, "m": m})
        elif st.get("fill") == "#0070ff":
            res_raw.append({"d": d, "m": m})
    stack.append(m)
    for ch in el:
        walk(ch, st)
    stack.pop()


walk(tree.getroot(), {})


def xf(polys, m):
    a, b, c, d, e, f = m
    return [[(a*x + c*y + e, b*x + d*y + f) for x, y in p] for p in polys]


sil = [p for ps in silhouette for p in xf(flatten(ps["d"]), ps["m"])]
# the atlas tiles the country into a dozen regional polygons with mixed
# windings — their union is rasterized and re-contoured below (contour_ms)

riv = []
for r in rivers_raw:
    for p in xf(flatten(r["d"]), r["m"]):
        riv.append(p)
res_sub = []
for r in res_raw:
    for p in xf(flatten(r["d"]), r["m"]):
        res_sub.append(p)
print(f"atlas: {len(sil)} silhouette tiles, {len(riv)} river polylines, "
      f"{len(res_sub)} water subpaths")

# ---- which polyline belongs to which asked river ---------------------------
# (read off the atlas overlay: path index in `riv` order = document order)
ASKED = {
    "vltava": [1],       # path 1.0
    "labe": [0],         # path 0.0
    "ohre": [2],         # path 1.1
    "berounka": [3],     # path 2.0
    "mze": [4],          # path 2.1
    "sazava": [20],      # path 6.1
    "dyje": [26],        # path 8.1
    "jihlava": [27],     # path 8.2
    "morava": [29],      # path 9.1
    "odra": [33, 31],    # paths 11.1 + 10.1
}
# verify the indices against bboxes so a re-download can't silently miswire
# bboxes in the transformed (final) user units
EXPECT = {
    "vltava": (140.96, 164.92, 207.73, 379.78),
    "labe": (165.46, 97.46, 319.06, 199.76),
    "ohre": (27.16, 139.76, 175.56, 198.36),
    "mze": (55.76, 232.36, 116.46, 241.26),
    "berounka": (116.76, 201.86, 198.06, 237.96),
    "sazava": (197.86, 219.16, 280.66, 244.66),
    "jihlava": (280.66, 275.36, 387.66, 334.66),
    "dyje": (312.06, 334.16, 415.06, 367.76),
    "morava": (403.26, 211.96, 457.26, 368.26),
    "odra": (449.66, 195.96, 508.46, 212.46),
}


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return (min(xs), min(ys), max(xs), max(ys))


asked_polys = {}
for code, idxs in ASKED.items():
    polys = [riv[i] for i in idxs]
    bb = bbox(polys[0])
    ex = EXPECT[code]
    assert all(abs(bb[k] - ex[k]) < 1.5 for k in range(4)), (code, bb, ex)
    asked_polys[code] = polys
ctx_polys = [p for i, p in enumerate(riv)
             if not any(i in v for v in ASKED.values())]

# ---- reservoirs -------------------------------------------------------------
# the anchor/hand/label tables were read off an untransformed dump of the
# same file: the outer <g translate(-7.84 -7.84)> is applied at use time
TR = -7.84


def sub_at(cx, cy, tol=1.0):
    for i, p in enumerate(res_sub):
        b = bbox(p)
        if b[0] - tol <= cx <= b[2] + tol and b[1] - tol <= cy <= b[3] + tol:
            return i
    raise KeyError((cx, cy))


RES_SRC = {   # code -> (subpath anchor point, name, extra accepts)
    "lipno": ((185.6, 376.5), "Lipno", ["Lipno I"]),
    "orlik": ((195.4, 289.9), "Orlík", []),
    "slapy": ((204.9, 246.5), "Slapy", []),
    "svihov": ((269.5, 251.5), "Švihov", ["Želivka"]),
    "hnevkovice": (None, "Hněvkovice", []),
    "rimov": (None, "Římov", []),
    "vranov": ((322.7, 343.7), "Vranov", []),
    # the atlas draws the whole Nové Mlýny cascade as one water body with
    # one label — one quiz unit, with the three basin names accepted
    "novemlyny": ((395.0, 344.4), "Nové Mlýny",
                  ["Novomlýnská", "Věstonická", "Mušov",
                   "Novomlýnská nádrž", "Věstonická nádrž",
                   "Mušovská nádrž"]),
    "dalesice": ((346.6, 311.6), "Dalešice", []),
    "vir": ((361.6, 258.7), "Vír", []),
    "sec": ((309.5, 230.4), "Seč", []),
    "nechranice": ((123.0, 170.4), "Nechranice", []),
    "flaje": (None, "Fláje", []),
    "prisecnice": (None, "Přísečnice", []),
    "jesenice": ((46.0, 209.2), "Jesenice", []),
    "hracholusky": ((100.2, 243.4), "Hracholusky", []),
    "brezova": (None, "Březová", []),
    "rozkos": ((339.0, 159.3), "Rozkoš", []),
    "slezska-harta": ((459.4, 210.1), "Slezská Harta", []),
    "kruzberk": ((469.0, 217.6), "Kružberk", []),
    "zermanice": ((540.6, 223.0), "Žermanice", []),
    "terlicko": ((538.3, 227.8), "Terlicko", []),
    "sance": ((538.2, 256.4), "Šance", []),
    "josefov-dul": (None, "Josefov Důl", ["Josefův Důl"]),
}
# hand-placed mini shapes for reservoirs the atlas does not draw
# (position on the right stream, checked against the reveal screenshot)
HAND = {
    "flaje": (149.0, 121.0), "prisecnice": (139.0, 127.0),
    "hnevkovice": (197.5, 261.5), "rimov": (210.5, 333.0),
    "brezova": (76.0, 177.0), "josefov-dul": (233.5, 88.0),
}


def mini_blob(cx, cy):
    rx, ry = 2.2, 1.3
    return [(cx + rx*math.cos(t), cy + ry*math.sin(t))
            for t in [i*math.pi/4 for i in range(8)]]


def contour_ms(mask, w, h):
    """Marching squares: boundary of a solid mask as an ordered loop."""
    def add(p, q):
        i = len(segs)
        segs.append((p, q))
        idx.setdefault(p, []).append(i)
        idx.setdefault(q, []).append(i)

    segs, idx = [], {}
    for y in range(h - 1):
        row = y * w
        for x in range(w - 1):
            c = ((mask[row + x] << 3) | (mask[row + x + 1] << 2)
                 | (mask[row + w + x] << 1) | mask[row + w + x + 1])
            if c in (0, 15):
                continue
            T, R = (x + .5, y), (x + 1, y + .5)
            B, L = (x + .5, y + 1), (x, y + .5)
            if c in (1, 14):
                add(R, B)
            elif c in (2, 13):
                add(L, B)
            elif c in (3, 12):
                add(L, R)
            elif c in (4, 11):
                add(T, R)
            elif c in (5, 10):
                add(T, B)
            elif c in (7, 8):
                add(L, T)
            elif c == 6:
                add(L, T)
                add(R, B)
            elif c == 9:
                add(T, R)
                add(L, B)
    used = [False] * len(segs)
    loops = []
    for i0 in range(len(segs)):
        if used[i0]:
            continue
        used[i0] = True
        p, q = segs[i0]
        path, cur, prev = [p, q], q, p
        while True:
            # ve zúženinách se potkávají čtyři konce úseček: pokračuj rovně
            bestj, bs, bo = None, -1e9, None
            for j in idx.get(cur, ()):
                if used[j]:
                    continue
                a, b = segs[j]
                o = b if a == cur else a
                s = ((o[0] - cur[0]) * (cur[0] - prev[0])
                     + (o[1] - cur[1]) * (cur[1] - prev[1]))
                if s > bs:
                    bestj, bs, bo = j, s, o
            if bestj is None:
                break
            used[bestj] = True
            prev, cur = cur, bo
            path.append(cur)
            if cur == path[0]:
                break
        loops.append(path)
    opens = [p for p in loops if p[0] != p[-1]]
    closed = [p for p in loops if p[0] == p[-1]]
    while opens:
        P = opens.pop(0)
        if not opens:
            closed.append(P)
            break
        best = (math.dist(P[0], P[-1]), -1, 0, 0)
        for i, Q in enumerate(opens):
            for pe in (0, -1):
                for qe in (0, -1):
                    d = math.dist(P[pe], Q[qe])
                    if d < best[0]:
                        best = (d, i, pe, qe)
        d, i, pe, qe = best
        if i < 0:
            closed.append(P)
            continue
        Q = opens.pop(i)
        if pe == 0:
            P = P[::-1]
        Q = Q if qe == 0 else Q[::-1]
        opens.append(P + Q[1:])
    return max(closed, key=len)


# ---- country silhouette -----------------------------------------------------
sil.sort(key=lambda p: -len(p))
country = path_closed_i(simplify_closed(sil[0] + [sil[0][0]], 0.4))
print("country ring pts:", len(sil[0]))

res_polys = {}
for code, (anchor, name, extra) in RES_SRC.items():
    if code in HAND:
        res_polys[code] = [mini_blob(HAND[code][0] + TR, HAND[code][1] + TR)]
    else:
        i = sub_at(anchor[0] + TR, anchor[1] + TR)
        res_polys[code] = [simplify_closed(res_sub[i] + [res_sub[i][0]], 0.25)]

# ---- emit -------------------------------------------------------------------
VB_W = 517.2
K = VB_W / 577.62243
VB_H = round(409.85852 * K, 1)


def sc(pts):
    return [(round(x * K, 1), round(y * K, 1)) for x, y in pts]


def path_open(pts):
    return "M " + " L ".join(f"{x} {y}" for x, y in sc(pts))


def path_closed(pts):
    return path_open(pts) + " Z"


RIVER_NAMES = {"vltava": "Vltava", "labe": "Labe", "dyje": "Dyje",
               "ohre": "Ohře", "morava": "Morava", "berounka": "Berounka",
               "sazava": "Sázava", "jihlava": "Jihlava", "mze": "Mže",
               "odra": "Odra"}
# label anchors in atlas units (tuned against the reveal-all screenshot)
LABELS = {
    "vltava": (186, 292), "labe": (248, 172), "dyje": (348, 357),
    "ohre": (84, 150), "morava": (430, 272), "berounka": (152, 224),
    "sazava": (240, 231), "jihlava": (330, 296), "mze": (68, 236),
    "odra": (497, 198),
    "lipno": (178, 372), "orlik": (181, 272), "slapy": (212, 243),
    "svihov": (262, 246), "hnevkovice": (204, 262), "rimov": (216, 336),
    "vranov": (314, 340), "novemlyny": (399, 352), "dalesice": (338, 306),
    "vir": (349, 253), "sec": (303, 224), "nechranice": (116, 163),
    "flaje": (149, 116), "prisecnice": (136, 124), "jesenice": (42, 205),
    "hracholusky": (93, 243), "brezova": (78, 172), "rozkos": (332, 150),
    "slezska-harta": (447, 196), "kruzberk": (462, 213),
    "zermanice": (533, 219), "terlicko": (545, 227),
    "sance": (533, 253), "josefov-dul": (238, 84),
}

recs_river = []
for code in sorted(ASKED, key=lambda c: RIVER_NAMES[c]):
    name = RIVER_NAMES[code]
    polys = [rdp(p, 0.15) for p in asked_polys[code]]
    recs_river.append({
        "code": code, "name": name, "alt": "řeka " + name,
        "accept": [name, "řeka " + name], "cat": "řeka",
        "path": " ".join(path_open(p) for p in polys),
        "cx": round((LABELS[code][0] + TR) * K, 1),
        "cy": round((LABELS[code][1] + TR) * K, 1),
    })
recs_res = []
for code, (anchor, name, extra) in sorted(RES_SRC.items(), key=lambda kv: kv[1][1]):
    acc = [name, "VN " + name, "vodní nádrž " + name] + extra
    recs_res.append({
        "code": code, "name": name, "alt": "VN " + name,
        "accept": acc, "cat": "vodní nádrž",
        "path": " ".join(path_closed(p) for p in res_polys[code]),
        "cx": round((LABELS[code][0] + TR) * K, 1),
        "cy": round((LABELS[code][1] + TR) * K, 1),
    })
ctx = [rdp(p, 0.3) for p in ctx_polys if len(p) >= 4]
data = {"base": country,
        "ctx": " ".join(path_open(p) for p in ctx),
        "river": recs_river, "res": recs_res}
js = ("// Auto-generated by scripts/build_data.py — do not edit by hand.\n"
      "// Source: data/07-vodstvo.svg (Česká republika – tematický atlas,\n"
      "//         Masarykova univerzita; river/reservoir geometry as drawn\n"
      "//         there), plus six hand-placed reservoirs the atlas omits.\n"
      f'window.WATER_VIEWBOX = "0 0 {VB_W} {VB_H}";\n'
      f"window.WATER = {json.dumps(data, ensure_ascii=False)};\n")
open(OUT, "w", encoding="utf-8").write(js)
print(f"wrote {OUT}: {len(recs_river)} rivers, {len(recs_res)} reservoirs, "
      f"{len(ctx)} context lines, {os.path.getsize(OUT)} bytes")
