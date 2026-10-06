# 1단계 데이터 계약·JSON Schema 작업 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 사용자 지시에 따라 작업 1~4를 하나씩 구현·테스트·로컬 커밋한 뒤 멈추고 한국어로 결과와 다음 작업을 보고한다. 사용자가 '계속'이라고 하기 전에는 다음 작업으로 넘어가지 않는다.

**Goal:** 샘플 화면과 실제 수집 작업이 공유할 버전 있는 데이터 계약·JSON Schema·검증용 사례를 만든다.

**Architecture:** 공통 값·상태·참조 구조를 재사용하고 산출물마다 스키마를 분리한다. Python 검증기는 구조 검사와 파일 간 참조 검사를 분리한다. 실제 계산·투자 판정·네트워크 수집·게시 코드는 이 단계에 포함하지 않는다.

**Tech Stack:** JSON Schema, Python, JSON/Markdown 합성 사례. 구현 시작 시 검증 라이브러리의 지원 사양을 확인하고 스키마 방언·의존성 버전을 고정한다.

**Spec:** [DESIGN.md](../../DESIGN.md), 특히 데이터 계약·판정 기준 v1·구축 순서·공개 빌드 정보 명세.

## 실행 상태 — 2026-10-06

- 사전 확인: Git 2.55.0.windows.1, uv 0.11.26, Python 3.14.6·3.12.13 설치 확인. Python 3.14.6 실행·pip 26.1.2 확인. 일반 python/py 명령은 현재 에이전트 PATH에서 찾을 수 없어 설치된 절대 경로로 확인했다.
- 필요한 jsonschema·referencing·날짜 형식 검증 패키지는 확인한 Python 3.14.6 환경에 없다. Windows 설치 명령을 안내하고 프로젝트 .venv 준비 후 작업 1을 진행한다. 사용할 라이브러리 버전은 환경 준비 후 requirements-dev.txt에 고정한다.
- .gitignore에 비밀 파일·가상환경·실제 분석 산출물을 먼저 제외한 뒤 프로젝트 폴더에서 git init을 완료했다. 원격 저장소는 없다.
- 작업 1: 환경 준비 중, 스키마·테스트 구현 및 완료 커밋 전. 작업 2~4: 시작 전. 작업 1 완료 후 사용자 '계속'을 기다린다.

## Global Constraints

- 스키마는 **v1 초안**이다. 구축 순서 4단계에서 RKLB 실제 공시 데이터가 검증을 통과하기 전까지 수정 가능하며 데이터 사전에도 이 상태를 명시한다. 변경 시 사례·스키마 버전과 변경 근거를 함께 관리한다.
- 구현 전 Python·Git·필요 패키지를 확인하고 없으면 Windows 설치 명령을 안내한다. 비밀 파일을 .gitignore에 먼저 제외하고 프로젝트 폴더에서 git init을 실행한다. 원격 저장소 연결·푸시는 구축 순서 3단계까지 하지 않는다.
- 지원 범위: 10-K·10-Q 제출 US-GAAP 비금융 일반 기업. 신규 상장사는 지원 범위 밖으로 안내한다.
- 판정 기준 버전은 v1, 안내는 '실제 결과 검토 후 조정 예정'. 이미 확정된 판정값을 다시 결정하지 않는다.
- 개별 평가·위험 신호·역DCF 세부 기준 TODO는 구축 순서 5단계 전 결정이다. 구조 정의를 위해 값을 지어내지 않는다.
- 16단계 템플릿 최종본·투자 프레임워크 v2는 입력 대기. 실제 섹션 제목·ID 목록 확정은 원본 수령 후 수행한다.
- 데이터 상태는 ok / not_applicable / unavailable / collection_failed, 근사 여부는 별도 필드. 누락은 null과 사유로 표현한다.
- 가격·평가 등 실제 값과 합성 샘플을 구분한다. sample 여부는 모든 사례의 meta에 명시한다.
- AI 평가와 코드 산출물의 책임을 명시한다. JSON Schema만으로 작성 주체·근거의 진실성을 보증하지 않는다.
- 공개 build-info.json은 commit_sha·built_at 두 필드만 허용한다. schema_version 등 다른 필드도 추가하지 않는다.
- GitHub·Cloudflare 자원 생성은 3단계. 1단계 검증은 API 키·사이트 자격 증명·네트워크 없이 실행한다.

