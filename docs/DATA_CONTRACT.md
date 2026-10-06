# 데이터 계약 — v1 초안

이 문서는 `docs/DESIGN.md`의 1단계 산출물이다. **구축 순서 4단계에서 RKLB 실제 공시 데이터가 계약 검증을 통과하기 전까지 스키마를 수정할 수 있다.** 필드 변경은 사례·이유와 함께 기록하고, 기존 산출물을 몰래 다른 의미로 해석하지 않는다. 현재 스키마 디렉터리의 `v1`은 초안 계열을 가리키며 파일의 `schema_version`은 `v1-draft`이다.

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
| `run.json` | 실행 스크립트 | 실행 ID·티커·엔진·기준시점·스냅샷·단계별 `step_id/state`와 선택적 입출력 SHA-256 | 단계 상태는 `pending/running/completed/failed/blocked` |

공통 상태는 `ok`, `not_applicable`, `unavailable`, `collection_failed`다. `ok` 수치는 number이고, 나머지 상태는 `value=null`과 비어 있지 않은 `reason`을 요구한다. `approximate`는 항상 별도 boolean이다. 0은 실제 측정값일 수 있으므로 누락값의 대용으로 쓰지 않는다. 계산 중에는 Python `Decimal`을 사용하고 JSON의 수치 직렬화·표시 반올림은 계산과 구분한다. 모든 시각은 시간대 정보를 포함하며 재무 기간은 별도 날짜 필드로 둔다.

## 후속 단계에서 채울 계약 자리

| 파일 | 작성 주체 | 예정 필드·참조 | 상태 |
| --- | --- | --- | --- |
| `extracted-facts.json` | 공시 본문 추출·검증 | 원문 위치, 단위, 기간, 출처 ID, 검증 상태 | 4단계 |
| `valuation.json` | 계산 코드 | 역DCF 입력·가정·9/10/11% 민감도·계산 가능 여부 | 판정 세부 규칙 결정 뒤 |
| `assessments.json` | AI | 기업 유형, 다섯 항목 평가, 근거·반증 조건·성장률 범위 | 판정 세부 규칙 결정 뒤 |
| `dashboard.json` | 조립 코드 | meta·metrics·decision 참조와 표시 상태 | 3단계 |
| `financials-analysis.json` | AI | 지표별 해석·한계·출처 | 4~5단계 |
| `template-items.json`·`template-notes.json` | 템플릿 코드 | 섹션/항목 ID, 원본 대비 변경 이유 | 5단계 |
| `report-items.json`·`report.md` | AI·조립 코드 | 고정 섹션 ID, 항목별 내용·출처·지표 참조 | 5단계 |
| `diagrams/` | 시각화 코드 | 기준 보고서 실행 ID·해시 | 6단계 |
| `validation.json` | 검증 코드 | 검사 결과, 산출물 해시, 게시 가능 여부 | 7단계 |

위 예정 필드를 지금 존재하는 스키마나 구현으로 주장하지 않는다. 실제 데이터를 다루며 필요한 필드부터 확장하고 `v1-draft` 변경 이력을 이 문서에 추가한다. 세부 판정 기준이 없다는 상태와 실제 입력 데이터가 없다는 상태는 구별한다.

## 로컬 실행

```powershell
.venv\Scripts\python.exe scripts\build_sections.py
.venv\Scripts\python.exe scripts\validate_bundle.py examples\sample-rklb
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

샘플은 합성 자료이며 실제 RKLB 공시 분석이 아니다. 이 검증은 구조·일부 참조 일치만 확인한다. 수치 정확성·출처 내용·보호된 게시 가능 여부는 후속 단계에서 검증한다.
