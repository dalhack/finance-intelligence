#!/usr/bin/env python3
"""LGS matematik soru bankası için bağımsız doğrulama.
Her soruda cevap, çözüm metninden kopyalanmadan yeniden hesaplanır (kaba kuvvet, kesirler, geometri);
şekilli sorularda değerler SVG'nin kendisinden okunur (şeklin ölçekli çizildiği de böylece sınanır).
Sonuç siklar[dogru] ile karşılaştırılır; diğer 3 şıkkın doğru sonuca eşit OLMADIĞI da denetlenir.
Kullanım: python3 verify_matematik.py  ->  verify_matematik.json + stdout özeti"""
import json, math, re, html, os, itertools
from fractions import Fraction as F
HERE = os.path.dirname(os.path.abspath(__file__))
QS = {q["id"]: q for q in json.load(open(os.path.join(HERE, "q_matematik.json"), encoding="utf-8"))}

def clean(s):
    s = re.sub(r"<sup>(.*?)</sup>", r"^\1", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("−", "-").replace("·", "*")
    return re.sub(r"\s+", " ", s).strip()

def val(s):
    """Şık metnini sayıya çevirir: 2,4 | 2/3 | 18√3 | √2,5 | 7 * 2^15 | 18 000"""
    t = clean(s).replace(" ", "")
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)?√(\d+(?:\.\d+)?)", t)
    if m: return float(m.group(1) or 1) * math.sqrt(float(m.group(2)))
    m = re.fullmatch(r"(?:(\d+)\*)?(\d+)\^(-?\d+)", t)
    if m: return float(int(m.group(1) or 1) * F(int(m.group(2))) ** int(m.group(3)))
    m = re.fullmatch(r"(-?\d+)/(\d+)", t)
    if m: return float(F(int(m.group(1)), int(m.group(2))))
    return float(t)

def tup(s):
    return tuple(int(x) for x in re.findall(r"-?\d+", clean(s)))

def expr(s, **v):
    t = clean(s).replace(" ", "").replace("²", "**2")
    t = re.sub(r"(\d)([a-z(])", r"\1*\2", t)
    t = re.sub(r"([a-z])([a-z])", r"\1*\2", t)
    return eval(t, {"__builtins__": {}}, v)

def eq(a, b): return abs(a - b) < 1e-9

def attrs(tag):
    return dict(re.findall(r"([\w-]+)='([^']*)'", tag))
def tags(svg, name):
    return [attrs(m) for m in re.findall(r"<%s\b[^>]*>" % name, svg)]
def texts(svg):
    return [(attrs(a), t) for a, t in re.findall(r"<text\b([^>]*)>(.*?)</text>", svg)]
def linmap(p):
    (v1, c1), (v2, c2) = p[0], p[-1]
    return lambda c: v1 + (c - c1) * (v2 - v1) / (c2 - c1)
def numlabel(t):
    t = t.replace("−", "-")
    return int(t) if re.fullmatch(r"-?\d+", t) else None

# ---- her soru: beklenen değer + şık karşılaştırıcı --------------------------------
def numeric(expected):               # sayısal şıklar
    return lambda q: [eq(val(s), expected) for s in q["siklar"]]
def exact(expected):                 # metin şıklar (sıralama vb.)
    return lambda q: [clean(s).replace(" ", "") == expected.replace(" ", "") for s in q["siklar"]]
def tuples(expected):
    return lambda q: [tup(s) == expected for s in q["siklar"]]
def poly(fn, pts):                   # cebirsel ifade şıkları: birçok noktada eşitlik
    return lambda q: [all(eq(expr(s, **p), fn(**p)) for p in pts) for s in q["siklar"]]

C = {}
def check(n):
    def deco(fn): C["mat-%03d" % n] = fn; return fn
    return deco

@check(1)
def _(q):
    n, e = 360, {}
    for p in (2, 3, 5):
        while n % p == 0: n //= p; e[p] = e.get(p, 0) + 1
    assert n == 1
    return numeric(sum(e.values()))(q)
