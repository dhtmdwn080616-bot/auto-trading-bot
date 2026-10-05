# photo-size (13번 사업체 첫 제품, MVP)

정적 파일만으로 동작하는 증명·여권사진 규격 맞추기 도구. 사진은 브라우저 안에서만 처리된다.

- `index.html` 도구 / `guide.html` 가이드 / `about.html` 소개 / `privacy.html` 개인정보 안내
- `js/core.js` 순수 로직(크롭 계산, JPEG 품질 이분 탐색) / `js/app.js` 화면 / `css/style.css`
- 전송 차단 근거: 모든 페이지 CSP `connect-src 'none'`, `default-src 'none'`, 외부 리소스 없음, 쿠키·저장소 미사용.

## 테스트
- 단위: `node --test tests/core.test.js`
- E2E: 이 폴더에서 `python3 -m http.server 8765 --bind 127.0.0.1` 실행 후
  `IMG_DIR=<이미지폴더> OUT_DIR=<출력폴더> CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome node tests/e2e.cjs`
  필요한 이미지(PIL로 생성): noise_3000x4000.jpg, portrait_2400x3200.png, noise_413x531.png, noise_1600x2000.png, small_200x260.jpg

## 남은 일 / 부채
- 프리셋 숫자는 2차 출처. 외교부 등 1차 출처 확인 전 확정 아님(QA).
- privacy/about의 [대표 확정] 자리표시자(운영자, 문의, 시행일, 호스팅).
- 실제 iOS/Android 기기 터치·HEIC 미검증. EXIF 회전은 브라우저 기본 동작에 의존(실기기 미검증).
- 배포 시 tests/ 폴더 제외 권장. HTTP 헤더 CSP(호스팅 설정)로 meta CSP 보강 권장.
