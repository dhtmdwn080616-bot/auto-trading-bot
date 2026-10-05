# GitHub Pages 포트폴리오 공개 절차 (대표용)

작성: p1-cto, 2026-10-04. 대상: `project1/company-1-web/portfolio/` (index + 가상 업체 샘플 3종).

## 결론
- 저장소 `dhtmdwn080616-bot/auto-trading-bot` 은 **public** (2026-10-04 GitHub REST API 확인, `has_pages: false`). 무료 플랜에서도 Pages 사용 가능.
- 배포 워크플로 `.github/workflows/pages-portfolio.yml` 준비 완료 (저장소 루트, actionlint 통과). `main` 브랜치에 `portfolio/` 변경이 push되면 자동 배포, 수동 실행도 가능.
- 대표가 할 일: 아래 1~4단계 (약 5분). 에이전트는 push·설정 변경을 하지 않았다.
- 예상 주소: `https://dhtmdwn080616-bot.github.io/auto-trading-bot/`

## 1. 변경 사항을 main에 반영
현재 작업은 `claude/...` 브랜치의 커밋되지 않은 파일이다. 대표 승인 후 커밋 → PR → `main` 병합. (워크플로는 `main`에서만 자동 실행되고, `github-pages` 환경도 기본적으로 기본 브랜치 배포만 허용한다.)

## 2. Pages 소스를 GitHub Actions로 설정
1. GitHub에서 저장소 열기 → 상단 **Settings**
2. 왼쪽 메뉴 **Code and automation > Pages**
3. **Build and deployment > Source** 드롭다운에서 **GitHub Actions** 선택 (Deploy from a branch 아님)
4. 저장 버튼은 없다. 선택 즉시 적용된다.

## 3. Actions 허용 확인
1. **Settings > Actions > General**
2. **Actions permissions** 가 "Allow all actions..." 또는 GitHub 제작 액션(`actions/*`) 허용 상태인지 확인
3. 저장소 상단 **Actions** 탭에서 워크플로 사용 안내가 뜨면 **I understand... enable** 클릭

## 4. 첫 배포 실행과 확인
1. **Actions** 탭 → 왼쪽 **Deploy portfolio to GitHub Pages** → **Run workflow** → Branch `main` → **Run workflow**
2. 초록 체크가 뜨면 실행 상세의 `deploy` 작업에 주소가 표시된다. 또는 **Settings > Pages** 상단 "Your site is live at ..."
3. 확인: 메인 페이지, 카페/학원/병원 샘플 3개 링크 클릭, 휴대폰에서 1회 열기
4. 첫 배포 후 반영까지 1~10분 걸릴 수 있다.

## 저장소 공개 여부 확인 방법
- 저장소 첫 화면 이름 옆 배지가 **Public** / **Private**
- 또는 **Settings > General > Danger Zone > Change repository visibility** 에 현재 상태 표시
- Private이면: 무료(Free) 계정은 Pages 사용 불가. Pro 이상 유료 플랜 필요(사이트 자체는 공개됨). 이 경우 아래 대안 B 권장.

## 주의 (보안·노출)
- 이 저장소는 public이라 **포트폴리오 외 파일(bot.py, project1 내부 문서, 가격 가정, 로그 등)도 누구나 볼 수 있다.** Pages는 `portfolio/` 폴더만 배포하지만 저장소 자체 공개는 별개다. 내부 문서 공개가 부담되면 대안 B로 분리하고 이 저장소를 private으로 전환하는 것을 검토.
- 주소에 `auto-trading-bot` 이 들어가 웹제작 포트폴리오로 어색하다. 고객 노출용으로는 대안 B가 낫다.
- 고객 시안·고객 제공 자료·고객 개인정보를 이 저장소(public)에 올리지 말 것. 시안 공유는 비공개 방식으로 별도 정할 것.
- API 키·토큰을 저장소에 커밋하지 말 것. 워크플로는 별도 시크릿을 쓰지 않는다(GitHub 기본 OIDC 권한만 사용).

## 대안
### B. 포트폴리오 전용 public 저장소 (권장, 고객 노출용)
1. 오른쪽 위 **+ > New repository**
2. 이름 예: `portfolio` 또는 `<사용자명>.github.io` (후자로 만들면 주소가 `https://<사용자명>.github.io/` 로 짧아짐)
3. **Public** 선택, README 체크 불필요 → **Create repository**
4. `portfolio/` 안의 4개 파일(index.html, cafe.html, academy.html, clinic.html)을 저장소 루트에 업로드 (**Add file > Upload files**, 드래그 후 **Commit changes**)
5. **Settings > Pages > Source = Deploy from a branch**, Branch `main` / 폴더 `/ (root)` → **Save**
6. 이 경우 워크플로 불필요. 파일 갱신은 같은 방식으로 업로드.

### C. Cloudflare Pages (GitHub 비공개 유지 시)
1. Cloudflare 가입(무료) → **Workers & Pages > Create > Pages > Upload assets**
2. 프로젝트 이름 입력 → `portfolio/` 폴더 업로드 → Deploy
3. 주소: `https://<프로젝트명>.pages.dev`. 계정 개설은 대표 전용 사항.

## 검증 기록 (2026-10-04, p1-cto)
- 로컬 `python3 -m http.server` 에서 `/`, `index.html`, `cafe.html`, `academy.html`, `clinic.html` 모두 200 (존재하지 않는 경로는 404 정상)
- 샘플 3종은 `samples/` 원본과 동일 내용(QA 2026-10-04: 상단 "가상 업체" 배너와 clinic 문구 수정을 두 폴더에 같이 반영), 외부 CDN·이미지 참조 없음. 앞으로 수정 시 두 폴더를 함께 고칠 것
- 워크플로: YAML 파싱, actionlint 통과
