#!/usr/bin/env python3
"""Extraktor říční sítě z OSM shapefilu do souřadnic herní mapy.

Zdroj: images/hotosm_cze_waterways_osm_shp/ (HOT OSM export vodstva ČR,
snapshot 2026-11-03; © OpenStreetMap contributors, ODbL). Složka je stejně
jako ostatní referenční podklady v /images/ verzionovaná jen lokálně —
viz .gitignore v kořeni repozitáře.

Skript:
1. vybere ze shapefilu segmenty 24 ptaných řek (podle jména a jeho
   jazykových variant, waterway river/stream) a zbytek sítě waterway=river
   jako kontext,
2. sešije segmenty každé řeky do souvislých linií a přes velké nádrže je
   propojí rovnou čarou (OSM řeku přes hladinu nekreslí),
3. napasuje kubické zobrazení (zem. šířka/délka → viewBox atlasu) metodou
   ICP na deset řek, které atlas kreslí také (startovní aproximace je
   kvadratický fit na setrvání; výsledek se kontroluje proti atlasu),
4. promítne, ořízne siluetou státu a zjednoduší RDP,
5. zapíše data/osm_rivers.json, který čte build_data.py.

Spuštění: python3 -I scripts/extract_osm.py   (potřebuje shapefile v images/)
"""
import json
import math
import os
import re
import struct
import unicodedata
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SHP_DIR = os.path.join(HERE, "..", "..", "images", "hotosm_cze_waterways_osm_shp")
SRC = os.path.join(HERE, "..", "data", "07-vodstvo.svg")
OUT = os.path.join(HERE, "..", "data", "osm_rivers.json")

VB_W = 517.2
K = VB_W / 577.62243          # walk-space atlasu → viewBox hry
VB_H = round(409.85852 * K, 1)

