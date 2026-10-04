/*
 * 브라우저 E2E 검증 (로컬 서버 필요)
 *   python3 -m http.server 8765 --bind 127.0.0.1   (photo-size 폴더에서)
 *   IMG_DIR=<테스트 이미지 폴더> OUT_DIR=<결과 폴더> node tests/e2e.cjs
 * 테스트 이미지(노이즈/합성 인물)는 저장소에 넣지 않는다. 생성 방법은 README 참고.
 * 확인 항목: 실제 다운로드 파일 용량 <= 목표, px 일치, localhost 외 요청 0건, CSP가 fetch 차단.
 */
'use strict';
const path = require('path');
const fs = require('fs');
const { chromium } = require(process.env.PLAYWRIGHT || '/opt/node22/lib/node_modules/playwright');

const BASE = process.env.BASE || 'http://127.0.0.1:8765/';
const IMG = process.env.IMG_DIR;
const OUT = process.env.OUT_DIR;
const EXE = process.env.CHROME || undefined;

function jpegSize(buf) {
  // SOF0/SOF2 마커에서 가로·세로 읽기
  let i = 2;
  while (i < buf.length) {
    if (buf[i] !== 0xff) { i++; continue; }
    const m = buf[i + 1];
    const len = buf.readUInt16BE(i + 2);
    if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) {
      return { h: buf.readUInt16BE(i + 5), w: buf.readUInt16BE(i + 7) };
    }
    i += 2 + len;
  }
  return null;
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ acceptDownloads: true, viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const external = [];
  const consoleErrors = []; // CSP 위반 메시지는 fetch 차단 확인용으로 기대되는 것
  page.on('request', (r) => { if (!r.url().startsWith(BASE) && !r.url().startsWith('blob:') && !r.url().startsWith('data:')) external.push(r.url()); });
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', (e) => consoleErrors.push(String(e)));

  await page.goto(BASE + 'index.html');
  const results = [];
  let fail = 0;

  async function waitDone() {
    await page.waitForFunction(() => {
      const s = document.getElementById('result-status');
      return s.textContent && s.textContent !== '변환 중...';
    }, null, { timeout: 60000 });
    await page.waitForTimeout(400); // 디바운스 후 재실행 대비
    await page.waitForFunction(() => document.getElementById('result-status').textContent !== '변환 중...', null, { timeout: 60000 });
  }

  async function check(name, file, setup, expect) {
    await page.setInputFiles('#file', path.join(IMG, file));
    await waitDone();
    if (setup) { await setup(); await waitDone(); }
    const info = await page.evaluate(() => ({
      status: document.getElementById('result-status').textContent,
      cls: document.getElementById('result-status').className,
      px: document.getElementById('r-px').textContent,
      size: document.getElementById('r-size').textContent,
      q: document.getElementById('r-quality').textContent,
      kb: Number(document.getElementById('out-kb').value),
      dl: document.getElementById('download').getAttribute('aria-disabled')
    }));
    const row = { name, ...info };
    if (expect.ok) {
      const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#download')]);
      const dest = path.join(OUT, name + '.jpg');
      await dl.saveAs(dest);
      const buf = fs.readFileSync(dest);
      const dim = jpegSize(buf);
      row.fileBytes = buf.length;
      row.fileDim = dim;
      row.pass = info.cls.includes('ok') && buf.length <= info.kb * 1000 &&
        (!expect.w || (dim.w === expect.w && dim.h === expect.h));
    } else {
      row.pass = info.cls.includes('error') && info.dl === 'true';
    }
    if (!row.pass) fail++;
    results.push(row);
  }

  await check('passport_noise3000', 'noise_3000x4000.jpg', null, { ok: true, w: 413, h: 531 });
  await check('passport_portrait_zoomed', 'portrait_2400x3200.png', async () => {
    await page.focus('#stage');
    for (let i = 0; i < 5; i++) await page.keyboard.press('+');
    await page.keyboard.press('Shift+ArrowLeft');
    await page.keyboard.press('ArrowUp');
  }, { ok: true, w: 413, h: 531 });
  await check('id3x4_noise413', 'noise_413x531.png', async () => {
    await page.selectOption('#preset', 'id3x4');
  }, { ok: true, w: 354, h: 472 });
  await check('custom_600x800_60KB_noise1600', 'noise_1600x2000.png', async () => {
    await page.fill('#out-w', '600');
    await page.fill('#out-h', '800');
    await page.fill('#out-kb', '60');
  }, { ok: true, w: 600, h: 800 });
  await check('custom_impossible_5KB_noise413', 'noise_413x531.png', async () => {
    await page.fill('#out-w', '413');
    await page.fill('#out-h', '531');
    await page.fill('#out-kb', '5');
  }, { ok: false });
  await check('keep_aspect_500KB_noise1600', 'noise_1600x2000.png', async () => {
    await page.selectOption('#preset', 'size500');
  }, { ok: true });
  await check('keep_aspect_shrink_6KB_noise413', 'noise_413x531.png', async () => {
    await page.fill('#out-kb', '6');
  }, { ok: true });
  results[results.length - 1].shrunk = results[results.length - 1].status.includes('픽셀 크기를 줄였습니다');
  await check('upscale_small', 'small_200x260.jpg', async () => {
    await page.selectOption('#preset', 'passport');
  }, { ok: true, w: 413, h: 531 });
  results[results.length - 1].upscaleWarned = results[results.length - 1].status.includes('확대');

  // CSP가 같은 출처 fetch까지 막는지 확인 (connect-src 'none')
  const fetchBlocked = await page.evaluate(() =>
    fetch(location.href).then(() => false, () => true));

  console.log(JSON.stringify({ results, external, fetchBlocked, consoleErrors }, null, 2));
  await browser.close();
  if (fail || external.length || !fetchBlocked) process.exit(1);
})().catch((e) => { console.error(e); process.exit(2); });
