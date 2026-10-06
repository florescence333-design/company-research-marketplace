# 사이트 배포 메모 — 운영·dev 인증 확인

사이트 코드는 `site/`에 있다. 비공개 사이트 저장소 `florescence333-design/company-research-site`의 `main` 운영 배포(`c80294f`)와 `dev` 미리보기 배포(`a551e94`)를 인증 설정 후 다시 배포해 검증했다. 운영 주소는 [company-research-site.pages.dev](https://company-research-site.pages.dev), 새 운영 고유 주소는 [77cb5c63.company-research-site.pages.dev](https://77cb5c63.company-research-site.pages.dev)다. 미리보기 별칭은 [dev.company-research-site.pages.dev](https://dev.company-research-site.pages.dev), 새 미리보기 고유 주소는 [76cb04d5.company-research-site.pages.dev](https://76cb04d5.company-research-site.pages.dev)다. 운영에서는 Claude AI 분석이 선택 가능하며 GPT는 코드 초안이다. 미리보기에서는 Claude·Codex AI 분석을 모두 볼 수 있다. 공개 플러그인 저장소 [`florescence333-design/company-research-marketplace`](https://github.com/florescence333-design/company-research-marketplace)에는 `runs/`, 실제 `data/`, `.env`·`.dev.vars`를 넣지 않는다. 운영 자료는 비공개 사이트 저장소 안에서만 관리한다.

## 로컬 화면

Windows PowerShell에서 저장소 루트 기준:

```powershell
npm.cmd ci --prefix site
npm.cmd run build --prefix site
npm.cmd run preview --prefix site -- --host 127.0.0.1 --port 4321
```

화면 주소는 `http://127.0.0.1:4321/company/RKLB/`이다. 일반 Astro 미리보기는 정적 화면 확인용이며 Cloudflare 비밀번호 미들웨어 검사는 아래 Pages 로컬 개발 서버에서 한다. SEC 수집 결과가 없으면 명시적으로 `샘플 데이터`라고 표시하고, 있으면 실제 수치·출처를 표시한다. 투자 판정은 언제나 `판정 보류 (v0.1)`이다.

실제 RKLB 실행은 사용자 범위 `SEC_USER_AGENT` 환경변수를 현재 PowerShell 프로세스에서만 읽어 SEC에 전달한다. 값을 화면·로그·파일에 출력하지 않는다.

```powershell
$env:SEC_USER_AGENT=[Environment]::GetEnvironmentVariable('SEC_USER_AGENT','User')
.venv\Scripts\python.exe scripts\company.py RKLB --engine gpt --new
```

이 명령은 SEC 수집 → 16섹션 부분 보고서 → 매출 Mermaid 도식 → 검증 → 로컬 사이트 빌드·테스트까지 진행한다. 기존 결과를 다시 검증·게시하려면 `.venv\Scripts\python.exe scripts\publish.py RKLB --engine gpt --run-id <실행 폴더 이름>`을 쓴다. 검증 또는 빌드가 실패하면 `site/data/companies/RKLB/gpt/current.json`이 이전 선택 결과를 가리키도록 복구한다. `validation.json`의 `passed`는 로컬 구조·원본 재계산·해시 검사 결과이며 원격 배포 성공 표시가 아니다.

## Pages 인증 및 빌드 정보

사이트 저장소에서는 프로젝트 루트를 사이트 코드로 지정하고 빌드 명령 `npm ci && npm run build`, 출력 폴더 `dist`를 사용한다. `functions/_middleware.js`가 로그인 페이지와 정확한 `/build-info.json` 경로 외의 정적 파일·분석 데이터를 보호한다. 운영·dev 미리보기·배포별 고유 주소에서 인증 없이 HTML과 분석 JSON이 노출되지 않는지 각각 확인한다.

Cloudflare Pages의 운영과 미리보기 환경에 다음 비밀 설정을 각각 입력한다. 값은 저장소·문서·명령행 인자에 기록하지 않는다.

Cloudflare 대시보드에서 프로젝트 **Settings → Variables and secrets**로 이동해 `Production`과 `Preview`에 각각 등록한다. `AUTH_PASSWORD`는 두 환경에 같은 비밀번호를 쓰고, `SESSION_SECRET`은 긴 무작위 값을 각 환경에 저장한다. 값을 저장한 뒤 다음 배포에서 적용되는지 확인한다. Pages Functions의 **Fail open/closed**는 `Fail closed`로 설정해 함수 사용량 한도에 도달했을 때 정적 분석 파일이 노출되지 않게 한다(2026-10-07 대시보드에서 설정 확인).

- `AUTH_PASSWORD`: 비밀번호 생성기로 만든 충분히 긴 무작위 문자열
- `SESSION_SECRET`: 독립적으로 생성한 긴 무작위 서명 비밀
- `SESSION_VERSION`: 비밀번호를 바꿀 때마다 새 값으로 변경해 기존 30일 쿠키를 무효화

`build-info.json`은 공개되며 `commit_sha`(사이트 저장소 커밋 해시)와 `built_at`(UTC 빌드 시각)만 담는다. Cloudflare 빌드에서는 `CF_PAGES_COMMIT_SHA`를 사용한다. 두 필드 외 값이 들어가거나 기대 커밋과 다르면 배포 성공으로 기록하지 않는다. 보호된 기업 페이지가 비밀번호 없이는 열리지 않고 정상 로그인 후에는 열리는지도 별도 확인한다.

운영 주소와 `dev` 미리보기의 별칭·배포별 고유 주소를 각각 확인한다. 사이트 저장소의 대상 커밋 전체 해시를 넣으며, 사이트 비밀번호는 이 명령에 전달하지 않는다.

```powershell
cd site
node scripts/check-deploy.mjs https://<확인할-주소> <사이트-저장소-커밋-전체-SHA>
```

이 검사는 공개 빌드 정보의 두 필드·캐시 설정·해시 일치와 비인증 목록·RKLB 상세·분석 JSON 차단, 로그인 페이지 응답을 확인한다. 성공해도 로그인 이후 화면 동작은 별도로 수동 확인한다. 배포가 이전 해시를 제공하면 아직 완료로 표시하지 않고 DESIGN.md의 15초 간격·10분 한도에 따라 재확인한다.

## 독립 비공개 사이트 저장소 준비

루트의 `scripts/export_site.py`는 Git이 추적하는 `site/` 코드와 로컬 게시 검증을 통과한 RKLB 선택 버전만 `deploy/site-repo/`에 복사한다. `.env`·`.dev.vars`·원본 SEC 캐시·다른 로컬 실행은 복사하지 않는다. `deploy/`는 루트 `.gitignore`에 포함되어 공개 플러그인 저장소에 들어가지 않는다. 이 PC의 `deploy/site-repo/`는 독립 Git 저장소로 초기화해 `main`·`dev` 로컬 브랜치를 준비했고, `npm ci`, `npm run build`, `npm test`가 통과했다. 공개 `build-info.json`은 독립 사이트 저장소 HEAD와 일치했다.

이 독립 저장소는 **비공개** GitHub 저장소에 연결되어 `main`·`dev`를 푸시했다. Cloudflare Pages의 운영 브랜치를 `main`, 개발 미리보기 브랜치를 `dev`로 두고 양쪽에 동일한 인증 비밀을 설정한다. `dev` 미리보기의 별칭·고유 주소와 운영 주소에서 보호 페이지·공개 빌드 정보 경로를 각각 검사한다. 원격에서 확인하기 전에는 배포 성공으로 기록하지 않는다.

현재 로컬 Pages Functions 검증은 다음 명령으로 실행했다. `.dev.vars`는 로컬 테스트용 무작위 값이며 `.gitignore`에 포함된다.

```powershell
cd site
npx.cmd wrangler pages dev dist --port 8788 --ip 127.0.0.1
```

다른 PowerShell 창의 저장소 루트에서 `node site/scripts/check-local-auth.mjs`를 실행하면 공개 빌드 정보·보호 경로·서명 쿠키·변조 쿠키를 검사한다. 2026-10-07 원격 검사에서 운영·미리보기 별칭과 새 고유 주소의 `/build-info.json`이 각각 커밋 `c80294fc62049240334a044ca2f0492afeabe67e`, `a551e9453f6da51333aec53e9f40c7ace5f6d285`를 공개했고, 비로그인 목록·RKLB·분석 데이터 경로는 `/login`으로 302 이동했다. 두 환경 모두 무작위 틀린 비밀번호는 401이며 쿠키를 발급하지 않았다. 사용자가 각 로그인 화면에서 정상 비밀번호를 직접 입력한 뒤 두 보호된 RKLB 화면과 16개 보고서 섹션이 표시되는 것을 확인했다. 실제 30일 만료와 원격 비밀번호 변경 후 세션 무효화는 별도 검증이 필요하다.