NS = "{http://www.w3.org/2000/svg}"
TOKEN = re.compile(r"([MmLlHhVvCcSsQqTtZzAa])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


# ---- SVG path flattening (stejný parser jako build_data.py) -----------------
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


def simplify_closed(loop, eps):
    i1 = max(range(len(loop)),
             key=lambda i: (loop[i][0] - loop[0][0]) ** 2
             + (loop[i][1] - loop[0][1]) ** 2)
    a = rdp(loop[:i1 + 1], eps)
    b = rdp(loop[i1:] + [loop[0]], eps)
    return a[:-1] + b[:-1]


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


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return (min(xs), min(ys), max(xs), max(ys))


def parse_atlas():
    """siluetu, říční síť a vodu z atlasového SVG (walk space)."""
    tree = ET.parse(SRC)
    silhouette, rivers_raw = [], []
    stack = [(1, 0, 0, 1, 0, 0)]

    def walk(el, style):
        tr = el.get("transform")
        m = mul(stack[-1], parse_matrix(tr)) if tr else stack[-1]
        st = dict(style)
        for k in ("fill", "stroke", "stroke-width"):
            if el.get(k):
                st[k] = el.get(k)
        if el.tag.replace(NS, "") == "path":
            d = el.get("d")
            if st.get("stroke") == "#005ce6":
                rivers_raw.append({"d": d, "m": m})
            elif st.get("fill") == "#ffffbe":
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
    riv = [p for r in rivers_raw for p in xf(flatten(r["d"]), r["m"])]
    return sil, riv


# ---- atlas: deset řek pro ICP + silueta -------------------------------------
# (stejné indexy a kontrolní bboxy jako v build_data.py — cesty v pořadí
# dokumentu; slouží jen jako kalibrační cíl, geometrie řek jde z OSM)
ASKED = {
    "vltava": [1], "labe": [0], "ohre": [2], "berounka": [3], "mze": [4],
    "sazava": [20], "dyje": [26], "jihlava": [27], "morava": [29],
    "odra": [33, 31],
}
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


# ---- 24 ptaných řek: jméno a jeho varianty v OSM ----------------------------
# klíč = diakritikou zbavené lowercase jméno z DBF; zahrnuty jsou jazykové
# varianty a pohraniční úseky (Thaya/Dyje, Olza/Olše, …), naopak NE jiné
# řeky stejného základu (Malé Labe, Moravská Dyje, Malá Bečva, …)
RIVERS = {
    # Vltava včetně pramenných toků (Teplá i Studená Vltava — atlas kreslí
    # Vltavu od soutoku u Lipna přes Studenou; kilometráž 430 km platí od
    # pramene Teplé Vltavy)
    "vltava":    ("Vltava",    ["vltava", "tepla vltava", "studena vltava",
                                "kalte moldau"]),
    "labe":      ("Labe",      ["labe", "labe / elbe", "elbe"]),
    "morava":    ("Morava",    ["morava", "march / morava"]),
    "ohre":      ("Ohře",      ["ohre", "eger"]),
    "sazava":    ("Sázava",    ["sazava"]),
    "dyje":      ("Dyje",      ["dyje", "thaya / dyje", "thaya"]),
    "jihlava":   ("Jihlava",   ["jihlava"]),
    "svratka":   ("Svratka",   ["svratka"]),
    "jizera":    ("Jizera",    ["jizera", "jizera (ceska vetev)"]),
    "luznice":   ("Lužnice",   ["luznice"]),
    "berounka":  ("Berounka",  ["berounka"]),
    "odra":      ("Odra",      ["odra"]),
    "otava":     ("Otava",     ["otava"]),
    "opava":     ("Opava",     ["opava", "opava / opawa"]),
    "radbuza":   ("Radbuza",   ["radbuza"]),
    "chrudimka": ("Chrudimka", ["chrudimka"]),
    "uhlava":    ("Úhlava",    ["uhlava"]),
    "zelivka":   ("Želivka",   ["zelivka"]),
    "mze":       ("Mže",       ["mze"]),
    "svitava":   ("Svitava",   ["svitava"]),
    "upa":       ("Úpa",       ["upa"]),
    "olse":      ("Olše",      ["olse", "olse / olza", "olza", "olza - olse"]),
    "becva":     ("Bečva",     ["becva", "roznovska becva", "vsetinska becva"]),
    "vlara":     ("Vlára",     ["vlara"]),
}
VARIANT2CODE = {v: code for code, (_, vs) in RIVERS.items() for v in vs}
ASKED_WW = {"river", "stream"}      # canal/ditch/weir… do ptaných řek nepatří


def strip_acc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


# ---- shapefile (SHP/DBF/SHX) parser ------------------------------------------
def dbf_open(path):
    f = open(path, "rb")
    hdr = f.read(32)
    nrec, hlen, rlen = struct.unpack("<IHH", hdr[4:12])
    f.seek(32)
    fields = []
    while True:
        fd = f.read(32)
        if fd[0:1] == b"\x0d" or not fd:
            break
        fields.append((fd[:11].split(b"\0")[0].decode(), fd[16]))
    offs = {}
    o = 1
    for name, ln in fields:
        offs[name] = (o, ln)
        o += ln
    f.seek(hlen)
    return f, nrec, rlen, offs


def shx_index(path):
    with open(path, "rb") as f:
        f.seek(100)
        data = f.read()
    return [struct.unpack(">ii", data[i:i + 8]) for i in range(0, len(data), 8)]


def shp_geom(f, off_words, len_words):
    f.seek(off_words * 2 + 8)         # +8 = hlavička záznamu
    rec = f.read(len_words * 2)
    shptype, = struct.unpack("<i", rec[:4])
    nparts, npoints = struct.unpack("<ii", rec[36:44])
    parts = struct.unpack(f"<{nparts}i", rec[44:44 + 4 * nparts])
    ps = 44 + 4 * nparts
    pts = struct.unpack(f"<{npoints * 2}d", rec[ps:ps + 16 * npoints])
    rings = []
    for pi in range(nparts):
        s = parts[pi]
        e = parts[pi + 1] if pi + 1 < nparts else npoints
        rings.append([(pts[2 * k], pts[2 * k + 1]) for k in range(s, e)])
    return shptype, rings


def load_lines():
    """→ (asked: code→[segmenty], ctx: [segmenty]) v lon/lat."""
    f, nrec, rlen, offs = dbf_open(os.path.join(SHP_DIR, "waterways_lines.dbf"))
    no, nl = offs["name"]
    wo, wl = offs["waterway"]
    asked_i = {}
    ctx_i = []
    data = f.read()
    f.close()
    for i in range(nrec):
        r = data[i * rlen:(i + 1) * rlen]
        ww = r[wo:wo + wl].decode("utf-8", "replace").strip()
        nm = r[no:no + nl].decode("utf-8", "replace").strip()
        code = VARIANT2CODE.get(strip_acc(nm).lower()) if nm else None
        if code and ww in ASKED_WW:
            asked_i.setdefault(code, []).append(i)
        elif ww == "river" and not code:
            ctx_i.append(i)          # kontext: všechny waterway=river mimo ptané
    shx = shx_index(os.path.join(SHP_DIR, "waterways_lines.shx"))
    asked = {}
    ctx = []
    with open(os.path.join(SHP_DIR, "waterways_lines.shp"), "rb") as g:
        for code, idxs in asked_i.items():
            segs = []
            for i in idxs:
                st, rings = shp_geom(g, *shx[i])
                if st == 3:
                    segs.extend(rings)
            asked[code] = segs
        for i in ctx_i:
            st, rings = shp_geom(g, *shx[i])
            if st == 3:
                ctx.extend(rings)
    return asked, ctx


def load_reservoirs():
    """nádrže (water=reservoir) s bboxem a prstenci — na mosty přes hladiny."""
    f, nrec, rlen, offs = dbf_open(os.path.join(SHP_DIR, "waterways_polygons.dbf"))
    no, nl = offs["name"]
    wo, wl = offs["water"]
    keep = []
    for i in range(nrec):
        r = f.read(rlen)
        ww = r[wo:wo + wl].decode("utf-8", "replace").strip()
        if ww != "reservoir":
            continue
        nm = r[no:no + nl].decode("utf-8", "replace").strip()
        keep.append((i, nm))
    f.close()
    shx = shx_index(os.path.join(SHP_DIR, "waterways_polygons.shx"))
    out = []
    with open(os.path.join(SHP_DIR, "waterways_polygons.shp"), "rb") as g:
        for i, nm in keep:
            st, rings = shp_geom(g, *shx[i])
            if st != 5:
                continue
            lon = [p[0] for ring in rings for p in ring]
            lat = [p[1] for ring in rings for p in ring]
            # plocha v deg^2 (přesný výpočet by bral v úvahu šířku, pro filtr stačí)
            span = (max(lat) - min(lat)) * (max(lon) - min(lon))
            if span < 2e-5:            # ~ menší než ~0,2 km² — můstky netřeba
                continue
            out.append({"name": nm, "rings": rings,
                        "bbox": (min(lon), min(lat), max(lon), max(lat))})
    return out


# ---- sešívání segmentů do linií ----------------------------------------------
def nodekey(p):
    return (round(p[0], 6), round(p[1], 6))


def stitch(segs):
    """Spojí segmenty sdílející koncové body do co nejdelších linií."""
    segs = [s for s in segs if len(s) >= 2]
    adj = {}
    for si, s in enumerate(segs):
        for end in (0, -1):
            adj.setdefault(nodekey(s[end]), []).append((si, end))
    used = [False] * len(segs)
    chains = []

    def walk_from(si, end):
        """projde řetězec od segmentu si (end=0: začíná jeho začátkem)"""
        used[si] = True
        chain = list(segs[si] if end == 0 else segs[si][::-1])
        while True:
            k = nodekey(chain[-1])
            nxt = [(j, e) for j, e in adj.get(k, ()) if not used[j]]
            if not nxt:
                break
            j, e = nxt[0]
            used[j] = True
            sj = segs[j] if e == 0 else segs[j][::-1]
            chain.extend(sj[1:] if nodekey(sj[0]) == k else sj)
        return chain

    for si in range(len(segs)):        # nejdřív od volných konců (degree 1)
        if used[si]:
            continue
        for end in (0, -1):
            if len(adj.get(nodekey(segs[si][end]), ())) == 1:
                chains.append(walk_from(si, end))
                break
    for si in range(len(segs)):        # pak uzavřené cykly (stará ramena)
        if used[si]:
            continue
        chains.append(walk_from(si, 0))
    return chains


def chain_len_km(ch):
    d = 0.0
    for a, b in zip(ch, ch[1:]):
        d += math.hypot((b[0] - a[0]) * 71.0, (b[1] - a[1]) * 111.0)
    return d


def chain_len_u(ch):
    return sum(math.dist(a, b) for a, b in zip(ch, ch[1:]))


def drop_strays(chains, margin=20.0):
    """Zahodí stejnojmenné potoky z jiných povodí (v OSM jich tak pár je —
    např. Bečva u Bohumína, Lužnice v Krušných horách): nechá jen řetězce,
    jejichž bbox protíná bbox nejdelšího řetězce zvětšený o margin."""
    if len(chains) <= 1:
        return chains
    dom = max(chains, key=chain_len_u)
    dx0, dy0, dx1, dy1 = bbox(dom)
    out = []
    for ch in chains:
        x0, y0, x1, y1 = bbox(ch)
        if (x0 <= dx1 + margin and x1 >= dx0 - margin
                and y0 <= dy1 + margin and y1 >= dy0 - margin):
            out.append(ch)
    return out


def near_reservoir(p, reservoirs, pad=0.01):
    for ri, r in enumerate(reservoirs):
        b = r["bbox"]
        if b[0] - pad <= p[0] <= b[2] + pad and b[1] - pad <= p[1] <= b[3] + pad:
            for ring in r["rings"]:
                if any(math.hypot((q[0] - p[0]) * 71, (q[1] - p[1]) * 111) < 1.2
                       for q in ring):
                    return ri
    return None


def bridge(chains, reservoirs):
    """Spojí konce linií: (a) blízko u sebe, (b) přes stejnou nádrž."""
    changed = True
    while changed:
        changed = False
        ends = []      # (chain index, which end 0/-1, point)
        for ci, ch in enumerate(chains):
            if not ch:
                continue               # už spojený řetězec
            ends.append((ci, 0, ch[0]))
            ends.append((ci, -1, ch[-1]))
        if len(ends) < 2:
            break
        # (a) nejbližší pár do ~2,5 km
        best = (2.5, None, None)
        for i in range(len(ends)):
            for j in range(i + 1, len(ends)):
                if ends[i][0] == ends[j][0]:
                    continue
                d = math.hypot((ends[i][2][0] - ends[j][2][0]) * 71,
                               (ends[i][2][1] - ends[j][2][1]) * 111)
                if d < best[0]:
                    best = (d, i, j)
        if best[1] is not None:
            join(chains, ends[best[1]], ends[best[2]])
            changed = True
            continue
        # (b) konce u stejné nádrže (do ~45 km)
        by_res = {}
        for ei, e in enumerate(ends):
            ri = near_reservoir(e[2], reservoirs)
            if ri is not None:
                by_res.setdefault(ri, []).append(ei)
        done = False
        for ri, eis in by_res.items():
            for i in range(len(eis)):
                for j in range(i + 1, len(eis)):
                    a, b = ends[eis[i]], ends[eis[j]]
                    if a[0] == b[0]:
                        continue
                    d = math.hypot((a[2][0] - b[2][0]) * 71,
                                   (a[2][1] - b[2][1]) * 111)
                    if d < 45.0:      # km — přes velké nádrže (Lipno, Orlík…)
                        join(chains, a, b)
                        done = True
                        break
                if done:
                    break
            if done:
                break
        changed = done


def join(chains, a, b):
    """Spojí dva řetězce konci a/b (podle potřeby převrátí), výsledek v a."""
    ci, end, _ = a
    cj, endj, _ = b
    A = chains[ci]
    B = chains[cj]
    if end == -1:
        pass                       # A končí vzadu — dobré
    else:
        A.reverse()                # chceme spoj na konci A
        end = -1
    if endj == 0:
        pass                       # B začíná vpředu — dobré
    else:
        B.reverse()
    chains[ci] = A + B
    chains[cj] = []


# ---- projekce: kubický fit ICP ------------------------------------------------
def basis(lon, lat):
    return [1.0, lon, lat, lon * lon, lon * lat, lat * lat,
            lon ** 3, lon * lon * lat, lon * lat * lat, lat ** 3]


def lstsq(rows, ys):
    k = len(rows[0])
    AtA = [[0.0] * k for _ in range(k)]
    Atb = [0.0] * k
    for r, y in zip(rows, ys):
        for i in range(k):
            Atb[i] += r[i] * y
            for j in range(k):
                AtA[i][j] += r[i] * r[j]
    M = [AtA[i][:] + [Atb[i]] for i in range(k)]
    for c in range(k):
        p = max(range(c, k), key=lambda rr: abs(M[rr][c]))
        M[c], M[p] = M[p], M[c]
        for rr in range(k):
            if rr != c:
                fct = M[rr][c] / M[c][c]
                for cc in range(c, k + 1):
                    M[rr][cc] -= fct * M[c][cc]
    return [M[i][k] / M[i][i] for i in range(k)]


# startovací kvadratická aproximace (prvních 6 koeficientů kubické báze):
# jednorázový fit na centroidy 18 nádrží, které kreslí atlas i OSM, plus tři
# říční soutoky; ICP ji níže doladí na celé říční síti a výsledek se assertuje
SEED = {
    "cx": [-4138.47596, 139.63201, 116.74653, -0.10307, -1.27634, -1.03669],
    "cy": [2363.25136, 3.03877, 26.9825, -0.5093, 0.17503, -1.43657],
}


def nearest_on_polyline(x, y, poly):
    best = (1e18, x, y)
    for i in range(len(poly) - 1):
        ax, ay = poly[i]
        bx, by = poly[i + 1]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0,
            ((x - ax) * dx + (y - ay) * dy) / L2))
        px, py = ax + t * dx, ay + t * dy
        d = (px - x) ** 2 + (py - y) ** 2
        if d < best[0]:
            best = (d, px, py)
    return math.sqrt(best[0]), best[1], best[2]


