# 데이터 계약 — v1 초안

이 문서는 `docs/DESIGN.md`의 1단계 산출물이다. 2026-10-06에 **RKLB 실제 SEC Company Facts 결과가 이 계약의 구조 검증을 통과했다.** 단, 그 검증은 수치·기업분류·공시 본문까지 완전 검증했다는 뜻이 아니다. 3~5단계에서 필요한 필드를 계속 보완하므로 스키마는 여전히 **v1 초안**(`v1-draft`)이다. 필드 변경은 사례·이유와 함께 기록하고, 기존 산출물을 몰래 다른 의미로 해석하지 않는다.

사용자 제공 Master Template 원본은 `docs/020. 기업분석_Master Template.md`이다. `template/sections.json`의 `S01`~`S16` ID와 제목은 이 파일의 최상위 번호 제목을 그대로 뽑았다. 원본 파일의 SHA-256을 함께 기록한다. 투자 프레임워크 v2는 **입력 대기**이다.

이번 일정의 판정 계산은 의도적으로 보류한다. `decision_policy_version`은 `v0.1`, 화면·파일에 표시하는 최종 상태는 **`판정 보류 (v0.1)`**이다. 축 A·축 B는 null이며 임의의 매수·회피 결과를 만들지 않는다. DESIGN.md의 판정 기준 v1은 향후 구현 명세로 남는다. 평가·역DCF·강제 회피의 세부 규칙은 사용자 결정 전까지 코드로 실행하지 않는다.

## 1단계에서 실행되는 파일

| 파일 | 작성 주체 | 핵심 필드·형식 | 참조·검증 |
| --- | --- | --- | --- |
| `template/sections.json` | `scripts/build_sections.py` | `schema_version`, `source_path`, `source_sha256`, `sections[]`의 `section_id/title/required` | 원본 템플릿의 1~16번 제목과 일치. 변경 시 다시 생성 |
| `meta.json` | 실행 스크립트 | `schema_version`, `run_id`, `data_snapshot_id`, 시간대 있는 `analysis_as_of/generated_at`, `ticker/CIK`, `engine`, `sample`, 코드·템플릿·기술 기본값·판정 버전 | 한 결과 묶음의 기준 ID. `sample=true`는 합성 시연을 뜻함 |
| `metrics.json` | 계산·수집 스크립트 | `run_id`, `data_snapshot_id`, `metrics[]`의 `metric_id/value/status/unit/approximate/reason/period_start/period_end/source_ids` | ID와 스냅샷은 meta와 일치. 출처 ID는 sources에 존재해야 함 |
| `sources.json` | 수집 스크립트 | `sources[]`의 `source_id/url/title/accessed_at/location`, 선택적으로 공시 번호·해시·인용문 | URL 확인만으로 내용 진실성을 보증하지 않음 |
| `decision.json` | 임시 판정 스크립트 | `schema_version=v1-draft`, `decision_policy_version=v0.1`, `verdict=판정 보류 (v0.1)`, `reason`, null 축, `pending_rules` | 실제 판정 불가. 같은 실행·스냅샷을 참조 |
| `run.json` | 실행 스크립트 | 실행 ID·티커·엔진·기준시점·스냅샷·옵션·단계별 `step_id/state`와 선택적 입출력 SHA-256 | 단계 상태는 `pending/running/completed/failed/blocked` |
| `extracted-facts.json` | 10-K 본문 추출 | `fact_id/value/unit/source_id/location/verification`, 실행·스냅샷 ID | 공식 10-K 원본 해시와 문구 재추출, 출처 ID 참조를 확인. 현재 RKLB 일부 사업 사실에 한정 |

공통 상태는 `ok`, `not_applicable`, `unavailable`, `collection_failed`다. `ok` 수치는 number이고, 나머지 상태는 `value=null`과 비어 있지 않은 `reason`을 요구한다. `approximate`는 항상 별도 boolean이다. 0은 실제 측정값일 수 있으므로 누락값의 대용으로 쓰지 않는다. 계산 중에는 Python `Decimal`을 사용하고 JSON의 수치 직렬화·표시 반올림은 계산과 구분한다. 모든 시각은 시간대 정보를 포함하며 재무 기간은 별도 날짜 필드로 둔다.

