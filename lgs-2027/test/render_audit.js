// Tüm soruları ve kartları 390px genişlikte çizip taşmaları raporlar. Kullanım: node test/render_audit.js [shots-dir]
const { chromium, devices } = require('playwright'); const path = require('path'), fs = require('fs');
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ ...devices['iPhone 13'] }); const p = await ctx.newPage();
  await p.goto('file://' + path.join(__dirname, '..', 'app', 'index.html'));
  const r = await p.evaluate(() => {
    const main = document.getElementById('main'), out = [];
    const H = ['A', 'B', 'C', 'D'];
    for (const q of window.LGS_QUESTIONS) {
      main.innerHTML = '<div class="qtext tw">' + q.metin + '</div>' + (q.svg ? '<div class="qsvg">' + q.svg + '</div>' : '') + '<div class="opts">' +
        q.siklar.map((s, i) => '<button class="opt"><span class="l">' + H[i] + '</span><span class="x">' + s + '</span></button>').join('') + '</div>' +
        '<div class="box">' + q.ipucu1 + q.ipucu2 + '</div><ol class="steps">' + q.cozum.map(c => '<li>' + c + '</li>').join('') + '</ol><div class="box">' + q.tuzaklar.join('<br>') + q.taktik + '</div>';
      const pr = [];
      if (main.scrollWidth - main.clientWidth > 1) pr.push('ekran taşması ' + (main.scrollWidth - main.clientWidth));
      main.querySelectorAll('.tw,.qsvg,.opt .x').forEach(e => { if (e.scrollWidth - e.clientWidth > 1) pr.push((e.className) + ' içi taşma ' + (e.scrollWidth - e.clientWidth)); });
      main.querySelectorAll('svg').forEach(s => { if (!s.viewBox.baseVal || !s.viewBox.baseVal.width) pr.push('viewBox yok'); });
      if (/<(?!\/?(b|i|u|br|sup|sub|table|tr|td|th|span|p|ul|ol|li|thead|tbody|div|strong|em)\b)[a-zA-Z]/.test(q.metin + q.siklar.join(''))) pr.push('beklenmeyen etiket');
      if (pr.length) out.push(q.id + ': ' + [...new Set(pr)].join('; '));
    }
    for (const c of (window.LGS_CONTENT.kartlar || [])) {
      main.innerHTML = '<div class="card"><div class="kfront">' + c.on + '</div><div class="box acc">' + c.arka + '</div></div><b>' + c.test.soru + '</b><div class="opts">' + c.test.siklar.map(s => '<button class="opt"><span class="l">A</span><span class="x">' + s + '</span></button>').join('') + '</div>';
      if (main.scrollWidth - main.clientWidth > 1) out.push(c.id + ': kart taşması');
    }
    return out;
  });
  console.log(r.length ? r.join('\n') : 'taşma yok'); console.log('sorunlu:', r.length);
  const dir = process.argv[2];
  if (dir) { fs.mkdirSync(dir, { recursive: true });
    const ids = await p.evaluate(() => window.LGS_QUESTIONS.filter(q => q.svg).map(q => q.id));
    for (let k = 0; k < ids.length; k += 6) {
      await p.evaluate(g => { document.getElementById('app').style.maxWidth = 'none'; document.body.style.overflow = 'auto'; const m = document.getElementById('main'); m.style.cssText = 'display:grid;grid-template-columns:repeat(3,1fr);gap:8px;overflow:visible';
        m.innerHTML = g.map(id => { const q = window.LGS_QUESTIONS.find(x => x.id === id); return '<div class="card" style="font-size:11px"><b>' + id + '</b><div class="qsvg">' + q.svg + '</div><div>' + q.metin.slice(0, 260) + '</div></div>'; }).join(''); }, ids.slice(k, k + 6));
      await p.setViewportSize({ width: 1100, height: 760 }); await p.screenshot({ path: path.join(dir, 'svg-' + String(k / 6).padStart(2, '0') + '.png') });
    }
    console.log('svg sayfası:', Math.ceil(ids.length / 6));
  }
  await b.close();
})();
