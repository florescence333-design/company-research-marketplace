# 2026-10-07 아침 작업 보고

> 이 문서는 밤사이 확인한 결과를 누적한다. 최종 체크리스트 상태는 08:40 전 아래에 반영한다.

## 밤사이 한 일

- `docs/reference/`의 프로젝트 지침을 적용해 S0.5 커스텀 프레임워크와 GPT판 RKLB 16개 대섹션·S04-A/B를 완성했다. 본문과 출처, 묶음별 진행 기록, SEC 재계산을 검증했다. 기준 보고서 내용은 복사하지 않았고 공개 플러그인 저장소에도 넣지 않았다.
- 템플릿 탭은 `template.md` 전문을 보여 주고, 보고서 탭 목차는 18개 항목의 작성 상태를 표시한다. 시각화 탭은 6요소 플라이휠과 공급자→직접 제작/외부 의존→고객군 가치사슬을 보고서 근거 섹션과 함께 표시한다. 옛 매출 상자 도식은 제거했다.
- 상단 대시보드에 TradingView 위젯, SEC 지표 기반 재무 카드 6개, 경고 신호를 추가했다. 적자 기업의 OCF 성장률·순이익의 질·PER는 오해를 부르는 양수 비율 대신 상태 문구로 보여 준다. 스크립트 CSP는 TradingView 위젯 스크립트 한 도메인만 예외로 허용한다.
- 공개 플러그인 저장소 `main`은 `615a679`(0.4.0)까지 푸시했다. 비공개 사이트 저장소의 `dev`와 `main`은 검증된 `5ba9485`로 배포했다. [dev 미리보기](https://dev.company-research-site.pages.dev/company/RKLB/)와 [운영 사이트](https://company-research-site.pages.dev/company/RKLB/)에서 확인할 수 있다.

## 실행·배포 확인

| 확인 항목 | 결과 |
| --- | --- |
| Python 자동 테스트 | 46개 통과 |
| 사이트 자동 테스트 | 대시보드 배포 전 12개 통과; 두 엔진 비교표 추가 후 13개 통과(비교표는 아직 배포 전) |
| 로컬 빌드·인증 | Astro 빌드, Pages Functions 공개/보호 경로·서명 쿠키·변조 쿠키 검사 통과 |
| dev 원격 배포 | `5ba9485` 빌드 해시 일치. 비로그인 분석 JSON 차단, 틀린 비밀번호 401·세션 미발급, 로그인된 차트·6개 카드·템플릿·도식 표시, 브라우저 콘솔 오류 없음 |
| 운영 원격 배포 | 같은 커밋 해시 일치. 비로그인 분석 파일 차단, 틀린 비밀번호 401·세션 미발급, 로그인된 GPT 18항목·차트·카드 표시 |
| 모바일 폭 | 390px iframe 안 실제 내용 폭 375px, 문서 가로 넘침 없음, 재무 카드 1열, 차트 iframe 표시 확인 |
| 올바른 비밀번호 | 사용자가 앞서 운영·Preview 양쪽에서 직접 입력해 RKLB 화면 통과 확인. 비밀번호는 기록하지 않음 |
| 공개 빌드 정보 | `build-info.json`에서 커밋 해시·빌드 시각만 공개하고 사이트 자격 증명 없이 확인 |

## GPT판 품질 비교

| 비교 | 이전 GPT판 | 새 GPT판 | 목표 자료 |
| --- | ---: | ---: | ---: |
| 작성 항목 | 16개, 자료 대기 4개 | 18개, 자료 대기 0개 | 16개 대섹션에 기업 맞춤 하위 섹션 |
| 본문 글자 수 | 5,995자 | 26,431자 | 기준 보고서 69,939자 |
| 웹 출처가 있는 항목 | 0개 | 18개 | 전 섹션 근거 기반 |
| `[해석]`·반대 논거 | 0개 | 18개 | 판단마다 구분 |
| 표가 있는 항목 | 0개 | 11개 | 필요한 곳에 구체적 표 |
| 커스텀 템플릿 | 없음 | 7,050자 | 기준 템플릿 13,206자 |

새 판은 SEC 수치의 기간을 구분하고, Electron·Space Systems·아직 상용화 전인 Neutron·종결 전 Iridium을 분리했다. S03은 SpaceX 합승과 Electron 전용 발사의 고객 선택, 미 우주군 조달의 단계, 경쟁사의 실제 운용 상태를 비교한다. S04-A는 Neutron의 시험·첫 비행·재비행·계약 조건을 분리한다. S12는 내부 변수 목록 대신 연도별 한국어 재무 표와 해석을 쓴다. 여전히 목표 보고서의 약 38% 분량으로, 제품별 원가·계약별 마진·고객 경제성과 경쟁 제품의 정량 비교가 부족하다. 이 한계를 빈 숫자로 메우지 않았다.

## 시장 스냅샷과 남은 문제

- Twelve Data 키는 파일·출력에 노출하지 않았다. 로컬 API 시험에서 RKLB 주가와 52주 범위를 받았다. 시가총액 필드는 현재 요금제에서 제공되지 않았고 적자 PER는 배수가 아니라 상태로 표시한다. [Twelve Data 요금표](https://twelvedata.com/pricing)와 [사용 범위 설명](https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage)에 따르면 개인 요금제의 표시·재배포 권한이 제한될 수 있으므로, 해당 권한이 확인되기 전에는 시장 스냅샷 숫자를 원격 사이트 저장소로 내보내지 않는다. 사이트 차트는 TradingView 위젯으로 별도 표시된다.
- 판정 엔진은 요청대로 구현하지 않았다. 가격 판정과 강제 회피 여부를 추정하지 않고 `판정 보류 (v0.1)`로 유지한다. 투자 프레임워크 v2는 여전히 입력 대기다.
- 다른 기업·비12월 결산, 공시 주석 전체 대조, 세션의 실제 30일 만료·비밀번호 변경 시 원격 무효화, 원격 자동 게시·충돌 복구는 아직 검증되지 않았다.
- 새 Claude판의 S0.5와 섹션 묶음 실행은 진행 중이다. 완료된 묶음만 검사하고 한도에 걸리면 `analysis-progress.json`을 기준으로 멈춘다. 검증 실패 결과는 dev에 게시하지 않는다.

## 아침에 사용자가 할 일

1. 새 빈 폴더에서 조교 설치·시작 리허설을 진행하고 `/company RKLB`가 S0.5까지 시작하는지 확인한다. 비밀번호와 API 키는 채팅에 적지 않는다.
2. Twelve Data 계정의 사이트 표시·재배포 허용 범위를 확인한다. 확인 전 원격 시장 숫자는 `확인 불가`로 유지된다.
3. dev의 새 GPT 보고서·도식·대시보드를 살펴보고 사실 관계나 원하는 분석 깊이의 우선순위를 알려 준다.

## 조교 PC 준비와 Claude판 실행

Node.js는 **필요**하다. Claude Code 설치와 Astro 사이트 빌드·로컬 실행에 사용한다. Git for Windows와 `uv`, Claude Code도 필요하다. Python 3.14와 `jsonschema`는 플러그인이 첫 실행에 `uv`로 준비하므로 Python을 별도로 설치할 필요는 없다. 사용자 범위 `SEC_USER_AGENT`에는 연락 가능한 이름·이메일을 설정해야 한다. README에 명령별 예상 권한 질문과 설치 시간을 적었다.

1. PowerShell: `New-Item -ItemType Directory "$env:USERPROFILE\Documents\CompanyResearchTest"; Set-Location "$env:USERPROFILE\Documents\CompanyResearchTest"`
2. `claude`를 실행하고 필요하면 `/login`한다.
3. Claude 대화창: `/plugin marketplace add florescence333-design/company-research-marketplace` → `/plugin install company-analysis@company-research-marketplace` (기설치면 marketplace/plugin update).
4. Claude 대화창: `/company RKLB`를 실행한다. 완료 전에는 묶음별 저장 상태를 확인한다.
5. 별도 PowerShell: `npm.cmd run dev --prefix .company-research/site -- --host 127.0.0.1 --port 4321`; 결과는 `.company-research/runs/RKLB/claude/<실행 ID>/`와 `http://127.0.0.1:4321/company/RKLB/`에 있다.

## 12시까지의 순서

1. Claude판 S0.5를 검증하고 섹션 묶음을 순서대로 작성·저장한다. 사용량 한도에 도달하면 진도를 기록하고 중단한다.
2. Claude판 전체·도식·출처를 검증하고 GPT판과 섹션별로 비교한다. 통과한 경우에만 dev 사이트에 게시한다.
3. 조교 PC 리허설에서 나온 설치·권한 질문을 README와 알려진 문제에 반영한다.
4. 12시부터는 새 기능을 멈추고 공개 마켓플레이스 설치성, RKLB 운영/미리보기 배포, 안내·완성/미완성 목록, 최종 체크리스트를 다시 확인한다.

## 체크리스트 최종 상태

아래 표는 작업이 끝날 때 `docs/overnight-todo.md`에서 갱신한다.
