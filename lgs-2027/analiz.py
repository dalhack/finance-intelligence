#!/usr/bin/env python3
"""data/analiz_<yıl>.json dosyalarını tek havuzda birleştirir: data/analiz_ozet.json + data/analiz_ozet.md"""
import json, glob, os, collections
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DERS = [('turkce', 'Türkçe', 4), ('matematik', 'Matematik', 4), ('fen', 'Fen Bilimleri', 4), ('inkilap', 'İnkılap Tarihi', 1), ('din', 'Din Kültürü', 1), ('ingilizce', 'İngilizce', 1)]
kz = {d: {k['kod']: k for k in json.load(open(os.path.join(D, f'kazanim_{d}.json'), encoding='utf-8'))} for d, _, _ in DERS}
rows = []; yillar = []
for f in sorted(glob.glob(os.path.join(D, 'analiz_20*.json'))):
    a = json.load(open(f, encoding='utf-8')); yillar.append(a['yil'])
    for s in a['sorular']:
        s['yil'] = a['yil']; d = s.get('ders')
        if d in kz and s.get('kazanimKod') in kz[d]: s['unite'] = kz[d][s['kazanimKod']]['unite']   # üniteyi resmî listeden al
        elif s.get('kazanimKod'): s['gecersizKod'] = True
        rows.append(s)
oz = {'yillar': yillar, 'soruSayisi': len(rows), 'dersler': {}, 'tip': {}, 'ozellik': {}, 'okuma': dict(collections.Counter(s.get('okuma') for s in rows)),
      'guven': dict(collections.Counter(s.get('guven') for s in rows)), 'gecersizKod': sum(1 for s in rows if s.get('gecersizKod'))}
md = [f"# LGS {min(yillar)}–{max(yillar)} çıkmış soru analizi ({len(rows)} soru)\n"]
top = []
for d, ad, kat in DERS:
    rs = [s for s in rows if s.get('ders') == d]
    un = collections.defaultdict(lambda: collections.Counter()); kc = collections.Counter(); tip = collections.Counter(); oz_ = collections.Counter()
    for s in rs:
        un[s.get('unite') or 'belirsiz'][s['yil']] += 1; tip[s.get('tip')] += 1
        if s.get('kazanimKod') and not s.get('gecersizKod'): kc[s['kazanimKod']] += 1
        for o in s.get('ozellik') or []: oz_[o] += 1
    oz['dersler'][d] = {'ad': ad, 'n': len(rs), 'unite': [{'unite': u, 'toplam': sum(c.values()), 'yil': {str(y): c.get(y, 0) for y in yillar}} for u, c in sorted(un.items(), key=lambda x: -sum(x[1].values()))],
                        'kazanim': [{'kod': k, 'ad': kz[d][k]['ad'], 'unite': kz[d][k]['unite'], 'n': n} for k, n in kc.most_common()], 'tip': dict(tip), 'ozellik': dict(oz_)}
    md.append(f"\n## {ad} ({len(rs)} soru)\n\n| Ünite / konu | " + ' | '.join(str(y)[2:] for y in yillar) + " | Toplam |\n|---|" + '---|' * (len(yillar) + 1))
    for u in oz['dersler'][d]['unite']: md.append(f"| {u['unite']} | " + ' | '.join(str(u['yil'][str(y)] or '·') for y in yillar) + f" | **{u['toplam']}** |")
    md.append("\nEn çok sorulan kazanımlar: " + '; '.join(f"{k['kod']} ({k['n']})" for k in oz['dersler'][d]['kazanim'][:6]))
    md.append("Soru tipleri: " + ', '.join(f"{k} {v}" for k, v in tip.most_common()))
    for k in oz['dersler'][d]['kazanim']: top.append({'ders': ad, 'kod': k['kod'], 'ad': k['ad'], 'n': k['n'], 'kat': kat, 'agirlikliPuan': k['n'] * kat})
oz['enCokPuan'] = sorted(top, key=lambda x: -x['agirlikliPuan'])[:10]
md.append("\n## En çok puan getiren 10 kazanım (soru sayısı × ders katsayısı)\n\n| # | Ders | Kazanım | Soru | Ağırlıklı |\n|---|---|---|---|---|")
for i, t in enumerate(oz['enCokPuan'], 1): md.append(f"| {i} | {t['ders']} | {t['kod']} {t['ad'][:90]} | {t['n']} | {t['agirlikliPuan']} |")
json.dump(oz, open(os.path.join(D, 'analiz_ozet.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(os.path.join(D, 'analiz_ozet.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
print('yıllar', yillar, '| soru', len(rows), '| okuma', oz['okuma'], '| güven', oz['guven'], '| geçersiz kod', oz['gecersizKod'])
