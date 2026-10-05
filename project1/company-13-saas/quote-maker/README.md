# quote-maker (13번 사업체 두 번째 제품, MVP)

정적 파일만으로 동작하는 견적서·거래명세서 생성기. 입력 내용은 브라우저 안에서만 쓰인다.

- `index.html` 도구 / `guide.html` 작성 가이드 / `about.html` 소개 / `privacy.html` 개인정보 안내
- `js/core.js` 순수 로직(BigInt 금액 계산, 반올림, 한글 금액, 사업자번호 형식, JSON 정규화) / `js/app.js` 화면 / `css/style.css`(photo-size 기반 + 인쇄 CSS)
- 전송 차단 근거: 모든 페이지 CSP `default-src 'none'; connect-src 'none'; form-action 'none'`, 외부 리소스 없음, 쿠키·localStorage·sessionStorage 미사용, 사용자 입력은 textContent/value로만 출력(innerHTML 없음).
- 저장은 .json 내려받기/불러오기만(파일 이름 ASCII: `quote_YYYY-MM-DD.json`, `statement_...`).

## 계산 규칙 (화면·가이드와 동일하게 유지)
- 금액은 원 단위 BigInt, 수량은 소수 3자리까지(×1000 정수).
- 품목 금액 = 수량 × 단가, 원 미만 반올림(0.5 이상 올림).
- 별도: 세액 = 공급가액 합계 × 10% 반올림(합계에 1회). 포함: 공급가액 = 합계 ÷ 1.1 반올림, 세액 = 합계 − 공급가액. 면세: 세액 0.
- 한글 금액은 1도 '일'을 붙임(일십일만). 한도는 '해' 단위(24자리) — 입력 한도(단가 12자리, 수량 정수 9자리, 100행)로 넘지 않게 함.

## 테스트
- 단위: `node --test tests/core.test.js`
- E2E: 이 폴더에서 `python3 -m http.server 8766 --bind 127.0.0.1` 실행 후
  `OUT_DIR=<출력폴더> CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome node tests/e2e.cjs`
  (캡처: desktop_full / mobile_full / dark_desktop / print_media.png, 인쇄 PDF: statement.pdf, long.pdf)

## 남은 일 / 부채
- 반올림 규칙 고정(반올림). 절사·품목별 세액 방식 옵션 없음 → 거래처와 1원 차이 가능(화면에 안내).
- 사업자등록번호는 10자리 형식만 검사(검증번호 계산·진위 확인 없음).
- 가이드의 견적서/거래명세서 설명은 일반적 용례 수준, 세무 1차 출처 미확인 → 세무사·국세청 확인 유도 문구로 처리.
- 실제 iOS/Android 인쇄·PDF 저장, Safari/Firefox 인쇄 레이아웃 미검증(headless Chromium만 확인).
- 직인(도장) 이미지 넣기 없음. 할인(음수) 행 미지원.
- 배포 시 tests/ 제외 권장. HTTP 헤더 CSP로 meta CSP 보강 권장.
