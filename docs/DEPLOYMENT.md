# 사이트 배포 메모 — 현재 로컬 검증 상태

사이트 코드는 `site/`에 있다. 현재 배포된 결과가 아니다. GitHub의 공개 플러그인 저장소와 비공개 사이트 저장소, Cloudflare 계정·Pages 프로젝트는 사용자 계정 로그인 후 구성해야 한다. 공개 플러그인 저장소에는 `runs/`, 실제 `data/`, `.env`·`.dev.vars`를 넣지 않는다. 사이트 저장소는 비공개로 만들고 운영 자료는 그 저장소 안에서만 관리한다.

## 로컬 화면

Windows PowerShell에서 저장소 루트 기준:

```powershell
npm.cmd ci --prefix site
npm.cmd run build --prefix site
npm.cmd run preview --prefix site -- --host 127.0.0.1 --port 4321
```

화면 주소는 `http://127.0.0.1:4321/company/RKLB/`이다. 일반 Astro 미리보기는 정적 화면 확인용이며 Cloudflare 비밀번호 미들웨어 검사는 아래 Pages 로컬 개발 서버에서 한다. 기본 데이터는 명시적으로 `샘플 데이터`라고 표시되고 투자 판정은 `판정 보류 (v0.1)`이다.

## Pages 인증 및 빌드 정보

사이트 저장소에서는 프로젝트 루트를 사이트 코드로 지정하고 빌드 명령 `npm ci && npm run build`, 출력 폴더 `dist`를 사용한다. `functions/_middleware.js`가 로그인 페이지와 정확한 `/build-info.json` 경로 외의 정적 파일·분석 데이터를 보호한다. 운영·dev 미리보기·배포별 고유 주소에서 인증 없이 HTML과 분석 JSON이 노출되지 않는지 각각 확인한다.

Cloudflare Pages의 운영과 미리보기 환경에 다음 비밀 설정을 각각 입력한다. 값은 저장소·문서·명령행 인자에 기록하지 않는다.

- `AUTH_PASSWORD`: 비밀번호 생성기로 만든 충분히 긴 무작위 문자열
- `SESSION_SECRET`: 독립적으로 생성한 긴 무작위 서명 비밀
- `SESSION_VERSION`: 비밀번호를 바꿀 때마다 새 값으로 변경해 기존 30일 쿠키를 무효화

`build-info.json`은 공개되며 `commit_sha`(사이트 저장소 커밋 해시)와 `built_at`(UTC 빌드 시각)만 담는다. Cloudflare 빌드에서는 `CF_PAGES_COMMIT_SHA`를 사용한다. 두 필드 외 값이 들어가거나 기대 커밋과 다르면 배포 성공으로 기록하지 않는다. 보호된 기업 페이지가 비밀번호 없이는 열리지 않고 정상 로그인 후에는 열리는지도 별도 확인한다.

현재 로컬 Pages Functions 검증은 다음 명령으로 실행했다. `.dev.vars`는 로컬 테스트용 무작위 값이며 `.gitignore`에 포함된다.

```powershell
cd site
npx.cmd wrangler pages dev dist --port 8788 --ip 127.0.0.1
```

다른 PowerShell 창의 저장소 루트에서 `node site/scripts/check-local-auth.mjs`를 실행하면 공개 빌드 정보·보호 경로·서명 쿠키·변조 쿠키를 검사한다. 실제 Cloudflare Pages 배포 확인은 계정·프로젝트 준비 후 수행한다.