## Review Focus

- 누락값을 0으로, 근사값을 정확한 공시값으로 표현한 사례를 거절한다(작업 1·2).
- 강제 회피가 확인되었지만 역DCF·축 결과는 없는 사례를 표현할 수 있어야 한다(작업 2).
- 규칙 입력 대기를 실제 데이터 부족의 판정 보류로 바꾸거나 게시 가능으로 표시하지 않는다(작업 2·3).
- 같은 기업의 서로 다른 엔진·run_id·data_snapshot_id를 잘못 연결한 묶음을 거절한다(작업 3).
- 공개 빌드 정보의 추가 필드와 실제 템플릿처럼 보이는 임의 샘플 원본을 허용하지 않는다(작업 2·4).

## 작업 1: 공통 계약과 데이터 사전

**Files:** 생성 `docs/DATA_CONTRACT.md`, `schemas/v1/common.schema.json`, `schemas/v1/meta.schema.json`, `schemas/v1/sources.schema.json`, `schemas/v1/run.schema.json`, `requirements-dev.txt`, `tests/contracts/test_common.py`.

**Interfaces:** 공통 정의는 ID·시간대 있는 시각·기간·통화·단위·데이터 상태·근사·출처 참조이다. meta는 schema_version/run_id/data_snapshot_id/analysis_as_of/engine/sample 및 설계서의 버전 필드를 제공한다. run은 단계 상태·입출력 해시·체크포인트를 제공한다.

- [ ] 설계서의 모든 산출물에 대해 필드명·자료형·필수 여부·작성 주체·참조 대상을 데이터 사전에 대응시킨다. 자료형은 정해도 미정 판정값은 채우지 않는다.
- [ ] `test_common.py`에 시간대 누락, 누락값에 사유 없음, 근사 표기 없음, 잘못된 엔진·단계 상태를 거절하고 유효한 공통 값을 허용하는 사례를 작성한다.
- [ ] `python -m unittest discover -s tests/contracts -p test_common.py`로 스키마 미구현 상태의 실패를 확인한다.
- [ ] 공통 스키마와 meta/sources/run 스키마를 작성하고, 지원되는 JSON Schema 방언·검증 라이브러리 버전을 기록·고정한다. 원정밀도 계산과 JSON 숫자 저장 경계도 데이터 사전에 명시한다.
- [ ] 같은 명령으로 통과를 확인한다. 모든 스키마 참조는 저장소 안에서 해결되도록 한다.

## 작업 2: 산출물별 스키마와 유효·무효 사례

**Files:** 생성 `schemas/v1/` 아래 `metrics.schema.json`, `extracted-facts.schema.json`, `valuation.schema.json`, `assessments.schema.json`, `decision.schema.json`, `financials-analysis.schema.json`, `dashboard.schema.json`, `report-items.schema.json`, `template-items.schema.json`, `template-notes.schema.json`, `sections.schema.json`, `diagrams-meta.schema.json`, `validation.schema.json`, `build-info.schema.json`. 생성 `tests/contracts/test_artifacts.py`, `tests/fixtures/contracts/valid/`, `tests/fixtures/contracts/invalid/`.

**Interfaces:** 각 스키마는 설계서의 동명 JSON을 검사한다. sections는 실제 원본의 목록이 아닌 목록 형식만 정의한다. report.md·template.md·Mermaid는 JSON Schema 대상 대신 run/validation의 경로·해시 참조 대상으로 정의한다. 규칙 준비 상태는 평가·계산 상태와 별도로 표현하고 미정 규칙의 ID·사유를 기록한다.

- [ ] 정상·누락·근사·확인된 강제 회피·미정 규칙 사례를 만든다. 미정 규칙은 실행 blocked·게시 불가로, 실제 입력 부족의 완성 보고서는 판정 보류로 구분한다.
- [ ] `test_artifacts.py`에 유효 사례 허용과 enum 오타·누락 사유 없음·추가 빌드 정보 필드·미정 규칙인데 게시 가능인 사례 거절을 작성한다.
- [ ] `python -m unittest discover -s tests/contracts -p test_artifacts.py`의 실패를 확인한 뒤 스키마를 작성한다. 필요한 값 존재 여부·null 허용을 조건부로 표현한다.
- [ ] valuation은 10년·2.5%·기본 10%와 민감도 9%/11%를 담고, assessments는 다섯 품질 항목·성장률 하단/기본/상단을 담도록 한다. decision에는 확정된 규칙/표 칸과 적용 순서를 기록하되 실제 판정 함수는 구현하지 않는다.
- [ ] build-info에는 전체 커밋 해시와 UTC 빌드 시각만 허용하고 추가 필드를 거절한다. 이 스키마 자체의 버전은 파일 경로에서 관리한다.
- [ ] 같은 명령으로 통과를 확인한다. 강제 회피와 미산출 축의 조합, 규칙 입력 대기와 데이터 누락의 차이를 데이터 사전에 예시로 남긴다.

