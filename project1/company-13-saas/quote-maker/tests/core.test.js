// 실행: node --test /home/user/auto-trading-bot/project1/company-13-saas/quote-maker/tests/core.test.js
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const C = require('../js/core.js');

const calc = (rows, mode) => C.calculate(rows, mode);
const sum3 = (r) => [r.supply, r.vat, r.total];

test('부가세 별도: 기본', () => {
  const r = calc([{ qty: '3', price: '110000' }], 'separate');
  assert.ok(r.ok);
  assert.deepStrictEqual(sum3(r), [330000n, 33000n, 363000n]);
});

test('부가세 별도: 세액 원 미만 반올림', () => {
  // 15 * 10% = 1.5 -> 2, 14 * 10% = 1.4 -> 1, 1234 -> 123.4 -> 123, 1235 -> 123.5 -> 124
  assert.deepStrictEqual(sum3(calc([{ qty: '1', price: '15' }], 'separate')), [15n, 2n, 17n]);
  assert.deepStrictEqual(sum3(calc([{ qty: '1', price: '14' }], 'separate')), [14n, 1n, 15n]);
  assert.deepStrictEqual(sum3(calc([{ qty: '1', price: '1234' }], 'separate')), [1234n, 123n, 1357n]);
  assert.deepStrictEqual(sum3(calc([{ qty: '1', price: '1235' }], 'separate')), [1235n, 124n, 1359n]);
});

test('부가세 별도: 세액은 품목별이 아니라 합계에 한 번 계산', () => {
  // 품목별로 반올림하면 2+2=4지만 합계 30*10%=3
  const r = calc([{ qty: '1', price: '15' }, { qty: '1', price: '15' }], 'separate');
  assert.deepStrictEqual(sum3(r), [30n, 3n, 33n]);
});

test('부가세 포함: 합계를 공급가액과 세액으로 나눔', () => {
  assert.deepStrictEqual(sum3(calc([{ qty: '1', price: '110000' }], 'included')), [100000n, 10000n, 110000n]);
  // 100000 / 1.1 = 90909.09 -> 90909, 세액 9091
  assert.deepStrictEqual(sum3(calc([{ qty: '1', price: '100000' }], 'included')), [90909n, 9091n, 100000n]);
  // 반올림 경계: 합계 5.5*1.1 ... 6원 -> 5.4545 -> 5, 세액 1 / 17원 -> 15.4545 -> 15 /
  assert.deepStrictEqual(sum3(calc([{ qty: '1', price: '6' }], 'included')), [5n, 1n, 6n]);
  // 11*10/11 = 10 정확, 1원 -> 0.909 -> 1, 세액 0
  assert.deepStrictEqual(sum3(calc([{ qty: '1', price: '1' }], 'included')), [1n, 0n, 1n]);
  // x.5 경계: 합계 n 에 대해 10n/11 의 소수부는 k/11 이라 정확히 .5가 나오지 않음 -> 모든 n에서 공급가액+세액=합계 확인
  for (let n = 0n; n < 2000n; n++) {
    const t = C.splitTotals(n, 'included');
    assert.strictEqual(t.supply + t.vat, n);
    // 공급가액은 n/1.1 에서 0.5원 이내
    const diff = t.supply * 11n - n * 10n; // = 11*(supply - n/1.1)
    assert.ok(diff <= 5n && diff >= -5n, 'n=' + n);
  }
});

test('면세', () => {
  assert.deepStrictEqual(sum3(calc([{ qty: '2', price: '50000' }], 'exempt')), [100000n, 0n, 100000n]);
});

test('0원', () => {
  for (const m of C.VAT_MODES) {
    assert.deepStrictEqual(sum3(calc([{ qty: '0', price: '1000' }], m)), [0n, 0n, 0n]);
    assert.deepStrictEqual(sum3(calc([{ qty: '5', price: '0' }], m)), [0n, 0n, 0n]);
    assert.deepStrictEqual(sum3(calc([{ qty: '', price: '' }], m)), [0n, 0n, 0n]);
  }
  assert.strictEqual(C.hangulWon(0n), '일금 영원정');
});

test('소수 수량: 품목 금액 원 미만 반올림', () => {
  // 1.5 * 333 = 499.5 -> 500
  assert.strictEqual(calc([{ qty: '1.5', price: '333' }], 'exempt').rows[0].amount, 500n);
  // 0.333 * 1000 = 333
  assert.strictEqual(calc([{ qty: '0.333', price: '1000' }], 'exempt').rows[0].amount, 333n);
  // 0.001 * 499 = 0.499 -> 0, 0.001 * 500 = 0.5 -> 1
  assert.strictEqual(calc([{ qty: '0.001', price: '499' }], 'exempt').rows[0].amount, 0n);
  assert.strictEqual(calc([{ qty: '0.001', price: '500' }], 'exempt').rows[0].amount, 1n);
  // 부동소수점이면 0.1*3 오차가 나는 경우: 0.1 * 3 = 0.3 -> 0
  assert.strictEqual(calc([{ qty: '0.1', price: '3' }], 'exempt').rows[0].amount, 0n);
  // 1.005 * 1000 = 1005 (float 로는 1004.9999...)
  assert.strictEqual(calc([{ qty: '1.005', price: '1000' }], 'exempt').rows[0].amount, 1005n);
  assert.strictEqual(C.formatQty(C.parseQty('1.50').milli), '1.5');
  assert.strictEqual(C.formatQty(C.parseQty('0.005').milli), '0.005');
  assert.strictEqual(C.formatQty(C.parseQty('1,234,567').milli), '1,234,567');
});