## 후속 단계에서 채울 계약 자리

| 파일 | 작성 주체 | 예정 필드·참조 | 상태 |
| --- | --- | --- | --- |
| `valuation.json` | 계산 코드 | 역DCF 입력·가정·9/10/11% 민감도·계산 가능 여부 | 판정 세부 규칙 결정 뒤 |
| `assessments.json` | AI | 기업 유형, 다섯 항목 평가, 근거·반증 조건·성장률 범위 | 판정 세부 규칙 결정 뒤 |
| `dashboard.json` | 조립 코드 | meta·metrics·decision 참조와 표시 상태 | 3단계 |
| `financials-analysis.json` | AI | 지표별 해석·한계·출처 | 4~5단계 |
| `template-items.json`·`template-notes.json` | 템플릿 코드 | 섹션/항목 ID, 원본 대비 변경 이유 | 5단계 |
| `report-items.json`·`report.md` | 조립 코드·후속 AI | Master Template의 16개 섹션 ID·제목·순서, 부분 작성/자료 확인 대기, 내용·출처·지표 참조 | 5단계 단순 연결 완료. AI 근거 검토는 후속 |
| `diagrams/` | 시각화 코드 | 기준 보고서 실행 ID·해시 | 6단계 |
| `validation.json` | 검증 코드 | 실행·스냅샷 ID, 검사 시각·통과 상태·검사 목록·보고서 해시 | 7단계 로컬 검증 완료. 원격 배포 상태는 별도 |

위 예정 필드를 지금 존재하는 스키마나 구현으로 주장하지 않는다. 실제 데이터를 다루며 필요한 필드부터 확장하고 `v1-draft` 변경 이력을 이 문서에 추가한다. 세부 판정 기준이 없다는 상태와 실제 입력 데이터가 없다는 상태는 구별한다.

5단계에서는 `meta.company_name`을 선택 필드로 추가하고 `report-items.schema.json`을 만들었다. `report-items.json`은 모든 섹션을 Master Template 순서대로 담고, 작성 상태와 사용한 지표·출처 ID를 적는다. 현재 내용은 SEC 숫자만으로 만들 수 있는 부분 보고서이며, 자료가 없는 섹션은 **자료 확인 대기**라고 명시한다. 수치 성장률은 코드에서 계산한다. 사업 경쟁력·밸류에이션·최종 매수/회피 판정은 작성하지 않는다.

후속 보강으로 RKLB 2025년 10-K 본문에서 직접 일치한 사업 사실을 `extracted-facts.json`에 담고, `report-items.json`의 선택적 `fact_ids`로 사용 섹션에 연결했다. 본문이 없거나 문구가 맞지 않으면 추정해서 채우지 않는다. 사업부 매출 합계는 Company Facts 총매출과 대조하고, 10-K 원본 SHA-256·accession·문서 내 위치를 출처에 남긴다. 10-K 파일 해시는 `meta.filing_sha256`에 기록한다. 이 역시 **v1 초안**이며 다른 기업과 다른 공시 형식에 일반화되었다는 뜻은 아니다.

## 로컬 실행

