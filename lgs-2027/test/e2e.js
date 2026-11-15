// Uçtan uca test: iPhone görünümü. Kullanım: node test/e2e.js [port]
const { chromium, devices } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const APP = process.env.APP || path.join(__dirname, '..', 'app'), OUT = process.env.SHOTS || path.join(__dirname, 'shots');
fs.mkdirSync(OUT, { recursive: true });
const srv = http.createServer((req, res) => {
  const f = path.join(APP, decodeURIComponent(req.url.split('?')[0].replace(/^\/$/, '/index.html')));
  fs.readFile(f, (e, b) => { if (e) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type': f.endsWith('.js') ? 'text/javascript; charset=utf-8' : 'text/html; charset=utf-8' }); res.end(b); });
});
let n = 0; const ok = (c, m) => { n++; if (!c) throw new Error('BAŞARISIZ: ' + m); console.log('  ✓ ' + m); };
(async () => {
  await new Promise(r => srv.listen(0, r)); const url = 'http://127.0.0.1:' + srv.address().port + '/';
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ ...devices['iPhone 13'], locale: 'tr-TR', timezoneId: 'Europe/Istanbul' });
  const page = await ctx.newPage(); const errs = [];
  page.on('pageerror', e => errs.push(String(e))); page.on('console', m => { if (m.type() === 'error' && !/fonts\.g|ERR_|Failed to load resource/.test(m.text())) errs.push(m.text()); });
  await page.clock.install({ time: new Date('2026-11-16T17:00:00+03:00') });
  await page.goto(url);
  const st = () => page.evaluate(() => JSON.parse(localStorage.getItem('lgs27.v1')));
  const curQ = async () => { const s = await st(); return page.evaluate(id => window.LGS_QUESTIONS.find(q => q.id === id), s.ses.cur.qid); };
  const noOverflow = async (ad) => { const o = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth); ok(o <= 1, ad + ': yatay taşma yok'); };
  const shot = (ad) => page.screenshot({ path: path.join(OUT, ad + '.png') });
  const answer = async (dogru) => { const q = await curQ(); const i = dogru ? q.dogru : (q.dogru + 1) % 4;
    await page.locator('.opt').nth(i).click(); await page.click('[data-a=cevapla]'); return q; };
  const gec = async () => { await page.clock.fastForward(4000); };

  console.log('1) Başla: ad ve konu seçimi');
  await page.fill('#ad', 'Ela'); await page.click('form[data-f=ad] button[type=submit]');
  ok(await page.locator('h1').innerText() === 'Merhaba Ela', 'selamlama adla görünüyor');
  await noOverflow('başla'); await shot('01-basla');
  await page.locator('details.ders.d-matematik summary').click();
  const chip = page.locator('details.d-matematik [data-a=konu]').first(); const konu = await chip.getAttribute('data-k'); await chip.click();
  await page.click('[data-a=adet][data-n="5"]'); await shot('02-konu-secimi');
  await page.click('[data-a=basla]');
  let q = await curQ(); ok((q.ders + '|' + q.unite) === konu, 'seçilen konudan soru geldi: ' + konu);
  ok(await page.locator('#tabs').isHidden(), 'soru ekranında sekmeler gizli');

  console.log('2) İpucu kademeleri');
  ok(await page.locator('.box.hint').count() === 0, 'başta ipucu kapalı');
  await page.click('[data-a=ipucu]'); ok(await page.locator('.box.hint').count() === 1, 'ipucu 1 açıldı');
  await page.click('[data-a=ipucu]'); ok(await page.locator('.box.hint').count() === 2, 'ipucu 2 açıldı');
  ok(await page.locator('[data-a=cevapla]').isDisabled(), 'şık seçmeden onay kapalı');
  await noOverflow('soru'); await shot('03-soru-ipucu');

  console.log('3) Döndürme: durum korunuyor');
  await page.locator('.opt').nth((q.dogru + 1) % 4).click();
  await page.setViewportSize({ width: 844, height: 390 });
  ok(await page.locator('.opt.sel').count() === 1 && await page.locator('.box.hint').count() === 2, 'yatay konumda seçim ve ipuçları duruyor');
  await noOverflow('yatay'); await page.setViewportSize({ width: 390, height: 664 });

  console.log('4) Yanlış cevap → çözüm → benzer soru');
  await page.click('[data-a=cevapla]');
  ok(await page.locator('.box.bad .verdict').innerText() === 'Bu sefer olmadı', 'yanlış geri bildirimi');
  ok(await page.locator('ol.steps li').count() >= 2, 'adım adım çözüm görünüyor');
  ok((await page.locator('#gb').textContent()).includes('neden cazip'), 'seçilen şıkkın tuzağı açıklanıyor');
  ok((await page.locator('#gb').textContent()).includes('Taktik') && (await page.locator('#gb').textContent()).includes('Anahtar kavram'), 'taktik ve kavram görünüyor');
  ok(await page.locator('[data-a=ileri]').isDisabled(), 'çözüm okunmadan ilerlenemiyor');
  await shot('04-yanlis-cozum'); await gec();
  ok(await page.locator('[data-a=ileri]').isEnabled(), 'kısa beklemeden sonra düğmeler açılıyor');
  await page.locator('[data-a=ht][data-k=dikkat]').click();
  const kz = q.kazanimKod, ilkId = q.id; await gec(); await page.click('[data-a=benzer]');
  q = await curQ(); ok(q.id !== ilkId && (q.kazanimKod === kz || (q.ders + '|' + q.unite) === konu), 'benzer soru aynı kazanım/konudan, farklı soru');
  ok((await page.locator('#main').textContent()).includes('Benzer soru'), 'benzer soru etiketi');
  await answer(true); ok(await page.locator('.box.good .verdict').innerText() === 'Doğru', 'doğru geri bildirimi');
  ok(await page.locator('ol.steps li').count() >= 2, 'doğruda da çözüm gösteriliyor'); await shot('05-dogru');

  console.log('5) Seansı bitir → özet');
  for (let i = 0; i < 12; i++) { if (!(await page.locator('[data-a=ileri]').count())) break; await page.click('[data-a=ileri]'); if (await page.locator('[data-a=ozetKapat]').count()) break; await answer(true); }
  ok(await page.locator('[data-a=ozetKapat]').count() === 1, 'özet ekranı açıldı');
  ok((await page.locator('#main').textContent()).includes('Takıldığın yer'), 'somut tek cümlelik geri bildirim'); await shot('06-ozet');
  await page.click('[data-a=ozetKapat]');

  console.log('6) Hata defteri ve aralıklı tekrar');
  await page.click('[data-a=tab][data-t=defter]');
  let s = await st(); ok(s.errors.length === 1 && s.errors[0].ht === 'dikkat' && s.errors[0].kz === kz, 'defterde 1 kayıt, hata tipi kaydedildi');
  ok((await page.locator('#main').textContent()).includes('2 gün sonra'), 'tekrar 2 gün sonraya planlandı'); await shot('07-defter');
  await page.clock.setSystemTime(new Date('2026-11-18T17:00:00+03:00')); await page.reload();
  ok((await page.locator('#main').textContent()).includes('Tekrar günü'), '2 gün sonra Başla ekranında tekrar günü uyarısı');
  await page.click('[data-a=tab][data-t=defter]'); await page.click('[data-a=tekrar]');
  q = await curQ(); ok((q.kazanimKod === kz || (q.ders + '|' + q.unite) === konu) && q.id !== ilkId, 'tekrar sorusu aynı kazanım/konudan, farklı soru (' + (q.kazanimKod === kz ? 'aynı kazanım' : 'aynı konu') + ')');
  ok((await page.locator('#main').textContent()).includes('Tekrar günü'), 'tekrar günü rozeti'); await shot('08-tekrar-gunu');
  await answer(true); await page.click('[data-a=ileri]'); await page.click('[data-a=ozetKapat]');
  s = await st(); ok(s.errors[0].ok === 1 && !s.errors[0].closed, 'ilk tekrar doğru: kayıt açık, 5 gün sonraya');
  await page.clock.setSystemTime(new Date('2026-11-23T17:00:00+03:00')); await page.reload();
  await page.click('[data-a=tab][data-t=defter]'); await page.click('[data-a=tekrar]'); await answer(true);
  ok((await page.locator('.box.good').textContent()).includes('Hata defterinden çıktı'), 'ikinci doğru: kayıt kapandı');
  await page.click('[data-a=ileri]'); await page.click('[data-a=ozetKapat]');
  s = await st(); ok(s.errors[0].closed === true, 'kayıt kapalı');

  console.log('7) Kavram kartları');
  await page.click('[data-a=tab][data-t=kartlar]'); await noOverflow('kartlar'); await page.locator('[data-a=kartBasla]').first().click();
  await page.click('[data-a=kartCevir]'); ok(await page.locator('.box.acc').count() === 1, 'kart çevrildi, kural görünüyor');
  await page.locator('.opt').first().click(); await shot('09-kart');
  s = await st(); ok(Object.keys(s.cards).length === 1, 'kart sonucu kaydedildi'); await page.click('[data-a=kartKapat]');

  console.log('8) Mini deneme');
  await page.click('[data-a=tab][data-t=deneme]'); await page.click('[data-a=denemeBasla][data-id=inkilap]');
  ok(await page.locator('#saat').innerText() === '15:00', 'süre 15:00');
  await page.locator('.opt').first().click(); await page.clock.fastForward(65000);
  const t = await page.locator('#saat').innerText(); ok(/^13:5\d$/.test(t), 'sayaç işliyor (' + t + ')'); await shot('10-deneme');
  await page.click('[data-a=dGit][data-i="1"]'); await page.locator('.opt').nth(1).click();
  await page.locator('[data-a=dBitirSor]').first().click(); await page.click('[data-a=dBitir]');
  ok((await page.locator('#main').textContent()).includes('net'), 'deneme sonucu ve net'); await noOverflow('sonuç'); await shot('11-deneme-sonuc');
  await page.click('[data-a=sonucKapat]');

  console.log('9) Taktikler ve MEB');
  await page.click('[data-a=tab][data-t=taktikler]'); ok(await page.locator('details.ders').count() >= 9, 'taktik başlıkları'); await noOverflow('taktikler'); await shot('12-taktikler');
  await page.click('[data-a=tab][data-t=meb]'); const nl = await page.locator('.lnk a').count(); ok(nl >= 10, 'MEB bağlantıları (' + nl + ')'); await shot('13-meb');

  console.log('10) İlerleme, Babama göster, dışa/içe aktarma');
  await page.click('[data-a=tab][data-t=ilerleme]'); await noOverflow('ilerleme'); await shot('14-ilerleme');
  await page.click('[data-a=baba]'); ok((await page.locator('#main').textContent()).includes('Öneri'), 'baba özeti'); await shot('15-baba'); await page.locator('[data-a=babaKapat]').last().click();
  const once = await st(); await page.click('[data-a=kodUret]'); const kod = await page.locator('#kodOut').inputValue();
  ok(kod.startsWith('LGS27:') && kod.length > 200, 'dışa aktarma kodu üretildi (' + kod.length + ' karakter)');
  await page.click('[data-a=sifirlaSor]'); await page.click('[data-a=sifirla]');
  s = await st(); ok(Object.keys(s.q).length === 0 && s.name === '', 'ilerleme silindi');
  await page.click('[data-a=tab][data-t=ilerleme]'); await page.fill('#kodIn', 'LGS27:bozuk'); await page.click('[data-a=iceAktarSor]');
  ok((await page.locator('#iceMsg').innerText()).length > 5, 'bozuk kodda anlaşılır hata');
  await page.fill('#kodIn', kod); await page.click('[data-a=iceAktarSor]'); await page.click('[data-a=iceAktar]'); await page.click('[data-a=sheetKapat]');
  s = await st(); ok(s.name === 'Ela' && Object.keys(s.q).length === Object.keys(once.q).length && s.errors.length === once.errors.length && s.exams.length === 1, 'içe aktarma ilerlemeyi geri getirdi');

  console.log('11) Karışık seans: art arda farklı konular; depolama kapalıyken çalışma');
  await page.click('[data-a=tab][data-t=basla]'); await page.click('[data-a=hizli]');
  s = await st(); const keys = s.ses.slots.map(x => x.key); ok(keys.length === 10 && keys.every((k, i) => i === 0 || k !== keys[i - 1]), 'karışık modda art arda aynı konu yok');
  ok(errs.length === 0, 'konsol hatası yok ' + JSON.stringify(errs));
  const p2 = await ctx.newPage(); await p2.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('kapalı'); } }); });
  const e2 = []; p2.on('pageerror', e => e2.push(String(e))); await p2.goto(url);
  ok((await p2.locator('#main').textContent()).includes('saklamaya izin vermiyor') && e2.length === 0, 'localStorage yokken uyarı veriyor, çökmüyor');
  await p2.click('[data-a=hizli]'); ok(await p2.locator('.opt').count() === 4, 'depolama olmadan da soru açılıyor');
  await browser.close(); srv.close(); console.log('\nTümü geçti: ' + n + ' kontrol');
})().catch(e => { console.error(e.message || e); process.exit(1); });