test('큰 금액: Number 정밀도(2^53) 넘어도 정확', () => {
  const r = calc([{ qty: '999999999.999', price: '999999999999' }], 'separate');
  // 수량(milli) × 단가 / 1000 을 BigInt 반올림으로 직접 계산한 값과 비교
  const expectLine = (999999999999n * 999999999999n * 2n + 1000n) / 2000n;
  assert.strictEqual(r.rows[0].amount, expectLine);
  assert.strictEqual(r.supply, expectLine);
  assert.strictEqual(r.vat, (expectLine * 2n + 10n) / 20n);
  assert.strictEqual(r.total, r.supply + r.vat);
  assert.strictEqual(C.formatWon(12345678901234567890n), '12,345,678,901,234,567,890');
  // 100행 최대값 합계도 한글 변환 가능해야 함
  const rows = Array.from({ length: 100 }, () => ({ qty: '999999999.999', price: '999999999999' }));
  const big = calc(rows, 'separate');
  assert.ok(C.hangulWon(big.total).startsWith('일금 '));
});

test('입력 검증', () => {
  assert.ok(C.parseQty('-1').error);
  assert.ok(C.parseQty('1e3').error);
  assert.ok(C.parseQty('1.2345').error);
  assert.ok(C.parseQty('abc').error);
  assert.ok(C.parseQty('1234567890').error);
  assert.ok(C.parsePrice('10.5').error);
  assert.ok(C.parsePrice('-100').error);
  assert.ok(C.parsePrice('1234567890123').error);
  assert.strictEqual(C.parsePrice('1,000,000').won, 1000000n);
  assert.strictEqual(C.parsePrice('000120').won, 120n);
  const r = calc([{ qty: 'x', price: '100' }, { qty: '1', price: '100' }], 'separate');
  assert.strictEqual(r.ok, false);
  assert.ok(r.rows[0].qtyError);
  const half = calc([{ qty: '2', price: '' }], 'separate');
  assert.ok(half.ok && half.rows[0].incomplete && half.total === 0n);
  assert.throws(() => calc([], 'bogus'));
});

test('한글 금액', () => {
  const cases = [
    [1n, '일'], [10n, '일십'], [11n, '일십일'], [100n, '일백'], [1000n, '일천'],
    [10000n, '일만'], [10001n, '일만일'], [110000n, '일십일만'], [330000n, '삼십삼만'],
    [363000n, '삼십육만삼천'], [1000000n, '일백만'], [100000000n, '일억'], [100010000n, '일억일만'],
    [123456789n, '일억이천삼백사십오만육천칠백팔십구'], [1000000000000n, '일조'],
    [10000000000000000n, '일경'], [100000000000000000000n, '일해'], [2020n, '이천이십'], [90909n, '구만구백구']
  ];
  for (const [n, s] of cases) assert.strictEqual(C.toHangulNumber(n), s, String(n));
  assert.strictEqual(C.hangulWon(330000n), '일금 삼십삼만원정');
  assert.throws(() => C.toHangulNumber(-1n));
  assert.throws(() => C.toHangulNumber(10n ** 24n));
});

test('사업자등록번호 형식', () => {
  assert.strictEqual(C.checkBizNo('1234567890').formatted, '123-45-67890');
  assert.strictEqual(C.checkBizNo(' 123-45-67890 ').formatted, '123-45-67890');
  assert.ok(C.checkBizNo('').empty);
  assert.ok(C.checkBizNo('123-45-6789').error);
  assert.ok(C.checkBizNo('12a4567890').error);
});

test('날짜', () => {
  assert.ok(C.isValidDate('2026-10-04'));
  assert.ok(C.isValidDate('2024-02-29'));
  assert.ok(!C.isValidDate('2026-02-29'));
  assert.ok(!C.isValidDate('2026-13-01'));
  assert.strictEqual(C.formatDateKo('2026-10-04'), '2026년 10월 4일');
});

test('JSON 불러오기 정규화', () => {
  const d = C.emptyDoc('2026-10-04');
  d.items = [{ name: '<img src=x onerror=alert(1)>', spec: 'A', qty: '1', price: '100' }];
  d.supplier.name = '테스트';
  const back = C.normalizeDoc(JSON.parse(JSON.stringify(d)));
  assert.deepStrictEqual(back, d);
  assert.throws(() => C.normalizeDoc(null));
  assert.throws(() => C.normalizeDoc({ app: 'other', version: 1 }));
  assert.throws(() => C.normalizeDoc({ app: 'quote-maker', version: 2, items: [] }));
  assert.throws(() => C.normalizeDoc({ app: 'quote-maker', version: 1 }));
  assert.throws(() => C.normalizeDoc({ app: 'quote-maker', version: 1, items: Array(101).fill({}) }));
  assert.throws(() => C.normalizeDoc({ app: 'quote-maker', version: 1, items: [{ name: { x: 1 } }] }));
  const odd = C.normalizeDoc({ app: 'quote-maker', version: 1, docType: 'evil', vatMode: 'x', date: '2026-02-30', items: [], extra: 1, note: 'n'.repeat(5000), supplier: { name: 'a'.repeat(500), hack: 1 } });
  assert.strictEqual(odd.docType, 'quote');
  assert.strictEqual(odd.vatMode, 'separate');
  assert.strictEqual(odd.date, '');
  assert.strictEqual(odd.items.length, 1);
  assert.strictEqual(odd.note.length, C.LIMITS.noteMax);
  assert.strictEqual(odd.supplier.name.length, C.LIMITS.textMax);
  assert.ok(!('hack' in odd.supplier) && !('extra' in odd));
  assert.strictEqual(C.fileName({ docType: 'statement', date: '2026-10-04' }), 'statement_2026-10-04.json');
});