```powershell
.venv\Scripts\python.exe scripts\build_sections.py
.venv\Scripts\python.exe scripts\validate_bundle.py examples\sample-rklb
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

샘플은 합성 자료이며 실제 RKLB 공시 분석이 아니다. 이 검증은 구조·일부 참조 일치만 확인한다. 수치 정확성·출처 내용·보호된 게시 가능 여부는 후속 단계에서 검증한다.

## 4단계 실제 RKLB 검증

`scripts/sec.py`는 SEC Company Facts에서 공시일이 분석 기준일을 넘지 않는 10-K·10-Q만 선택한다. 연간 흐름 값은 330~380일 기간을 요구하고 공시별 출처 ID·태그·기간·원본 SHA-256을 기록한다. 2023~2025년 매출·영업손익·순손익·영업현금흐름, 최신 현금·자산·부채·자본을 수집했다. EPS(TTM)는 최근 연속 4개 독립 분기 희석 EPS가 있으면 합산하고, 없으면 연간 순이익 + 최신 누적 순이익 − 전년 동기 누적 순이익을 최신 분기 희석 가중평균 주식 수로 나누어 **근사**로 표시한다. 135일이 넘은 주식 수나 누락 분모는 사용하지 않는다. 공식 [2025년 10-K](https://www.sec.gov/Archives/edgar/data/1819994/000181999426000013/rklb-20251231.htm)의 정해진 문구에서 사업부 매출·수주잔고·누적 발사/배치·직원·Neutron 계획 탑재량을 부분 추출한다.

```powershell
$env:SEC_USER_AGENT=[Environment]::GetEnvironmentVariable('SEC_USER_AGENT','User')
.venv\Scripts\python.exe scripts\company.py RKLB --engine gpt --site-data
$run=Get-ChildItem runs\RKLB\gpt | Sort-Object LastWriteTime -Descending | Select-Object -First 1
.venv\Scripts\python.exe scripts\verify_sec_run.py $run.FullName
npm.cmd run build --prefix site
```

`data/`, `runs/`, `site/data/`는 Git에서 제외한다. SEC_USER_AGENT 값은 코드·출력·문서에 쓰지 않는다. `verify_sec_run.py`는 보관한 Company Facts와 10-K 원본 해시에서 재무 지표·사업 사실·출처를 다시 계산해 대조한다. 전체 10-K/10-Q 감사 의견과 주석 검토, 다른 결산월 기업 검증, AI의 재무 해석은 다음 작업이다.

## 6단계 실행 상태와 도식

실제 실행은 `run.json`에 S0~S7의 상태와 검증 가능한 산출물 해시를 기록한다. `--new`는 새 실행, `--run-id`는 같은 티커·엔진 실행의 해시 확인 후 재사용이다. 기본 실행은 같은 옵션의 24시간 이내 미완료 실행이 하나일 때 그 실행을 재사용하고, 여러 개면 명시 ID를 요구한다. 현재 단순 파이프라인은 중간 단계 부분 재실행 대신 변조를 감지해 새 실행을 요구한다. S3는 RKLB 2025 10-K의 일부 사실이 검증되면 완료로 표시하고 범위를 사유에 기록한다. 공시 전체 추출 및 S7 원격 게시 검증은 미완료다.

`scripts/visualize_run.py`는 검증된 연간 매출 2개 이상에서 Mermaid 매출 연혁 도식을 만든다. `diagrams/manifest.json`은 기준 보고서 run_id·스냅샷·보고서 해시·도식 해시를 기록한다. `--no-viz`는 도식 없이 결과를 만들고, `--viz-only --run-id <id>`는 기존 보고서 해시가 바뀌지 않았을 때 도식만 다시 만든다. 브라우저는 Mermaid를 렌더링한다. 사업 플라이휠·밸류체인 도식은 아직 자료 확인 대기다. `--original`은 원본 템플릿 사용을 실행 옵션에 기록하며 현재 커스텀 템플릿 생성 전이라 기본 실행과 동일한 16개 원본 섹션을 사용한다.

## 7단계 로컬 게시 계약

`scripts/publish.py`는 합성 샘플·오래된 분석·변조된 산출물·원본 SEC 재계산 불일치를 거부한다. 통과한 묶음에 `validation.json`을 쓰고 `site/data/companies/RKLB/<engine>/versions/`의 내용 주소가 붙은 폴더에 복사한다. `current.json` 포인터만 바꿔 사이트를 빌드·테스트하며, 실패하면 이전 포인터를 복구한다. 같은 회사의 Claude판·GPT판은 각각 별도 포인터다. 실제 데이터 디렉터리는 루트 Git에서 제외한다. Cloudflare 배포 커밋·인증 확인은 아직 완료되지 않았다.
