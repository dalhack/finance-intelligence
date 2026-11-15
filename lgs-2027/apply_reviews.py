#!/usr/bin/env python3
"""Bağımsız denetim bulgularındaki (data/review_<ders>.json) hazır düzeltmeleri soru ve kart dosyalarına uygular.
Bir kez çalıştırılır; uygulananlar data/review_applied.json'a yazılır, ikinci kez uygulanmaz."""
import json, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
ap = os.path.join(D, 'review_applied.json')
done = json.load(open(ap, encoding='utf-8')) if os.path.exists(ap) else {}
for d in ['turkce', 'matematik', 'fen', 'inkilap', 'din', 'ingilizce']:
    rp = os.path.join(D, f'review_{d}.json')
    if not os.path.exists(rp): continue
    files = {n: json.load(open(os.path.join(D, n), encoding='utf-8')) for n in (f'q_{d}.json', f'cards_{d}.json')}
    idx = {x['id']: x for n in files for x in files[n]}
    excl_p = os.path.join(D, 'exclude.json'); excl = json.load(open(excl_p)) if os.path.exists(excl_p) else []
    for b in json.load(open(rp, encoding='utf-8')).get('bulgular', []):
        i = b.get('id'); key = f"{i}:{b.get('tur')}"
        if key in done: continue
        if b.get('ciddiyet') == 'at':
            if i not in excl: excl.append(i)
            done[key] = 'atıldı'; print('AT   ', i, b.get('tur')); continue
        dz = b.get('duzeltme') or {}
        if not dz or i not in idx: done[key] = 'not (düzeltme yok)'; print('NOT  ', i, b.get('tur'), '-', (b.get('aciklama') or '')[:110]); continue
        item = idx[i]; bad = [k for k in dz if k not in item and not k.startswith('test')]
        if bad: print('ATLA ', i, 'bilinmeyen alan', bad); done[key] = 'atlandı: ' + ','.join(bad); continue
        for k, v in dz.items():
            if k.startswith('test.'): item['test'][k[5:]] = v
            else: item[k] = v
        done[key] = 'uygulandı: ' + ','.join(dz); print('UYGUL', i, ','.join(dz))
    for n, v in files.items(): json.dump(v, open(os.path.join(D, n), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if excl: json.dump(excl, open(excl_p, 'w'))
json.dump(done, open(ap, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