def fit_icp(atlas_riv, osm_riv):
    cx = SEED["cx"] + [0.0] * 4      # kvadratický seed → kubická báze
    cy = SEED["cy"] + [0.0] * 4
    stats = None
    for it, thresh in enumerate((10, 6, 4, 3, 2, 1.5)):
        ctrl = []
        for code, polys in atlas_riv.items():
            for seg in osm_riv[code]:
                for lon, lat in seg:
                    bq = basis(lon, lat)
                    X = sum(c * b for c, b in zip(cx, bq))
                    Y = sum(c * b for c, b in zip(cy, bq))
                    best = (1e18, X, Y)
                    for poly in polys:
                        cand = nearest_on_polyline(X, Y, poly)
                        if cand[0] < best[0]:
                            best = cand
                    d, nx, ny = best
                    if d < thresh:
                        ctrl.append((lon, lat, nx, ny))
        rows = [basis(lo, la) for lo, la, _, _ in ctrl]
        cx = lstsq(rows, [nx for _, _, nx, _ in ctrl])
        cy = lstsq(rows, [ny for _, _, _, ny in ctrl])
        tot = mx = 0.0
        for lo, la, nx, ny in ctrl:
            bq = basis(lo, la)
            X = sum(c * b for c, b in zip(cx, bq))
            Y = sum(c * b for c, b in zip(cy, bq))
            e = math.hypot(X - nx, Y - ny)
            tot += e * e
            mx = max(mx, e)
        stats = (len(ctrl), math.sqrt(tot / len(ctrl)), mx)
        print(f"  ICP iter {it}: thresh={thresh}u ctrl={stats[0]} "
              f"RMS={stats[1]:.3f}u max={stats[2]:.3f}u")
    return cx, cy, stats


