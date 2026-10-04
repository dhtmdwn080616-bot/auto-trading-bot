// 실행: node --test /home/user/auto-trading-bot/project1/company-13-saas/photo-size/tests/core.test.js
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const C = require('../js/core.js');

test('프리셋 기본값', () => {
  const p = C.getPreset('passport');
  assert.strictEqual(p.width, 413);
  assert.strictEqual(p.height, 531);
  assert.strictEqual(p.maxKB, 500);
  assert.ok(C.getPreset('custom'));
  assert.strictEqual(C.getPreset('nope'), null);
});

test('입력 검증', () => {
  assert.ok(C.validateSpec('413', '531', '500', false).width === 413);
  assert.ok(C.validateSpec('41.5', '531', '500', false).error);
  assert.ok(C.validateSpec('10', '531', '500', false).error);
  assert.ok(C.validateSpec('413', '', '500', false).error);
  assert.ok(C.validateSpec('413', '531', '0', false).error);
  assert.ok(C.validateSpec('', '', '500', true).keepAspect);
});

test('KB는 1000바이트 기준', () => {
  assert.strictEqual(C.kbToMaxBytes(500), 500000);
});

test('fitCrop: 비율 유지, 이미지 안, 가운데', () => {
  const c = C.fitCrop(3000, 4000, 413 / 531);
  assert.ok(Math.abs(c.w / c.h - 413 / 531) < 1e-9);
  assert.ok(c.x >= 0 && c.y >= 0 && c.x + c.w <= 3000 + 1e-9 && c.y + c.h <= 4000 + 1e-9);
  const wide = C.fitCrop(4000, 1000, 0.75);
  assert.strictEqual(wide.h, 1000);
  assert.strictEqual(wide.x, (4000 - 750) / 2);
});

test('zoom/clamp: 비율 유지, 밖으로 안 나감', () => {
  const a = 413 / 531;
  let c = C.fitCrop(1200, 1600, a);
  c = C.zoomCropTo(c, 3, 1200, 1600, a, 6);
  assert.ok(Math.abs(C.cropZoom(c, 1200, 1600, a) - 3) < 1e-9);
  assert.ok(Math.abs(c.w / c.h - a) < 1e-9);
  c = C.clampCrop({ x: -500, y: 99999, w: c.w, h: c.h }, 1200, 1600);
  assert.strictEqual(c.x, 0);
  assert.ok(Math.abs(c.y + c.h - 1600) < 1e-9);
  const z = C.zoomCropTo(c, 100, 1200, 1600, a, 6);
  assert.ok(Math.abs(C.cropZoom(z, 1200, 1600, a) - 6) < 1e-9);
  const z1 = C.zoomCropTo(c, 0.1, 1200, 1600, a, 6);
  assert.ok(Math.abs(C.cropZoom(z1, 1200, 1600, a) - 1) < 1e-9);
});

test('downscaleSteps: 마지막은 목표 크기', () => {
  const s = C.downscaleSteps(3000, 4000, 413, 531);
  assert.deepStrictEqual(s[s.length - 1], { w: 413, h: 531 });
  assert.strictEqual(s.length, 3);
  assert.deepStrictEqual(C.downscaleSteps(300, 400, 413, 531), [{ w: 413, h: 531 }]);
});

// 가짜 인코더: 품질에 따라 크기가 변하는 함수
const fake = (fn) => (q) => Promise.resolve({ size: Math.round(fn(q)) });

test('findQuality: 목표 이하 중 가장 높은 품질', async () => {
  const size = (q) => 50000 + q * 1000000; // 단조 증가
  const r = await C.findQuality(fake(size), 500000);
  assert.ok(r.ok);
  assert.ok(r.size <= 500000);
  // 정답 q* = 0.45. 7회 이분 탐색이면 오차 (0.95-0.05)/128 이내
  assert.ok(0.45 - r.quality < 0.9 / 128 + 1e-6 && r.quality <= 0.45, String(r.quality));
});

test('findQuality: 최고 품질이 이미 목표 이하면 1회로 끝', async () => {
  const r = await C.findQuality(fake(() => 1000), 500000);
  assert.ok(r.ok);
  assert.strictEqual(r.quality, 0.95);
  assert.strictEqual(r.tries.length, 1);
});

test('findQuality: 최저 품질로도 넘으면 ok=false', async () => {
  const r = await C.findQuality(fake(() => 600000), 500000);
  assert.strictEqual(r.ok, false);
  assert.ok(r.size > 500000);
});

test('findQuality: 단조가 아니어도 ok 결과는 항상 목표 이하', async () => {
  for (let seed = 1; seed < 200; seed++) {
    const size = (q) => 40000 + q * 900000 + ((Math.sin(seed * 97 + q * 1000) + 1) * 30000);
    const target = 100000 + seed * 3000;
    const r = await C.findQuality(fake(size), target);
    if (r.ok) assert.ok(r.size <= target, `seed ${seed}`);
  }
});

test('formatKB는 1000바이트 기준(목표 용량 계산과 동일)', () => {
  assert.strictEqual(C.formatKB(500000), '500.0KB');
});

test('parseExifOrientation: EXIF 방향 읽기', () => {
  const mk = (le, ori) => {
    const w16 = (v) => le ? [v & 255, v >> 8] : [v >> 8, v & 255];
    const w32 = (v) => le ? [v & 255, (v >> 8) & 255, 0, 0] : [0, 0, (v >> 8) & 255, v & 255];
    const tiff = [].concat(le ? [0x49, 0x49] : [0x4d, 0x4d], w16(42), w32(8), w16(1),
      w16(0x0112), w16(3), w32(1).map((x, i) => i === 0 && le ? 1 : x), w16(ori), [0, 0], w32(0));
    // 값(count=1)은 4바이트 영역 앞 2바이트에 short로 들어간다
    const body = [0x45, 0x78, 0x69, 0x66, 0, 0].concat(tiff);
    const len = body.length + 2;
    return Uint8Array.from([0xff, 0xd8, 0xff, 0xe1, len >> 8, len & 255].concat(body, [0xff, 0xd9]));
  };
  assert.strictEqual(C.parseExifOrientation(mk(false, 6)), 6);
  assert.strictEqual(C.parseExifOrientation(mk(true, 3)), 3);
  assert.strictEqual(C.parseExifOrientation(Uint8Array.from([0xff, 0xd8, 0xff, 0xd9, 0, 0, 0, 0, 0, 0, 0, 0])), 0);
  assert.strictEqual(C.parseExifOrientation(Uint8Array.from([1, 2, 3])), 0);
});
