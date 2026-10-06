# Company Research Plugin — Windows 설치·실행 안내

미국 기업 티커 `RKLB`의 SEC 공시 수치를 수집해 16개 섹션의 **부분 보고서**와 로컬 웹 화면을 만든다. 투자 판정은 현재 **`판정 보류 (v0.1)`**로 고정되어 있다. 근거가 부족한 항목은 `자료 확인 대기`로 표시한다. 실제 결과와 합성 샘플을 혼동하지 않는다.

## 조교 PC에서 필요한 프로그램

| 프로그램 | 확인한 버전 | 설치·확인 방법 (PowerShell) | 예상 시간 |
| --- | --- | --- | --- |
| Git for Windows | 2.55.0 | `winget install --id Git.Git -e`; `git --version` | 약 3~10분 |
| uv와 Python | uv 관리 Python 3.14.6 | `winget install --id astral-sh.uv -e`; `uv venv --python 3.14 .venv` | 약 2~8분 |
| Node.js / npm | 24.19.0 / 11.17.0 | `winget install --id OpenJS.NodeJS.LTS -e`; `node --version`, `npm.cmd --version` | 약 3~10분 |
| Claude Code | 2.1.199 | `npm.cmd install -g @anthropic-ai/claude-code`; `claude --version`; 첫 사용 시 `claude`에서 로그인 | 약 3~10분 + 로그인 |

설치 뒤 PowerShell을 새로 열어 PATH를 갱신한다. Git Bash가 필요한 Claude Code 환경에서는 Git for Windows가 먼저 설치되어 있어야 한다. 설치 방식은 [uv 공식 문서](https://docs.astral.sh/uv/getting-started/installation/)와 [Claude Code 공식 문서](https://docs.anthropic.com/en/docs/claude-code/getting-started)를 참고한다. 이 저장소에서 테스트한 조합은 위 버전이며, 다른 버전은 아직 검증하지 않았다.

## 의존성 설치와 키 없는 확인 — 약 3~6분

공개 저장소에서 시작한다. 이미 이 프로젝트 폴더가 있으면 첫 두 명령을 건너뛰고 그 루트로 이동한다.

```powershell
git clone https://github.com/florescence333-design/company-research-marketplace.git
cd company-research-marketplace
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
npm.cmd ci --prefix site
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe scripts\company.py RKLB --engine gpt --sample
```

마지막 명령은 **합성 샘플**을 `runs/RKLB/gpt/`에 만들고 경로를 출력한다. SEC 자료나 API 키가 필요 없다. `sample=true`이며 실제 투자 분석이 아니다.

## 실제 RKLB 실행과 로컬 화면 — 첫 실행 약 2~5분

SEC는 연락 가능한 이름과 이메일을 넣은 User-Agent를 요구한다. Windows의 사용자 환경변수 `SEC_USER_AGENT`를 시스템 설정에서 미리 등록한다. 값을 채팅·저장소·문서·터미널 출력에 적지 않는다. 아래 명령은 그 값을 현재 프로세스로 읽을 뿐 출력하지 않는다. Twelve Data 키는 이 경로에 필요하지 않다.

```powershell
$env:SEC_USER_AGENT = [Environment]::GetEnvironmentVariable('SEC_USER_AGENT', 'User')
if ([string]::IsNullOrWhiteSpace($env:SEC_USER_AGENT)) { throw 'SEC_USER_AGENT 사용자 환경변수를 먼저 설정하세요.' }
.venv\Scripts\python.exe scripts\company.py RKLB --engine gpt --new
npm.cmd run dev --prefix site -- --host 127.0.0.1 --port 4321
```

명령이 성공하면 `http://127.0.0.1:4321/company/RKLB/`에서 결과를 본다. 보고서 탭은 16개 섹션을 제목·상태·출처별로 표시하고 원문도 접어 볼 수 있다. 마지막 개발 서버 명령은 실행 상태로 남으므로 확인 후 `Ctrl+C`로 종료한다. 실제 실행은 SEC 수집 → 원본 재계산 → 16섹션 부분 보고서 → Mermaid 매출 도식 → 로컬 사이트 빌드·테스트까지 자동으로 연결한다. `--new`를 빼면 24시간 이내 같은 조건의 미완료 실행 1개를 재사용한다. 자세한 검증·재게시 방법은 [배포 안내](docs/DEPLOYMENT.md)에 있다.

## Claude Code 플러그인 설치

프로젝트 루트에서 Claude Code를 실행한다. 로그인되지 않았다면 `/login`을 먼저 완료한다. 공개 저장소의 마켓플레이스 등록·플러그인 설치·활성화와 `claude plugin validate --strict .`는 이 PC에서 확인했다. **Claude AI의 실제 16섹션 분석 실행은 로그인 뒤 확인할 예정**이다.

```powershell
claude
```

Claude Code 대화 입력창에서 아래 명령을 순서대로 실행한다. 예상 소요 시간은 설치 1~3분, 첫 실제 RKLB 분석은 SEC 수집·AI 작성량에 따라 약 5~20분이며 아직 실측되지 않았다.

```text
/plugin marketplace add florescence333-design/company-research-marketplace
/plugin install company-analysis@company-research-marketplace
/company RKLB
```

`/company RKLB`는 공시 수집 후 Claude가 16섹션을 직접 보강하고, 출처·판정 보류·보고서 본문을 검증한 뒤 로컬 화면에 게시하도록 설계했다. 실패 시 결과 경로와 검증 오류를 확인한다. 공통 스크립트는 Codex에서 `--engine gpt`, Claude Code에서 `--engine claude`를 사용한다. 설치와 로그인 뒤에는 `/company-publish RKLB`로 기존 실행의 로컬 재검증·게시도 할 수 있다. 로컬 빌드 성공을 Cloudflare 배포 성공으로 해석하지 않는다.

## 현재 범위

| 완성된 것 | 미완성인 것 |
| --- | --- |
| 16개 Master Template 섹션 ID·제목, v1 초안 JSON Schema | 투자 프레임워크 v2 입력 |
| RKLB 4년 SEC 재무·최신 단독 분기 매출 비교·매출 CAGR·영업이익률·FCF·부채비율·EPS 근사·2025 10-K 사업/고객 집중도 일부 | 다른 기업·비12월 결산 검증, 공시 전체 대조·심층 재무 지표 |
| 16섹션 부분 보고서, 매출 Mermaid 도식, 로컬 사이트와 Pages 인증 검사 | 산업·고객·경쟁력 등 전체 AI 분석, 주가/배당/실적 일정 |
| 실행 재사용, 로컬 자동 게시·빌드 실패 복구 | 판정 엔진, 원격 GitHub/Cloudflare 게시·인증 검증 |

구체적인 제한과 재확인 항목은 [알려진 문제](docs/KNOWN_ISSUES.md)에 있다. 비밀 값과 실제 실행 데이터는 Git에서 제외된다.