## 작업 3: 파일 간 검증과 오프라인 실행 명령

**Files:** 생성 `scripts/validate_contract.py`, `tests/contracts/test_bundle.py`. 작업 2의 fixtures 확장.

**Interfaces:** `validate_bundle(bundle_dir: Path, schema_dir: Path) -> list[dict[str, str]]`. 오류 항목은 `code`, `file`, `path`, `message` 문자열을 갖는다. CLI는 `python scripts/validate_contract.py <bundle_dir> --schemas schemas/v1`, 유효하면 종료 코드 0, 계약 오류면 1. 구조 통과를 S6 완료나 게시 승인으로 표현하지 않는다.

- [ ] `test_bundle.py`에 존재하지 않는 source_id/metric_ref, 묶음 내 run_id·snapshot 불일치, dashboard와 decision 참조 불일치 사례를 작성한다. 다른 엔진 묶음끼리 스냅샷이 다른 것은 비교 가능한 상태이며 묶음 내부 불일치와 구분한다.
- [ ] `python -m unittest discover -s tests/contracts -p test_bundle.py`로 실패를 확인한다.
- [ ] 구조 검사 후 참조 대상 존재·고유성·입력/실행 일치를 검사한다. 성장률 범위의 순서·대상·단위 일치도 검사하되 미정 역DCF 계산식을 구현하지 않는다.
- [ ] 같은 명령과 유효/무효 fixture의 CLI를 실행해 종료 코드와 오류 위치를 확인한다. 외부 URL에 접속하거나 원본 보고서를 자동 보충하지 않는다.

## 작업 4: 샘플 화면·수집 작업에 인계

**Files:** 생성 `examples/contracts/rklb/claude/`, `examples/contracts/rklb/gpt/`, `examples/contracts/README.md`. 수정 `docs/DATA_CONTRACT.md`, `docs/DESIGN.md`의 1단계 진행 상태·변경 기록.

**Interfaces:** 두 엔진 예시는 같은 스키마를 따르며 sample=true를 명시한다. 원본 미입력은 입력 대기로 표현하고, 보고서 항목 구조 예시는 테스트 전용 ID로 분리해 실제 16단계 템플릿 목록에 등록하지 않는다. 산업 데이터·공개 저장소 배포 설정은 생성하지 않는다.

- [ ] 두 엔진의 항목 평가 차이와 입력 스냅샷 차이를 구분해 볼 수 있는 예시를 만들고, 모든 금액·평가는 합성임을 표시한다.
- [ ] 두 예시를 CLI로 검증하고 `python -m unittest discover -s tests/contracts` 전체를 실행한다. 예시 내 참조 누락·비밀 값·실제 원본으로 오인할 템플릿이 없는지 검토한다.
- [ ] 데이터 사전에 스키마 버전 변경·구형 결과 처리 원칙, 5단계 전 채울 규칙, 원본 수령 후 확정할 항목 목록을 기록한다.
- [ ] 화면 담당은 3단계, 수집 담당은 4단계에 착수할 수 있도록 파일별 소비 위치·검증 명령을 README에 기록한다. 각 작업 완료 시 로컬 커밋은 남기고, 원격 저장소 연결·푸시는 구축 순서 3단계까지 수행하지 않는다.

## 완료 기준

구조와 파일 간 참조 검증이 유효 사례를 허용하고 무효 사례를 거절한다. 미정 규칙·원본 입력 대기를 숨기지 않으면서 샘플 화면·수집 작업에 필요한 형식을 제공한다. 실제 공시 분석·역DCF 계산·최종 판정 구현·사이트 배포는 1단계 완료 주장에 포함하지 않는다.
