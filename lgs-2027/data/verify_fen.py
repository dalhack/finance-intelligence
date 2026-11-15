#!/usr/bin/env python3
"""q_fen.json icindeki sayisal/hesaplanabilir sorulari BAGIMSIZ hesaplayip siklarla karsilastirir.
Her kontrol fonksiyonu, 'dogru oldugu hesapla bulunan sik indeksleri' kumesini dondurur.
pass  <=> bu kume tam olarak {dogru}  (yani dogru sik tutuyor VE diger 3 sik tutmuyor).
Hesap icermeyen sorular 'kavramsal' olarak isaretlenir.
Kullanim: python3 verify_fen.py   -> verify_fen.json + ozet
"""
import json, re, os, math, itertools
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
QS = {q["id"]: q for q in json.load(open(os.path.join(HERE, "q_fen.json"), encoding="utf-8"))}

def clean(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return s.replace("&gt;", ">").replace("&lt;", "<").replace("−", "-").strip()

def num(s):
    m = re.search(r"-?\d+(?:[.,]\d+)?", clean(s))
    return float(m.group().replace(",", ".")) if m else None

def numeric(q, value):
    return {i for i, o in enumerate(q["siklar"]) if num(o) is not None and abs(num(o) - value) < 1e-9}

def roman_set(opt):
    return frozenset(re.findall(r"\b(III|II|I)\b", clean(opt)))

def oncul(q, truths):
    want = frozenset(k for k, v in truths.items() if v)
    return {i for i, o in enumerate(q["siklar"]) if roman_set(o) == want}

def chain_ok(opt, val):
    """'L > N > K = M' gibi bir siralama, val sozlugundeki degerlerle tam uyumlu mu?"""
    s = re.sub(r"\bP\s*", "", clean(opt)).replace(" ", "")
    groups = [g.split("=") for g in s.split(">")]
    names = [n for g in groups for n in g]
    if sorted(names) != sorted(val):
        return False
    for g in groups:
        if any(val[n] != val[g[0]] for n in g):
            return False
    return all(val[a[0]] > val[b[0]] for a, b in zip(groups, groups[1:]))

def chain(q, val):
    return {i for i, o in enumerate(q["siklar"]) if chain_ok(o, val)}

def truths(q, flags, keys, want=True):
    """flags: sik sirasiyla hesaplanan dogruluk degerleri; keys: hizalama icin her sikta aranacak anahtar sozcuk."""
    for o, k in zip(q["siklar"], keys):
        assert k in o, (q["id"], k, o)
    return {i for i, f in enumerate(flags) if f == want}

def cross(p1, p2):
    """Tek karakter caprazlamasi: yavru genotiplerinin listesi (itertools ile sayma)."""
    return ["".join(sorted(a + b)) for a, b in itertools.product(p1, p2)]

# ---------------------------------------------------------------- kontroller
def c003(q):
    t = [int(h) * 60 + int(m) for h, m in re.findall(r"(\d+) sa (\d+) dk", q["metin"])]
    (kj, kd), (lj, ld), (mj, md) = (t[0], t[1]), (t[2], t[3]), (t[4], t[5])
    return oncul(q, {"I": kj > kd,                      # Haziran'da gunduz uzun -> Kuzey YK
                     "II": ld < lj,                     # L'de Aralik'ta kis baslar mi?
                     "III": abs(mj - md) < min(abs(kj - kd), abs(lj - ld))})

def c006(q):
    obs = [84, 200, 84, 30]
    for v in obs: assert ">%d<" % v in q["svg"]
    lat = 39.9  # Ankara
    dates = [("21 Mart", 0.0), ("21 Haziran", 23.44), ("23 Eylül", 0.0), ("21 Aralık", -23.44)]
    ok = set()
    for s in range(4):
        seq = [dates[(s + k) % 4] for k in range(4)]
        model = [100 * math.tan(math.radians(lat - d)) for _, d in seq]
        if all(abs(a - b) < 5 for a, b in zip(model, obs)):
            ok.add(dates[s][0])
    return {i for i, o in enumerate(q["siklar"]) if o in ok}

def c008(q):
    left = "ATGCCA"; shown = "T1C2G3"
    comp = {"A": "T", "T": "A", "G": "C", "C": "G"}
    for l, r in zip(left, shown):
        assert (">%s<" % l) in q["svg"]
        if not r.isdigit(): assert comp[l] == r
    ans = [comp[l] for l, r in zip(left, shown) if r.isdigit()]
    return {i for i, o in enumerate(q["siklar"]) if re.findall(r"[ATGC]", o) == ans}

def c009(q):
    kids = cross("Ss", "ss")
    return numeric(q, float(F(kids.count("ss"), len(kids)) * 100))

def c010(q):
    rows = re.findall(r"<td>(uzun × \w+)</td><td>(\d+)</td><td>(\d+)</td>", q["metin"])
    total = 0
    for parents, tall, short in rows:
        obs = F(int(short), int(tall) + int(short))
        second = ["UU", "Uu"] if parents.endswith("uzun") else ["uu"]
        fits = []
        for a, b in itertools.product(["UU", "Uu"], second):
            kids = cross(a, b)
            if abs(F(kids.count("uu"), 4) - obs) < F(1, 20):
                fits.append((a, b))
        counts = {sum(g == "Uu" for g in f) for f in fits}
        assert len(counts) == 1, (parents, fits)     # melez ata sayisi tek anlamli olmali
        total += counts.pop()
    return numeric(q, total)

def c011(q):
    f1 = set(cross("MM", "mm")); assert f1 == {"Mm"}
    f2 = cross("Mm", "Mm")
    mor = [g for g in f2 if "M" in g]
    val = F(mor.count("Mm"), len(mor))
    out = set()
    for i, o in enumerate(q["siklar"]):
        a, b = re.findall(r"<span>(\d+)</span>", o)
        if F(int(a), int(b)) == val: out.add(i)
    return out

def c016(q):
    area = {"K": 10 * 20, "L": 5 * 20, "M": 5 * 10}
    return chain(q, {k: F(1, a) for k, a in area.items()})      # agirlik esit, P ~ 1/A

def c018(q):
    d = {"su": F(1), "tuzlu su": F(11, 10)}                      # yalniz d_tuzlu > d_su bilgisi kullanilir
    return chain(q, {"K": d["su"] * 10, "L": d["su"] * 20, "M": d["tuzlu su"] * 20})

def c019(q):
    return chain(q, {"K": F(1, 1), "L": F(2, 1), "M": F(2, 2), "N": F(3, 2)})   # blok / taban yuzu

def c022(q):
    pos = {"X": (3, 1), "Y": (2, 7), "Z": (3, 8), "T": (2, 2)}   # (periyot, grup) - svg ile ayni
    def Z(p, g): return {1: 0, 2: 2, 3: 10}[p] + (g if p > 1 else (1 if g == 1 else 2))
    metal = {3, 4, 11, 12, 13, 19, 20}; soygaz = {2, 10, 18}
    z = {k: Z(*v) for k, v in pos.items()}
    assert z == {"X": 11, "Y": 9, "Z": 18, "T": 4}
    flags = [z["X"] not in metal and z["X"] not in soygaz and z["X"] not in {5, 14},
             pos["Y"][0] == pos["Z"][0], z["Z"] in soygaz, pos["T"][1] == pos["X"][1]]
    return truths(q, flags, ["ametal", "periyot", "soygaz", "grup"])

def c023(q):
    start = {1: 1, 2: 3, 3: 11}
    assert start[3] == 2 + 8 + 1
    return numeric(q, start[3] + (7 - 1))

def c025(q):
    return numeric(q, 28 + (20 - 4))

def c026(q):
    ph = {"K": 1, "L": 5, "M": 8, "N": 12}
    flags = [ph["K"] > 7,                                        # kirmizi turnusolu maviye: baz
             max(ph, key=ph.get) == "M",
             ph["L"] < 7 and ph["K"] < 7 and ph["L"] > ph["K"],  # ikisi de asit, L daha zayif
             ph["N"] < 7]                                        # eksi tat: asit
    return truths(q, flags, ["turnusol", "Bazlık", "zayıf", "ekşi"])

def c028(q):
    c = {"su": 4.18, "zeytinyagi": 1.97}                         # J/g°C (yaklasik)
    dT = {"K": 1 / (100 * c["su"]), "L": 1 / (200 * c["su"]), "M": 1 / (100 * c["zeytinyagi"])}
    order = sorted(dT, key=dT.get, reverse=True)                 # 1 = en dik
    return {i for i, o in enumerate(q["siklar"]) if re.findall(r"[KLM]", o) == order}

def c031(q):
    f = 40                                                       # sabit makara: F = yuk
    return {i for i, o in enumerate(q["siklar"]) if num(o) == f and "işten kazanç" not in o and "yön" in o}

def c032(q):
    return numeric(q, float(F(60 * 2, 6)))

def c033(q):
    rows = [(int(a), int(b)) for a, b in re.findall(r"<td>(\d+) cm</td><td>(\d+) N</td>", q["metin"])]
    G, h = 10, 30
    work = [f * l for l, f in rows]
    assert all(w == G * h for w in work)
    gain = [F(G, f) for l, f in rows]
    flags = [True,
             all(a[1] > b[1] for a, b in zip(rows, rows[1:])),
             gain.index(max(gain)) == 2,
             work[2] < min(work[:2])]
    return truths(q, flags, ["bağımsız", "azalmıştır", "Kuvvet kazancı", "işten kazanç"], want=False)

def c034(q):
    P, h = 80, 2
    fk, sk = P, h
    fl, sl = F(P, 2), 2 * h
    flags = [fk == 80, fl == 40, fl * sl == F(fk * sk, 2), sl == 4]
    return truths(q, flags, ["80 N", "40 N", "yarısı", "4 m"], want=False)

def c036(q):
    assert 50 * 30 == 150 * 10
    return numeric(q, float(F(150 * 10, 30)))

def c039(q):
    d = {5: 1, 15: 3, 25: 6, 35: 8, 45: 2}
    ts = sorted(d)
    return oncul(q, {"I": all(d[a] < d[b] for a, b in zip(ts, ts[1:]) if b <= 35),
                     "II": all(d[a] < d[b] for a, b in zip(ts, ts[1:])),
                     "III": d[15] > d[45]})

def c047(q):
    kwh = F(2000, 1000) * F(30, 60) * 30
    return numeric(q, float(kwh * 3))

def c048(q):
    save = [5 * (60 - 10) * 6, 1200 * 1, F(1800 * 1, 2), 100 * 2]   # Wh/gun, sik sirasiyla
    for o, k in zip(q["siklar"], ["LED", "Klima", "Bulaşık", "Televizyon"]): assert k in o
    return {i for i, s in enumerate(save) if s == max(save)}

CHECKS = {"fen-003": c003, "fen-006": c006, "fen-008": c008, "fen-009": c009, "fen-010": c010, "fen-011": c011,
          "fen-016": c016, "fen-018": c018, "fen-019": c019, "fen-022": c022, "fen-023": c023, "fen-025": c025,
          "fen-026": c026, "fen-028": c028, "fen-031": c031, "fen-032": c032, "fen-033": c033, "fen-034": c034,
          "fen-036": c036, "fen-039": c039, "fen-047": c047, "fen-048": c048}

def main():
    res = {}
    for qid, q in QS.items():
        if qid not in CHECKS:
            res[qid] = "kavramsal"; continue
        try:
            got = CHECKS[qid](q)
            res[qid] = "pass" if got == {q["dogru"]} else "fail"
            if res[qid] == "fail": print("FAIL", qid, "hesaplanan:", sorted(got), "dogru:", q["dogru"])
        except Exception as e:
            res[qid] = "fail"; print("FAIL", qid, "hata:", repr(e))
    json.dump(res, open(os.path.join(HERE, "verify_fen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = {k: sum(v == k for v in res.values()) for k in ("pass", "fail", "kavramsal")}
    print("toplam %d | pass %d | fail %d | kavramsal %d" % (len(res), n["pass"], n["fail"], n["kavramsal"]))

if __name__ == "__main__":
    main()