# ---- ořez siluetou -------------------------------------------------------------
class Clipper:
    """ořezává promítnuté linie polygonem státu (ve viewBox)"""
    TOL = 1.5

    def __init__(self, ring):
        self.ring = ring
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        self.b0 = (min(xs), min(ys), max(xs), max(ys))
        self.NB = 512
        self.buckets = [[] for _ in range(self.NB)]
        dy = self.b0[3] - self.b0[1]
        n = len(ring)
        for i in range(n):                      # včetně uzavírací hrany
            (x1, y1), (x2, y2) = ring[i], ring[(i + 1) % n]
            lo = max(0, int((min(y1, y2) - self.b0[1]) / dy * self.NB))
            hi = min(self.NB - 1, int((max(y1, y2) - self.b0[1]) / dy * self.NB))
            for b in range(lo, hi + 1):
                self.buckets[b].append((x1, y1, x2, y2))
        self._dy = dy

    def inside(self, x, y):
        if not (self.b0[0] - self.TOL <= x <= self.b0[2] + self.TOL
                and self.b0[1] - self.TOL <= y <= self.b0[3] + self.TOL):
            return False
        b = min(self.NB - 1, max(0, int((y - self.b0[1]) / self._dy * self.NB)))
        cnt = 0
        for (x1, y1, x2, y2) in self.buckets[b]:
            if (y1 > y) != (y2 > y):
                if x1 + (y - y1) * (x2 - x1) / (y2 - y1) > x:
                    cnt += 1
        if cnt % 2 == 1:
            return True
        # těsně za hranicí (generalizace siluety): ber jako uvnitř
        best = self.TOL
        n = len(self.ring)
        for i in range(n):                      # včetně uzavírací hrany
            ax, ay = self.ring[i]
            bx, by = self.ring[(i + 1) % n]
            if min(ax, bx) - best > x or max(ax, bx) + best < x:
                continue
            if min(ay, by) - best > y or max(ay, by) + best < y:
                continue
            dx, dy2 = bx - ax, by - ay
            L2 = dx * dx + dy2 * dy2
            t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0,
                ((x - ax) * dx + (y - ay) * dy2) / L2))
            d = math.hypot(ax + t * dx - x, ay + t * dy2 - y)
            if d < best:
                return True
        return False

    def clip(self, pts):
        out = []
        cur = []
        prev = None
        for p in pts:
            c = self.inside(p[0], p[1])
            if c and prev is False:
                cur = [self._cross(pts_prev, p, True), p]
            elif c:
                cur.append(p)
            elif prev is True and cur:
                cur.append(self._cross(pts_prev, p, False))
                out.append(cur)
                cur = []
            pts_prev = p
            prev = c
        if len(cur) >= 2:
            out.append(cur)
        return [o for o in out if len(o) >= 2]

    def _cross(self, a, b, entering):
        lo, hi = a, b
        for _ in range(20):
            mid = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
            if self.inside(mid[0], mid[1]):
                if entering:
                    hi = mid
                else:
                    lo = mid
            else:
                if entering:
                    lo = mid
                else:
                    hi = mid
        return ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)


