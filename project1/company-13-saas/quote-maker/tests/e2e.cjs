/*
 * 브라우저 E2E 검증 (로컬 서버 필요)
 *   python3 -m http.server 8766 --bind 127.0.0.1   (quote-maker 폴더에서)
 *   OUT_DIR=<결과 폴더> CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome node tests/e2e.cjs
 * 확인 항목: 계산·한글 금액 화면 반영, 행 추가/삭제, 사업자번호 형식, JSON 내려받기→불러오기 왕복,
 *   XSS 문자열이 HTML로 해석되지 않음, localhost 외 요청 0건, CSP가 fetch 차단, 쿠키·저장소 미사용,
 *   데스크톱/모바일/다크 캡처와 인쇄 PDF 생성.
 */
'use strict';
const path = require('path');
const fs = require('fs');
const { chromium } = require(process.env.PLAYWRIGHT || '/opt/node22/lib/node_modules/playwright');

const BASE = process.env.BASE || 'http://127.0.0.1:8766/';
const OUT = process.env.OUT_DIR;
const EXE = process.env.CHROME || undefined;

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ acceptDownloads: true, viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const external = [];
  const errors = [];
  page.on('request', (r) => { const u = r.url(); if (!u.startsWith(BASE) && !u.startsWith('blob:') && !u.startsWith('data:')) external.push(u); });
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('dialog', (d) => d.accept());

  const checks = [];
  const ok = (name, cond, extra) => checks.push({ name, pass: !!cond, ...(extra !== undefined ? { got: extra } : {}) });
  const txt = (sel) => page.locator(sel).first().textContent();
  const totals = async () => ({ s: await txt('#t-supply'), v: await txt('#t-vat'), t: await txt('#t-total'), h: await txt('#t-hangul') });

  await page.goto(BASE + 'index.html');
  ok('작성일 기본값 오늘', /^\d{4}-\d{2}-\d{2}$/.test(await page.inputValue('#doc-date')));
  ok('초기 삭제 버튼 비활성(1행)', await page.locator('.btn-del').first().isDisabled());

  await page.fill('#supplier-bizNo', '1234567890');
  await page.fill('#supplier-name', '예시상사');
  await page.fill('#supplier-ceo', '홍길동');
  await page.fill('#supplier-address', '서울특별시 예시구 예시로 1');
  await page.fill('#supplier-bizType', '서비스');
  await page.fill('#supplier-bizItem', '소프트웨어 개발');
  await page.fill('#supplier-phone', '02-000-0000');
  await page.fill('#client-name', '받는회사');
  await page.focus('#client-name');
  ok('사업자번호 하이픈 자동 정리', (await page.inputValue('#supplier-bizNo')) === '123-45-67890');
  await page.fill('#client-bizNo', '123');
  await page.focus('#client-name');
  ok('사업자번호 형식 오류 표시', (await txt('#client-bizNo-msg')).includes('10자리') && (await page.getAttribute('#client-bizNo', 'aria-invalid')) === 'true');
  await page.fill('#client-bizNo', '');
  await page.focus('#client-name');

  const row = (i) => page.locator('#items > li').nth(i);
  await row(0).locator('[data-field=name]').fill('웹사이트 제작');
  await row(0).locator('[data-field=spec]').fill('반응형 5페이지');
  await row(0).locator('[data-field=qty]').fill('3');
  await row(0).locator('[data-field=price]').fill('110000');
  let t = await totals();
  ok('별도 1행: 330,000 / 33,000 / 363,000', t.s === '330,000원' && t.v === '33,000원' && t.t === '363,000원' && t.h === '일금 삼십육만삼천원정', t);

  // 키보드로 품목 추가: 포커스가 새 행 품명으로 이동해야 함
  await page.focus('#add-item');
  await page.keyboard.press('Enter');
  ok('키보드로 행 추가 후 포커스 이동', await page.evaluate(() => document.activeElement === document.querySelectorAll('#items input[data-field=name]')[1]));
  await page.keyboard.type('유지보수');
  await row(1).locator('[data-field=spec]').fill('월');
  await row(1).locator('[data-field=qty]').fill('1.5');
  await row(1).locator('[data-field=price]').fill('333');
  t = await totals();
  ok('별도 2행(소수 수량 반올림): 330,500 / 33,050 / 363,550', t.s === '330,500원' && t.v === '33,050원' && t.t === '363,550원', t);
  ok('행 금액 표시 1.5×333=500', (await row(1).locator('.item-amount').textContent()) === '500');
  await row(1).locator('[data-field=price]').blur();
  await page.locator('#items input[data-field=price]').first().focus();
  await page.locator('#note').focus();
  ok('단가 천 단위 쉼표 정리', (await row(0).locator('[data-field=price]').inputValue()) === '110,000');

  await page.check('input[name=vatMode][value=included]');
  t = await totals();
  ok('포함: 330,500 -> 300,455 / 30,045', t.s === '300,455원' && t.v === '30,045원' && t.t === '330,500원', t);
  await page.check('input[name=vatMode][value=exempt]');
  t = await totals();
  ok('면세: 세액 0', t.s === '330,500원' && t.v === '0원' && t.t === '330,500원', t);
  await page.check('input[name=vatMode][value=separate]');

  await row(1).locator('[data-field=qty]').fill('abc');
  t = await totals();
  ok('잘못된 수량: 합계 비움 + aria-invalid', t.t === '-' && (await row(1).locator('[data-field=qty]').getAttribute('aria-invalid')) === 'true', t);
  ok('미리보기도 입력 확인 필요', (await txt('.doc-sum-hangul')) === '입력 확인 필요');
  await row(1).locator('[data-field=qty]').fill('1.5');

  // XSS 문자열은 글자 그대로 표시되어야 함
  await page.fill('#note', '<img src=x onerror="document.title=\'pwned\'">\n두 번째 줄');
  ok('비고 XSS 미해석', (await page.locator('#doc img').count()) === 0 && (await page.title()) !== 'pwned' && (await txt('.doc-note p')).includes('<img'));
  await page.fill('#note', '견적 유효기간: 작성일로부터 30일\n결제: 계약 시 50%, 완료 시 50%');

  ok('미리보기 제목 견적서', (await txt('.doc-title')) === '견 적 서');
  ok('미리보기 합계 한글', (await txt('.doc-sum-hangul')) === '일금 삼십육만삼천오백오십원정');
  ok('미리보기 공급자 등록번호', (await page.locator('.doc-supplier td').first().textContent()) === '123-45-67890');

  // 데스크톱 캡처 (견적서)
  await page.screenshot({ path: path.join(OUT, 'desktop_full.png'), fullPage: true });

  // JSON 내려받기 -> 새로 작성 -> 불러오기
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#save-json')]);
  const jsonPath = path.join(OUT, dl.suggestedFilename());
  await dl.saveAs(jsonPath);
  const saved = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
  ok('JSON 파일명/내용', /^quote_\d{4}-\d{2}-\d{2}\.json$/.test(dl.suggestedFilename()) && saved.items.length === 2 && saved.items[1].qty === '1.5' && saved.supplier.name === '예시상사', dl.suggestedFilename());
  await page.click('#reset-doc');
  ok('새로 작성 후 비어 있음', (await page.inputValue('#supplier-name')) === '' && (await page.locator('#items > li').count()) === 1 && (await totals()).t === '0원');
  await page.setInputFiles('#load-json', jsonPath);
  await page.waitForFunction(() => document.getElementById('file-status').textContent.includes('불러왔습니다'));
  t = await totals();
  ok('불러오기 후 복원', (await page.inputValue('#supplier-name')) === '예시상사' && (await page.locator('#items > li').count()) === 2 && t.t === '363,550원' && (await page.inputValue('#note')).includes('30일'), t);
  // 잘못된 파일
  const badPath = path.join(OUT, 'bad.json');
  fs.writeFileSync(badPath, '{"app":"other"}');
  await page.setInputFiles('#load-json', badPath);
  await page.waitForFunction(() => document.getElementById('file-status').className.includes('error'));
  ok('잘못된 파일 거부, 기존 내용 유지', (await page.inputValue('#supplier-name')) === '예시상사');

  // 행 삭제
  await row(0).locator('.btn-del').click();
  t = await totals();
  ok('1행 삭제 후 합계 = 500 + 50', t.s === '500원' && t.v === '50원' && t.t === '550원', t);
  ok('삭제 후 남은 1행 삭제 버튼 비활성', await page.locator('.btn-del').first().isDisabled());
  ok('삭제 안내 live region', (await txt('#items-status')).includes('삭제했습니다'));
  // 다시 불러와 거래명세서로
  await page.setInputFiles('#load-json', jsonPath);
  await page.waitForFunction(() => document.querySelectorAll('#items > li').length === 2);
  await page.check('input[name=docType][value=statement]');
  ok('거래명세서 제목', (await txt('.doc-title')) === '거 래 명 세 서');

  // 개인정보: 저장소·쿠키·네트워크
  const store = await page.evaluate(() => ({ ls: localStorage.length, ss: sessionStorage.length, cookie: document.cookie }));
  ok('localStorage/sessionStorage/cookie 비어 있음', store.ls === 0 && store.ss === 0 && store.cookie === '', store);
  const fetchBlocked = await page.evaluate(() => fetch(location.href).then(() => false, () => true));
  ok('CSP가 같은 출처 fetch도 차단', fetchBlocked);
  // sendBeacon은 true를 돌려줄 수 있으므로 CSP 위반 이벤트(connect-src)가 나는지와 서버 도달 여부로 확인
  let beaconReached = false;
  page.on('requestfinished', (r) => { if (r.url().includes('/beacon-test')) beaconReached = true; });
  const violation = await page.evaluate(() => new Promise((res) => {
    document.addEventListener('securitypolicyviolation', (e) => res(e.effectiveDirective), { once: true });
    try { navigator.sendBeacon('/beacon-test', 'a'); } catch (e) { res('threw'); }
    setTimeout(() => res('none'), 2000);
  }));
  await page.waitForTimeout(300);
  ok('sendBeacon 차단(connect-src 위반)', (violation === 'connect-src' || violation === 'threw') && !beaconReached, violation);

  // 인쇄: print 미디어 캡처 + PDF
  await page.emulateMedia({ media: 'print' });
  await page.screenshot({ path: path.join(OUT, 'print_media.png'), fullPage: true });
  const formVisible = await page.locator('#editor').isVisible();
  ok('인쇄 시 입력 폼 숨김', !formVisible);
  await page.pdf({ path: path.join(OUT, 'statement.pdf'), format: 'A4', preferCSSPageSize: true });
  await page.emulateMedia({ media: 'screen' });

  // 품목 많을 때 PDF (여러 쪽, 머리행 반복 확인용)
  await page.evaluate(() => { for (let i = 0; i < 38; i++) document.getElementById('add-item').click(); });
  await page.evaluate(() => {
    document.querySelectorAll('#items > li').forEach((li, i) => {
      if (i < 2) return;
      li.querySelector('[data-field=name]').value = '추가 품목 ' + (i + 1);
      li.querySelector('[data-field=qty]').value = '1';
      li.querySelector('[data-field=price]').value = '10000';
    });
    document.getElementById('note').dispatchEvent(new Event('input', { bubbles: true }));
  });
  ok('40행 합계(363,550 + 38×11,000)', (await txt('#t-total')) === (363550 + 38 * 11000).toLocaleString('en-US') + '원', await txt('#t-total'));
  await page.emulateMedia({ media: 'print' });
  await page.pdf({ path: path.join(OUT, 'long.pdf'), format: 'A4', preferCSSPageSize: true });
  await page.emulateMedia({ media: 'screen' });

  // 다크 모드 데스크톱
  const dark = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: 'dark' });
  const dp = await dark.newPage();
  dp.on('request', (r) => { if (!r.url().startsWith(BASE)) external.push(r.url()); });
  await dp.goto(BASE + 'index.html');
  await dp.fill('#client-name', '받는회사');
  await dp.locator('[data-field=name]').fill('품목');
  await dp.locator('[data-field=qty]').fill('2');
  await dp.locator('[data-field=price]').fill('15000');
  await dp.screenshot({ path: path.join(OUT, 'dark_desktop.png'), fullPage: true });

  // 모바일 폭
  const mob = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const mp = await mob.newPage();
  mp.on('request', (r) => { if (!r.url().startsWith(BASE)) external.push(r.url()); });
  mp.on('pageerror', (e) => errors.push(String(e)));
  await mp.goto(BASE + 'index.html');
  await mp.locator('[data-field=name]').fill('웹사이트 제작');
  await mp.locator('[data-field=qty]').fill('3');
  await mp.locator('[data-field=price]').fill('110000');
  await mp.click('#add-item');
  const pageOverflow = await mp.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok('모바일 페이지 가로 넘침 없음', pageOverflow <= 0, pageOverflow);
  await mp.screenshot({ path: path.join(OUT, 'mobile_full.png'), fullPage: true });
  for (const p of ['guide.html', 'about.html', 'privacy.html']) {
    await mp.goto(BASE + p);
    const ov = await mp.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    ok(p + ' 모바일 가로 넘침 없음', ov <= 0, ov);
    if (p === 'guide.html') await mp.screenshot({ path: path.join(OUT, 'mobile_guide.png'), fullPage: true });
  }

  ok('외부 요청 0건', external.length === 0, external);
  const unexpected = errors.filter((e) => !/Content Security Policy|connect-src|Failed to fetch/.test(e));
  ok('예상 외 콘솔 오류 없음', unexpected.length === 0, unexpected);

  const failed = checks.filter((c) => !c.pass);
  console.log(JSON.stringify({ total: checks.length, failed: failed.length, checks }, null, 1));
  await browser.close();
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
