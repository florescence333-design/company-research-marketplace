# Company Research Plugin — Windows 설치·실행 안내

> **빠른 안내**
> - 새 빈 폴더에서 끝까지 검증된 경로는 **Codex CLI (0.5.0, 약 18분)**이다. 아래 [Codex CLI로 실행하는 경우](#codex-cli로-실행하는-경우--새-빈-폴더-리허설-완료)부터 보세요.
> - 시연 티커는 **RKLB**다. 다른 기업은 아직 검증 전이다.
> - Claude Code 경로는 설치·환경 준비까지 확인했고, AI 작성 단계는 미검증이다.

공개 GitHub 마켓플레이스 플러그인 버전은 **0.5.0**이다.

미국 기업 티커 `RKLB`의 SEC 공시 수치를 수집하고 S0.5 기업별 커스텀 템플릿을 만든 뒤, 16개 대섹션과 필요한 하위 섹션을 분석하는 로컬 웹 화면을 만든다. 투자 판정은 현재 **`판정 보류 (v0.1)`**로 고정되어 있다. 검색을 시도하고도 근거를 찾지 못한 항목만 `자료 확인 대기`로 표시한다. 실제 결과와 합성 샘플을 혼동하지 않는다.

## 조교 PC에서 필요한 프로그램

| 프로그램 | 확인한 버전 | 설치·확인 방법 (PowerShell) | 예상 시간 |
| --- | --- | --- | --- |
| Git for Windows | 2.55.0 | `winget install --id Git.Git -e`; `git --version` | 약 3~10분 |
| uv | 0.11.26 | `winget install --id astral-sh.uv -e`; `uv --version` | 약 2~5분. Python 3.14는 플러그인이 첫 실행 때 준비 |
| Node.js / npm | 24.19.0 / 11.17.0 | `winget install --id OpenJS.NodeJS.LTS -e`; `node --version`, `npm.cmd --version` | 약 3~10분 |
| Claude Code | 2.1.199 | `npm.cmd install -g @anthropic-ai/claude-code`; `claude --version`; 첫 사용 시 `claude`에서 로그인 | 약 3~10분 + 로그인 |
| Codex CLI | 0.160.1 | Codex 앱과 별도로 `npm.cmd install -g @openai/codex@0.160.1`; PowerShell에서는 `codex.cmd --version` | 설치 시간 + 로그인 |

설치 뒤 PowerShell을 새로 열어 PATH를 갱신한다. Git Bash가 필요한 Claude Code 환경에서는 Git for Windows가 먼저 설치되어 있어야 한다. 설치 방식은 [uv 공식 문서](https://docs.astral.sh/uv/getting-started/installation/)와 [Claude Code 공식 문서](https://docs.anthropic.com/en/docs/claude-code/getting-started)를 참고한다. 이 저장소에서 테스트한 조합은 위 버전이며, 다른 버전은 아직 검증하지 않았다.

SEC는 연락 가능한 이름과 이메일을 넣은 User-Agent를 요구한다. 실행 전에 아래 예시의 `이름 이메일`을 본인의 연락처로 바꿔 Windows 사용자 환경변수 `SEC_USER_AGENT`를 등록하고 **PowerShell을 새로 연다**. 실제 값은 채팅·문서·터미널 출력에 적지 않는다.

```powershell
[Environment]::SetEnvironmentVariable("SEC_USER_AGENT", "이름 이메일", "User")
```

## Claude Code로 실행하는 경우 — 새 빈 폴더의 환경 준비 확인

개발 저장소를 복제하거나 `.venv`를 미리 만들 필요가 없다. PowerShell에서 새 빈 폴더를 만들고 그 안에서 Claude Code를 실행한다. 플러그인은 `user` 범위로 설치해 어느 작업 폴더에서도 활성화한다. 첫 실행의 Python·패키지·사이트 준비에는 약 3~10분, SEC 수집에는 약 2~5분이 걸릴 수 있다. AI 작성 시간은 아직 슬래시 명령 전체로 실측하지 않았다.

```powershell
New-Item -ItemType Directory -Path "$env:USERPROFILE\Documents\CompanyResearchTest"
Set-Location "$env:USERPROFILE\Documents\CompanyResearchTest"
claude
```

Claude Code 대화 입력창에서 다음을 실행한다. 로그인 요청이 나오면 `/login`을 먼저 완료한다.

```text
/plugin marketplace add florescence333-design/company-research-marketplace
/plugin install company-analysis@company-research-marketplace
/company RKLB
```

플러그인은 설치된 자신의 파일에서 공개 실행 코드만 현재 폴더의 `.company-research/`로 복사한다. `uv`가 Python 3.14와 `jsonschema`가 들어간 가상환경을 만들고 npm이 사이트 패키지를 설치한다. 실제 SEC 수집·실행 결과도 그 폴더에만 저장된다. 개발 폴더의 `.venv`나 `git clone`에 의존하지 않는다. 이미 플러그인을 설치한 PC에서 새 버전을 받으려면 Claude Code에서 `/plugin marketplace update company-research-marketplace` 후 `/plugin update company-analysis@company-research-marketplace`를 사용하고 Claude Code를 재시작한다.

Twelve Data 키는 현재 경로에 필요하지 않다. `--sample`은 합성 샘플만 만들며 실제 투자 분석이 아니다.

완료 후 별도 PowerShell 창에서 같은 빈 폴더로 이동해 화면을 연다. 서버는 `Ctrl+C`로 종료한다.

```powershell
Set-Location "$env:USERPROFILE\Documents\CompanyResearchTest"
npm.cmd run dev --prefix .company-research/site -- --host 127.0.0.1 --port 4321
```

화면 주소는 `http://127.0.0.1:4321/company/RKLB/`이다. `/company RKLB`는 SEC 수집 → 코드 초안 → S0.5 커스텀 템플릿 → Claude의 섹션 묶음별 근거 분석 → 보고서 기반 도식 → 검증 → 로컬 게시 순서다. 각 묶음을 저장하므로 사용량 한도 이후 같은 실행 폴더에서 이어갈 수 있다. 투자는 `판정 보류 (v0.1)`로 표시한다. **Claude 경로 기록(0.4.2 기준):** 2026-10-07에 개발 폴더 밖의 새 빈 폴더에서 공개 마켓플레이스 플러그인의 자체 Python 3.14/npm 준비·실제 RKLB SEC 수집·코드 초안·로컬 게시를 실행했고, 사이트 테스트 13개와 SEC 재계산·JSON 스키마 검사를 통과했다. 다만 **새 폴더에서 `/company RKLB` 한 줄의 Claude AI 작성 단계까지는 사용량 한도로 검증하지 못했다.** Git이 없는 새 작업 폴더의 공개 `build-info.json`에는 `commit_sha: null`을 기록하며, Cloudflare 배포에서는 실제 커밋 해시가 필수다.

## Claude Code에서 예상되는 권한 승인

권한 모드·버전에 따라 질문이 묶이거나 생략될 수 있다. 아래는 플러그인이 실제로 시도하도록 작성된 명령과 파일 작업이다. 표시된 경로가 방금 만든 폴더 또는 설치된 `company-analysis` 플러그인을 가리키는지 확인한다. `Bash(python *)` 같은 광범위한 영구 허용은 필요하지 않다.

| 승인 화면에 나올 작업 | 하는 일 |
| --- | --- |
| `/plugin marketplace add ...`, `/plugin install ...` (설치 시) | 공개 GitHub 마켓플레이스를 등록하고 `company-analysis` 플러그인을 `user` 범위로 설치한다. |
| 새 폴더 신뢰 및 설치된 스킬 읽기 | Claude Code가 현재 빈 폴더와 플러그인 지침을 사용한다. |
| `Bash(uv run --no-project --python 3.14 <플러그인>/scripts/bootstrap.py)` | 설치된 플러그인의 공개 파일을 `.company-research/`로 복사하고 Python·`jsonschema`·npm 패키지를 준비한다. 첫 실행에는 다운로드가 발생할 수 있다. |
| `Bash(.company-research/.venv/Scripts/python.exe scripts/company.py RKLB --engine claude)` | SEC 공시를 읽고 `data/`·`runs/`에 캐시·코드 초안을 만든 뒤 사이트를 로컬 빌드·검사한다. `--new` 등 선택 옵션이 뒤에 붙을 수 있다. |
| `WebSearch`·`WebFetch` 또는 설치 환경의 웹 검색·열람 도구 | 16개 섹션 각각에 대해 IR·실적 자료·경쟁사·규제·산업 자료를 검색하고 실제 근거를 확인한다. 검색 결과를 외부로 게시하는 명령은 아니다. |
| `Read/Edit(.company-research/runs/.../template-notes.json, report-items.json, sources.json)` | Claude가 먼저 기업별 S0.5 템플릿을 쓰고, 다음으로 각 섹션의 해석·검색어·출처 ID를 묶음별로 작성한다. SEC 수치·기존 SEC 출처·비밀 값은 수정 대상이 아니다. |
| `Bash(.../python.exe scripts/template_stage.py <실행 폴더> --render)` | 커스텀 템플릿의 16개 대섹션·하위 섹션 구조를 검증하고 `template.md`를 만든다. |
| `Bash(.../python.exe scripts/validate_bundle.py ...)`, `Bash(.../python.exe scripts/verify_sec_run.py ...)` | JSON 구조, 출처, SEC 원본과 계산값을 다시 검증한다. |
| `Bash(.../python.exe scripts/ai_report.py <실행 폴더> --model claude-code --sections ... --checkpoint)` | 섹션 묶음을 검증·저장하고 `analysis-progress.json`에 진도를 남긴다. 최종 실행은 `--checkpoint` 없이 전체를 검증한다. |
| `Bash(.../python.exe scripts/visualize_run.py <실행 폴더>)` | 보고서 근거 플라이휠·가치사슬 도식의 구조를 검증한다. |
| `Bash(.../python.exe scripts/publish.py RKLB --engine claude --run-id <실행 ID>)` | 검증된 결과를 로컬 사이트에 선택하고 빌드·테스트한다. GitHub 푸시나 Cloudflare 배포는 하지 않는다. |

`/company-publish RKLB`는 기존 실행을 다시 검증·로컬 게시하며 `--run-id`를 받을 수 있다. 권한 질문에서 위 범위를 벗어난 경로나 외부 전송 명령이 보이면 승인하지 말고 해당 명령을 확인한다. 자세한 배포 상태는 [배포 안내](docs/DEPLOYMENT.md)에 있다.

## Codex CLI로 실행하는 경우 — 새 빈 폴더 리허설 완료

Claude Code와 같은 공개 GitHub 마켓플레이스를 사용한다. Codex 앱을 설치했더라도 CLI는 별도로 설치해야 한다. PowerShell 실행 정책에서 `codex` 대신 `codex.cmd`를 사용한다. Git·uv·Node.js/npm과 사용자 범위 `SEC_USER_AGENT`는 Claude 경로와 공통이며, Codex 계정 로그인도 필요하다. 아래 절차는 Windows의 새 빈 폴더에서 **0.5.0 설치 후 `$company RKLB`부터 로컬 게시까지 실측**했다.

```powershell
npm.cmd install -g @openai/codex@0.160.1
codex.cmd plugin marketplace add florescence333-design/company-research-marketplace
codex.cmd plugin list --marketplace company-research-marketplace
codex.cmd plugin add company-analysis@company-research-marketplace
New-Item -ItemType Directory -Path "$env:USERPROFILE\Documents\CompanyResearchCodexTest"
Set-Location "$env:USERPROFILE\Documents\CompanyResearchCodexTest"
codex.cmd --no-daemon -a on-request -s workspace-write -c sandbox_workspace_write.network_access=true
```

설치 전 `plugin list`의 `VERSION` 칸이 비어 있어도 정상이다. 설치 후 플러그인 경로의 `company-analysis/0.5.0`과 Codex 앱 플러그인 화면의 **설치됨** 표시를 확인했다. 설치는 CLI에서 실측했고, **앱에서 `$company RKLB`를 실행하는 경로는 아직 시험 전**이다. Codex 앱이 켜진 상태에서 CLI를 일반 실행하면 `os error 5`가 발생해 위 명령에 `--no-daemon`을 넣었다. 기본 샌드박스에서는 인터넷·작업 폴더 밖 접근이 막혀 Python 준비가 실패했으며, 위 `workspace-write`·네트워크 설정으로 실행했다. [OpenAI 플러그인 안내](https://developers.openai.com/plugins/build/plugins)와 [Codex 설정 참고](https://learn.chatgpt.com/docs/config-file/config-reference)를 함께 볼 수 있다.

Codex 입력창은 **영문 입력 상태**로 두고 `$company RKLB`를 입력한다. 승인 질문은 **리허설 기준 4~5번 안팎**이었다. 횟수나 스크립트 목록은 고정되어 있지 않다. 요청된 명령이 **현재 작업 폴더 안의 `.company-research/` 플러그인 스크립트**를 실행하는지 확인한 뒤 해당되면 **2번(`p`)**을 선택한다. 다른 경로나 예상하지 못한 외부 전송 명령이면 먼저 내용을 확인한다. 리허설에서는 **13:16 실행 시작 → 13:20 SEC 수집의 첫 승인 질문 → 13:34 로컬 게시 완료**, 실행부터 게시까지 약 **18분**이 걸렸다.

결과는 현재 폴더의 `.company-research/runs/RKLB/gpt/<실행 ID>/`에 저장되고, 게시된 사이트 데이터는 `.company-research/site/data/companies/RKLB/gpt/`에 있다. 완료 후 **다른 PowerShell 창**에서 같은 작업 폴더로 이동해 로컬 사이트를 연다.

```powershell
Set-Location "$env:USERPROFILE\Documents\CompanyResearchCodexTest"
npm.cmd run dev --prefix .company-research/site -- --host 127.0.0.1 --port 4321
```

브라우저 주소는 `http://127.0.0.1:4321/company/RKLB/`이며 서버는 `Ctrl+C`로 종료한다. 로컬 게시만으로 GitHub나 Cloudflare에 자동 배포되지는 않는다.

## 현재 범위

| 완성된 것 | 미완성인 것 |
| --- | --- |
| 16개 Master Template 섹션 ID·제목, v1 초안 JSON Schema | 투자 프레임워크 v2 입력 |
| RKLB 4년 SEC 재무·최신 단독 분기 매출 비교·매출 CAGR·영업이익률·FCF·부채비율·EPS 근사·2025 10-K 사업/고객 집중도 일부 | 다른 기업·비12월 결산 검증, 공시 전체 대조·심층 재무 지표 |
| Codex RKLB 16개 대섹션+4-A/B, S0.5 커스텀 템플릿, 보고서 근거 플라이휠·가치사슬, 재무 카드 6개 | 조교 경로 보고서 깊이(개발 버전보다 얕음, 소제목 없음), Claude판의 새 지침 전체 실행, 산업·고객·경쟁력의 추가 검증, 실적 일정 |
| 실행 재사용, 로컬 자동 게시·빌드 실패 복구, 비공개 사이트의 운영·dev Pages 인증·접근 검사 | 판정 엔진, 30일 만료·비밀번호 변경의 원격 세션 검사, 원격 자동 게시·복구 검증 |

구체적인 제한과 재확인 항목은 [알려진 문제](docs/KNOWN_ISSUES.md)에 있다. 비밀 값과 실제 실행 데이터는 Git에서 제외된다.