# ---- main -----------------------------------------------------------------------
def main():
    print("atlas SVG…")
    sil, riv = parse_atlas()
    sil.sort(key=lambda p: -len(p))
    country = [(x * K, y * K)
               for x, y in simplify_closed(sil[0] + [sil[0][0]], 0.4)]
    atlas_riv = {}
    for code, idxs in ASKED.items():
        polys = [riv[i] for i in idxs]
        bb = bbox(polys[0])
        ex = EXPECT[code]
        assert all(abs(bb[k] - ex[k]) < 1.5 for k in range(4)), (code, bb, ex)
        atlas_riv[code] = [[(x * K, y * K) for x, y in p] for p in polys]
    print(f"  silueta {len(country)} bodů, {len(atlas_riv)} atlasových řek")

    print("shapefile…")
    asked, ctx_segs = load_lines()
    reservoirs = load_reservoirs()
    print(f"  ptané řeky: {sum(len(v) for v in asked.values())} segmentů, "
          f"kontext: {len(ctx_segs)} segmentů, nádrže: {len(reservoirs)}")

    print("ICP fit…")
    cx, cy, (nctrl, rms, mx) = fit_icp(atlas_riv, asked)
    assert rms < 1.5 and mx < 4.0, ("ICP fit nesedí", rms, mx)
    # sanity: velká města musí padnout do siluety
    clipper = Clipper(country)
    for name, lon, lat, box in [("Praha", 14.4378, 50.0755, (160, 160, 200, 195)),
                                ("Brno", 16.5993, 49.1951, (325, 250, 365, 285)),
                                ("Ostrava", 18.2925, 49.8209, (440, 170, 485, 205))]:
        bq = basis(lon, lat)
        X = sum(c * b for c, b in zip(cx, bq))
        Y = sum(c * b for c, b in zip(cy, bq))
        assert box[0] <= X <= box[2] and box[1] <= Y <= box[3], (name, X, Y)
        assert clipper.inside(X, Y), (name, "mimo siluetu")
        print(f"  {name}: ({X:.1f}, {Y:.1f}) ✓")

    def project(ch):
        out = []
        for lon, lat in ch:
            bq = basis(lon, lat)
            out.append((sum(c * b for c, b in zip(cx, bq)),
                        sum(c * b for c, b in zip(cy, bq))))
        return out

    print("řeky: šití, mosty, projekce, ořez…")
    rivers_out = []
    for code in sorted(RIVERS, key=lambda c: RIVERS[c][0]):
        name = RIVERS[code][0]
        chains = stitch(asked.get(code, []))
        chains = [c for c in chains if chain_len_km(c) >= 1.0]
        n0 = len(chains)
        bridge(chains, reservoirs)
        chains = [c for c in chains if len(c) >= 2]
        vb = []
        for ch in chains:
            for part in clipper.clip(project(ch)):
                part = rdp(part, 0.15)
                if len(part) >= 4 and chain_len_u(part) >= 2.0:
                    vb.append([(round(x, 1), round(y, 1)) for x, y in part])
        nstray = len(vb) - len(drop_strays(vb))
        vb = drop_strays(vb)
        npts = sum(len(p) for p in vb)
        bbs = [bbox(p) for p in vb]
        bb = (min(b[0] for b in bbs), min(b[1] for b in bbs),
              max(b[2] for b in bbs), max(b[3] for b in bbs)) if bbs else None
        nbridged = len([c for c in chains if c])
        print(f"  {name:11} řetězců {n0}→{nbridged}, po ořezu {len(vb)}"
              f"{' (-%d cizích)' % nstray if nstray else ''}, "
              f"{npts} b., bbox {tuple(round(v) for v in bb) if bb else None}")
        rivers_out.append({"code": code, "name": name, "chains": vb})

    print("kontext…")
    cchains = stitch(ctx_segs)
    ctx_out = []
    for ch in cchains:
        for part in clipper.clip(project(ch)):
            part = rdp(part, 0.35)
            if len(part) >= 2:
                ctx_out.append([(round(x, 1), round(y, 1)) for x, y in part])
    print(f"  {len(cchains)} řetězců → {len(ctx_out)} po ořezu, "
          f"{sum(len(p) for p in ctx_out)} bodů")

    data = {
        "meta": {
            "source": ("OpenStreetMap contributors (ODbL) — HOT OSM waterways "
                       "export hotosm_cze_waterways_osm_shp, snapshot 2026-11-03"),
            "projection": {"deg": 3, "cx": cx, "cy": cy,
                           "icp_ctrl": nctrl, "icp_rms": round(rms, 3),
                           "icp_max": round(mx, 3)},
            "viewbox": [VB_W, VB_H],
        },
        "rivers": rivers_out,
        "ctx": ctx_out,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"zapsáno {OUT} ({os.path.getsize(OUT)} bajtů)")


if __name__ == "__main__":
    main()