@check(2)
def _(q): return numeric(sum(1 for t in range(0, 601) if t % 18 == 0 and t % 24 == 0))(q)
@check(3)
def _(q):
    g = math.gcd(96, 120); return numeric((96 // g - 1) + (120 // g - 1))(q)
@check(4)
def _(q):
    c = [n for n in range(101, 200) if n % 8 == 3 and n % 12 == 3 and n % 7 == 0]
    assert len(c) == 1, c
    return numeric(c[0] % 5)(q)
@check(5)
def _(q):
    pairs = re.findall(r"(\d+) ve (\d+)</td>", q["metin"]); assert len(pairs) == 6
    return numeric(sum(1 for a, b in pairs if math.gcd(int(a), int(b)) == 1))(q)
@check(6)
def _(q): return numeric(float(F(-2) ** 3 + F(3) ** -2 * F(3) ** 4 - F(5) ** 0))(q)
@check(7)
def _(q):
    v = 2 ** 5
    for _ in range(6): v *= 4
    assert v & (v - 1) == 0
    return numeric(v.bit_length() - 1)(q)
@check(8)
def _(q):
    d = {"K": F(32, 10) / 10 ** 4, "L": F(45, 100000), "M": F(28) / 10 ** 5, "N": F(51, 100) / 10 ** 3}
    assert len(set(d.values())) == 4
    return exact("<".join(sorted(d, key=d.get)))(q)
@check(9)
def _(q):
    n = (2 ** 40 - 2 ** 40 // 8) // 2 ** 22; return numeric(n)(q)
@check(10)
def _(q): return numeric(float(3 * F(10) ** 2 + 4 * F(10) ** 0 + 7 * F(10) ** -2 + 5 * F(10) ** -3))(q)
@check(11)
def _(q): assert math.isqrt(196) ** 2 == 196; return numeric(4 * math.isqrt(196))(q)
@check(12)
def _(q):
    svg = q["svg"]; tx = texts(svg)
    ticks = sorted((numlabel(t), float(a["x"])) for a, t in tx if numlabel(t) is not None)
    fx = linmap(ticks)
    pts = {}
    for c in tags(svg, "circle"):
        x = float(c["cx"]); name = min(((abs(float(a["x"]) - x), t) for a, t in tx if t in "KLMN"))[1]
        pts[name] = fx(x)
    target = 3 * math.sqrt(6); lo = math.floor(target)
    inside = [k for k, v in pts.items() if lo < v < lo + 1]      # aynı iki doğal sayı arasında olan tek nokta
    assert len(inside) == 1 and abs(pts[inside[0]] - target) < 0.1, pts
    return exact(inside[0])(q)
@check(13)
def _(q): return numeric(2 * (math.sqrt(48) + math.sqrt(75)))(q)
@check(14)
def _(q):
    k = math.sqrt(12); return numeric(2 * (k + 30 / k))(q)
@check(15)
def _(q):
    def irr(s):
        x = F(re.search(r"√([\d,]+)", clean(s)).group(1).replace(",", "."))
        r = lambda n: math.isqrt(n) ** 2 == n
        return not (r(x.numerator) and r(x.denominator))
    return [irr(s) for s in q["siklar"]]
@check(16)
def _(q):
    svg = q["svg"]
    ys = sorted((numlabel(t), float(a["y"]) - 4) for a, t in texts(svg) if a.get("text-anchor") == "end" and numlabel(t) is not None)
    fy = linmap(ys)
    A = [fy(float(r["y"])) for r in tags(svg, "rect") if r["class"] == "acf"]
    B = [fy(float(r["y"])) for r in tags(svg, "rect") if r["class"] == "mf"]
    assert len(A) == len(B) == 4 and all(eq(v, round(v)) for v in A + B), (A, B)
    for r in tags(svg, "rect"): assert eq(fy(float(r["y"]) + float(r["height"])), 0)   # sütunlar tabana oturuyor
    return numeric(sum(A) / 4 - sum(B) / 4)(q)
@check(17)
def _(q):
    svg = q["svg"]; ang = []
    for p in re.findall(r"<path[^>]*d='M(\S+) (\S+) L(\S+) (\S+) A\S+ \S+ 0 0 1 (\S+) (\S+) Z'", svg):
        cx, cy, x1, y1, x2, y2 = map(float, p)
        a = lambda x, y: math.degrees(math.atan2(x - cx, cy - y)) % 360
        ang.append((a(x2, y2) - a(x1, y1)) % 360 or 360)
    lab = {}
    for a, t in texts(svg):
        if "°" in t: lab[float(a["x"]), float(a["y"])] = int(re.search(r"(\d+)°", t).group(1))
    assert sorted(round(x) for x in ang) == sorted(lab.values()) and round(sum(ang)) == 360, ang
    assert all(abs(x - round(x)) < 0.3 for x in ang)
    d = dict(zip(["Spor", "Kodlama", "Müzik", "Resim"], [round(x) for x in ang]))
    assert d == {"Spor": 120, "Kodlama": 108, "Müzik": 90, "Resim": 42}
    total = F(54 * 360, d["Kodlama"])
    return numeric(float(total * d["Spor"] / 360 - total * d["Resim"] / 360))(q)
@check(18)
def _(q):
    bag = ["k"] * 5 + ["m"] * 4 + ["s"] * 3
    return numeric(float(F(sum(1 for b in bag if b != "m"), len(bag))))(q)
@check(19)
def _(q): return numeric(float(F(sum(1 for n in range(1, 41) if 40 % n == 0), 40)))(q)
PX = [dict(x=v) for v in (-3, -1, 0, 2.5, 7, 11)]
@check(20)
def _(q): return poly(lambda x: (2 * x + 3) * (x - 4), PX)(q)
@check(21)
def _(q): return poly(lambda x: (x * x - 9) / (x - 3), [dict(x=v) for v in (4, 5.5, 10, 17)])(q)
@check(22)
def _(q): return poly(lambda x: 4 * math.sqrt(4 * x * x - 12 * x + 9), [dict(x=v) for v in (2.5, 3, 7, 12)])(q)
@check(23)
def _(q):
    sol = [(a, 9 - a) for a in [F(k, 100) for k in range(0, 901)] if a * (9 - a) == 18]
    assert sol; vals = {a * a + b * b for a, b in sol}; assert len(vals) == 1
    return numeric(float(vals.pop()))(q)
@check(24)
def _(q):
    e = re.search(r"<b>(.*?)</b>", q["metin"]).group(1)
    return numeric(expr(e, a=1, b=1))(q)       # katsayılar toplamı = değişkenlere 1 yazınca çıkan değer
@check(25)
def _(q):
    s = [F(k, 2) for k in range(0, 100) if 30 + 20 * F(k, 2) == 170]; assert len(s) == 1
    return numeric(float(s[0]))(q)
@check(26)
def _(q):
    svg = q["svg"]; tx = texts(svg)
    xs = sorted((numlabel(t), float(a["x"])) for a, t in tx if a.get("text-anchor") == "middle" and numlabel(t) is not None)
    ys = sorted((numlabel(t), float(a["y"]) - 4) for a, t in tx if a.get("text-anchor") == "end" and numlabel(t) is not None)
    ys = [(0, float([l for l in tags(svg, "line") if l["y1"] == l["y2"] and "stroke-opacity" not in l][-1]["y1"]))] + ys
    fx, fy = linmap(xs), linmap(ys)
    ln = [l for l in tags(svg, "line") if l.get("class") == "ac"][0]
    p1 = (fx(float(ln["x1"])), fy(float(ln["y1"]))); p2 = (fx(float(ln["x2"])), fy(float(ln["y2"])))
    assert eq(p1[0], 0) and eq(p1[1], 240) and eq(p2[0], 8) and eq(p2[1], 0), (p1, p2)
    return numeric(p1[1] + (p2[1] - p1[1]) * (5 - p1[0]) / (p2[0] - p1[0]))(q)
@check(27)
def _(q):
    m = re.search(r"d='M(\S+) (\S+) L(\S+) (\S+) L(\S+) (\S+) Z'", q["svg"]); x1, y1, x2, y2, x3, y3 = map(float, m.groups())
    assert eq((y2 - y3) / (x2 - x1), 0.15)      # şekil gerçek eğimle çizilmiş
    return numeric(float(F(9, 10) / F(3, 20)))(q)
@check(28)
def _(q):
    s = [F(k, 4) for k in range(0, 60) if 30 - 3 * F(k, 4) > 0 and 24 - 2 * F(k, 4) > 0 and 2 * (30 - 3 * F(k, 4)) == 24 - 2 * F(k, 4)]
    assert len(s) == 1; return numeric(float(s[0]))(q)
@check(29)
def _(q):
    xi, yi = F(12, 2), F(12, 3)
    svg = q["svg"]; tx = texts(svg)
    ln = [l for l in tags(svg, "line") if l.get("class") == "ac"][0]
    xs = sorted((numlabel(t), float(a["x"])) for a, t in tx if a.get("text-anchor") == "middle" and numlabel(t) is not None)
    ys = sorted((numlabel(t), float(a["y"]) - 4) for a, t in tx if a.get("text-anchor") == "end" and numlabel(t) is not None)
    fx, fy = linmap(xs), linmap(ys)
    for k in ("1", "2"): assert eq(2 * fx(float(ln["x" + k])) + 3 * fy(float(ln["y" + k])), 12)   # çizilen doğru denklemi sağlıyor
    return numeric(float(xi * yi / 2))(q)
@check(30)
def _(q):
    res = []
    for s in q["siklar"]:
        t = clean(s).replace(" ", "").replace("≤", "<=").replace("≥", ">=")
        t = re.sub(r"(\d)([a-z(])", r"\1*\2", t)
        res.append(all(eval(t, {}, {"x": x}) == (45 * x + 75 <= 615) for x in range(0, 31)))
    return res
@check(31)
def _(q):
    svg = q["svg"]; tx = texts(svg); rows = {}
    for c in tags(svg, "circle"): rows[float(c["cy"])] = {"cx": float(c["cx"]), "closed": c["fill"] != "none"}
    for l in tags(svg, "line"):
        if l.get("class") == "ac": rows[float(l["y1"])]["dir"] = "L" if float(l["x2"]) < float(l["x1"]) else "R"
    names = ["I", "II", "III", "IV"]; pred = {}
    for i, y in enumerate(sorted(rows)):
        r = rows[y]
        ticks = sorted((numlabel(t), float(a["x"])) for a, t in tx if numlabel(t) is not None and abs(float(a["y"]) - y - 19) < 1)
        b = linmap(ticks)(r["cx"])
        pred[names[i]] = (lambda b, r: lambda x: (x < b if r["dir"] == "L" else x > b) or (r["closed"] and x == b))(b, r)
    xs = [F(k, 4) for k in range(-40, 60)]
    return [all(pred[clean(s)](x) == (-3 * x + 5 > -7) for x in xs) for s in q["siklar"]]
@check(32)
def _(q): return numeric(max(h for h in range(1, 50) if 50 + 20 * (h - 1) <= 175))(q)
@check(33)
def _(q): return numeric(min(x for x in range(0, 21) if 5 * x - 2 * (20 - x) >= 65))(q)
@check(34)
def _(q):
    ln = [l for l in tags(q["svg"], "line") if l.get("class") == "ac"][0]
    dx = abs(float(ln["x2"]) - float(ln["x1"])); dy = abs(float(ln["y2"]) - float(ln["y1"]))
    assert eq(dy / dx, 2.4 / 0.7)            # şekil ölçekli
    return numeric(math.sqrt(2.5 ** 2 - 0.7 ** 2))(q)
@check(35)
def _(q): return numeric(sum(1 for x in range(1, 100) if x < 7 + 12 and 7 < x + 12 and 12 < x + 7))(q)
@check(36)
def _(q):
    Aa, Ba = 50, 72; Ca = 180 - Aa - Ba
    side = {"|BC|": math.sin(math.radians(Aa)), "|AC|": math.sin(math.radians(Ba)), "|AB|": math.sin(math.radians(Ca))}
    m = re.search(r"d='M(\S+) (\S+) L(\S+) (\S+) L(\S+) (\S+) Z'", q["svg"]); ax, ay, bx, by, cx, cy = map(float, m.groups())
    ang = lambda p, a, b: math.degrees(math.acos(((a[0]-p[0])*(b[0]-p[0]) + (a[1]-p[1])*(b[1]-p[1])) / math.dist(p, a) / math.dist(p, b)))
    assert abs(ang((ax, ay), (bx, by), (cx, cy)) - 50) < 0.5 and abs(ang((bx, by), (ax, ay), (cx, cy)) - 72) < 0.5
    return exact("<".join(sorted(side, key=side.get)))(q)
@check(37)
def _(q):
    x = y = 0; path = 0
    for dx, dy in ((8, 0), (0, 6), (4, 0), (0, 10)): x += dx; y += dy; path += abs(dx) + abs(dy)
    return numeric((path + math.hypot(x, y)) / 60 * 60)(q)
@check(38)
def _(q):
    h = math.sqrt(13 ** 2 - (10 / 2) ** 2); return numeric(10 * h / 2 * 150)(q)
@check(39)
def _(q): return numeric(float(F(24, 10) * 15))(q)
@check(40)
def _(q): return numeric(float(F(16, 10) / 2 * F(75, 10)))(q)
@check(41)
def _(q): return numeric(float(F(60) * 250 / 100))(q)
@check(42)
def _(q): return numeric(float(F(12 * 50, 100) * F(8 * 50, 100)))(q)
@check(43)
def _(q): return tuples((-3 + 5, 2 - 4))(q)
@check(44)
def _(q):
    svg = q["svg"]; tx = texts(svg)
    xs = sorted((numlabel(t), float(a["x"])) for a, t in tx if a.get("text-anchor") == "middle" and numlabel(t) is not None)
    ys = sorted((numlabel(t), float(a["y"]) - 4) for a, t in tx if a.get("text-anchor") == "end" and numlabel(t) is not None)
    c = tags(svg, "circle")[0]; px, py = linmap(xs)(float(c["cx"])), linmap(ys)(float(c["cy"]))
    assert eq(px, round(px)) and eq(py, round(py))
    return tuples((-round(px), round(py)))(q)
@check(45)
def _(q):
    p = (3, 2); r = (p[0], -p[1]); e = (r[0] - 6, r[1] - 4)
    return numeric(math.dist(p, e))(q)
@check(46)
def _(q):
    svg = q["svg"]
    pol = [[((float(x) - 20) / 20, (float(y) - 15) / 20) for x, y in (p.split(",") for p in a["points"].split())] for a in tags(svg, "polygon")]
    P1, P2 = (set(p) for p in pol)
    d = [(float(l["x1"]) - 20) / 20 for l in tags(svg, "line") if "stroke-dasharray" in l and l["x1"] == l["x2"]][0]
    def apply(desc, P):
        t = clean(desc)
        if "yansıma" in t: P = {(2 * d - x, y) for x, y in P}
        m = re.search(r"(\d+) birim sağa", t)
        if m: P = {(x + int(m.group(1)), y) for x, y in P}
        m = re.search(r"(\d+) birim (aşağı|yukarı)", t)
        if m: P = {(x, y + int(m.group(1)) * (1 if m.group(2) == "aşağı" else -1)) for x, y in P}   # ekranda y aşağı doğru artar
        return P
    return [apply(s, P1) == P2 for s in q["siklar"]]
@check(47)
def _(q): return numeric(3 * (10 / 2) ** 2 * 12)(q)
@check(48)
def _(q):
    r = tags(q["svg"], "rect")[0]; c = tags(q["svg"], "circle")[0]
    assert eq(float(r["width"]) / float(c["r"]), 2 * 3) and eq(float(r["height"]) / float(c["r"]), 10 / 4)   # açınım ölçekli (π = 3)
    return numeric(2 * 3 * 4 * 10)(q)
@check(49)
def _(q): return numeric(float(F(3 * 6 ** 2 * 20) / (F(3 * 3 ** 2 * 10) * F(4, 5))))(q)
@check(50)
def _(q):
    pyr_edges = 6 + 6            # taban ayrıtları + yan ayrıtlar
    prism_vertices = 2 * 3
    return numeric(pyr_edges + prism_vertices)(q)

def main():
    out, fails = {}, []
    for qid, q in sorted(QS.items()):
        if qid not in C: out[qid] = "kavramsal"; continue
        try:
            m = C[qid](q)
            ok = m[q["dogru"]] and sum(m) == 1 and len(set(clean(s) for s in q["siklar"])) == 4
            why = "" if ok else "eşleşen şıklar=%s dogru=%d" % (m, q["dogru"])
        except Exception as e:
            ok, why = False, "%s: %s" % (type(e).__name__, e)
        out[qid] = "pass" if ok else "fail"
        if not ok: fails.append((qid, why))
    json.dump(out, open(os.path.join(HERE, "verify_matematik.json"), "w"), ensure_ascii=False, indent=1)
    n = len(out); p = sum(v == "pass" for v in out.values()); k = sum(v == "kavramsal" for v in out.values())
    print("toplam %d | pass %d | fail %d | kavramsal %d" % (n, p, len(fails), k))
    for f in fails: print("FAIL", *f)
    return 1 if fails else 0

if __name__ == "__main__":
    raise SystemExit(main())
