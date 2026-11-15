#!/usr/bin/env python3
"""data/*.json -> app/questions.js + app/content.js ; şema denetimi yapar."""
import json, os, re, sys, collections
B = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(B, 'data'); A = os.path.join(B, 'app')
DERS = ['turkce', 'matematik', 'fen', 'inkilap', 'din', 'ingilizce']
HT = {'islem', 'okuma', 'kavram', 'grafik', 'birim', 'dikkat'}
TIP = {'uzun-metin', 'grafik-tablo', 'cok-adimli', 'deney', 'gorsel', 'klasik'}
def load(n, default=None):
    p = os.path.join(D, n)
    if not os.path.exists(p): return default
    return json.load(open(p, encoding='utf-8'))
def bad_svg(s): return bool(re.search(r'<script|<image|href=|<foreignObject|on\w+=', s, re.I))
qs, cards, errs = [], [], []
excl = set(load('exclude.json', []))
for d in DERS:
    kz = {k['kod'] for k in (load(f'kazanim_{d}.json', []) or [])}
    for q in load(f'q_{d}.json', []) or []:
        e = []
        if q.get('id') in excl: continue
        for f in ['id', 'ders', 'unite', 'kazanimKod', 'kazanimAd', 'metin', 'ipucu1', 'ipucu2', 'taktik']:
            if not isinstance(q.get(f), str) or not q[f].strip(): e.append('eksik ' + f)
        if q.get('ders') != d: e.append('ders')
        if q.get('zorluk') not in (1, 2, 3): e.append('zorluk')
        if not (isinstance(q.get('siklar'), list) and len(q['siklar']) == 4 and len(set(q['siklar'])) == 4): e.append('siklar')
        if q.get('dogru') not in (0, 1, 2, 3): e.append('dogru')
        if not (isinstance(q.get('cozum'), list) and 2 <= len(q['cozum']) <= 6): e.append('cozum adım sayısı')
        t = q.get('tuzaklar')
        if not (isinstance(t, list) and len(t) == 4 and all(isinstance(x, str) for x in t)): e.append('tuzaklar')
        elif q.get('dogru') in (0, 1, 2, 3) and any((not t[i].strip()) != (i == q['dogru']) for i in range(4)): e.append('tuzaklar doluluk')
        if q.get('hataTipi') not in HT: e.append('hataTipi')
        if q.get('tip') not in TIP: e.append('tip')
        if not (isinstance(q.get('kavramlar'), list) and 1 <= len(q['kavramlar']) <= 2): e.append('kavramlar')
        if q.get('svg') and (bad_svg(q['svg']) or not q['svg'].lstrip().startswith('<svg')): e.append('svg')
        if kz and q.get('kazanimKod') not in kz: e.append('kazanım kodu listede yok: ' + str(q.get('kazanimKod')))
        if e: errs.append((q.get('id'), e)); continue
        q.setdefault('svg', ''); qs.append(q)
    for c in load(f'cards_{d}.json', []) or []:
        ok = all(isinstance(c.get(f), str) and c[f].strip() for f in ['id', 'ders', 'unite', 'on', 'arka']) and isinstance(c.get('test'), dict) \
            and len(c['test'].get('siklar', [])) == 4 and c['test'].get('dogru') in (0, 1, 2, 3) and c['test'].get('soru')
        if ok and c['ders'] == d: cards.append(c)
        else: errs.append((c.get('id'), ['kart şeması']))
ids = [q['id'] for q in qs]
assert len(ids) == len(set(ids)), 'yinelenen id'
tk = load('taktikler.json'); src = load('sources.json', {}) or {}
def links(y):
    out = []
    for k, ad in [('sozel', 'Sözel kitapçık'), ('sayisal', 'Sayısal kitapçık')]:
        v = y.get(k)
        if v and v.get('url') and v.get('dogrulandi'): out.append({'ad': ad, 'url': v['url']})
    for c in y.get('cevap') or []:
        if c.get('url') and c.get('dogrulandi'): out.append({'ad': c.get('ad') or 'Cevap anahtarı', 'url': c['url']})
    return out
cik = [{'yil': y['yil'], 'tarih': y.get('tarih', ''), 'baglantilar': links(y)} for y in sorted(src.get('cikmis', []), key=lambda y: -y['yil'])]
cik = [y for y in cik if y['baglantilar']]
orn = collections.OrderedDict()
for o in src.get('ornek', []):
    if o.get('url') and o.get('dogrulandi'):
        orn.setdefault(o.get('donem', ''), []).append({'ad': o.get('ad') or o.get('ay', ''), 'url': o['url']})
content = {'sinav': tk['sinav'], 'taktikler': tk['taktikler'], 'kartlar': cards,
           'kaynaklar': {'cikmis': cik, 'ornek': [{'donem': k, 'baglantilar': v} for k, v in sorted(orn.items(), reverse=True)],
                         'not': 'Bağlantılar 15 Kasım 2026 tarihinde tek tek denetlendi. MEB dosya adreslerini değiştirirse açılmayabilir.'}}
js = lambda o: json.dumps(o, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
open(os.path.join(A, 'questions.js'), 'w', encoding='utf-8').write('window.LGS_QUESTIONS=' + js(qs) + ';\n')
open(os.path.join(A, 'content.js'), 'w', encoding='utf-8').write('window.LGS_CONTENT=' + js(content) + ';\n')
print('soru', len(qs), dict(collections.Counter(q['ders'] for q in qs)), '| kart', len(cards), '| çıkmış yıl', len(cik), '| örnek dönem', len(orn))
for i, e in errs: print('  HATA', i, e)
