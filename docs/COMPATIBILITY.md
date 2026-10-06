# 2단계 실행 환경 확인

2026-10-06 기준. 이번 확인은 Windows 로컬 환경에서 수행했다.

| 항목 | 확인 결과 |
| --- | --- |
| Python | 프로젝트 `.venv`의 3.14.6에서 `jsonschema` 4.26.0 사용 확인 |
| Node.js / npm | 24.19.0 / 11.17.0 실행 확인 |
| Claude Code | CLI 2.1.199 실행. `claude plugin validate --strict .` 통과. `claude -p '/company RKLB --sample' --plugin-dir .`는 **로그인 필요**로 종료돼 실제 스킬 호출은 미확인 |
| Codex | CLI 0.160.0 실행. 루트 `plugin.json`과 `skills/company/SKILL.md` 마련. 프로젝트 Python 명령을 `--engine gpt`로 실행해 검증 통과. Codex 설치형 플러그인 호출은 공개 저장소 준비 후 확인 필요 |
| 공통 명령 | `scripts/company.py RKLB --engine claude --sample`과 `--engine gpt --sample` 모두 합성 묶음을 생성했고 `scripts/validate_bundle.py` 통과 |
| Twelve Data | API 키가 현재 환경에 없어 무료 요금제의 배당 이력·실적 발표 일정 제공 여부는 **미확인**. 키를 확보하면 실제 계정으로 각 엔드포인트를 확인하고, 미제공 시 배당은 SEC 공시·발표일은 웹 리서치로 대체 |

샘플 결과는 `runs/` 아래에만 남기며 `sample=true`이다. 실제 RKLB 공시 분석이라고 안내하지 않는다. 사용자의 Claude Code 로그인과 Twelve Data 키가 준비되면 각각 실제 스킬 호출·무료 API 권한을 다시 확인한다. 로그인 정보와 API 키는 이 문서에 기록하지 않는다.

## 알려진 문제

- Claude Code 실제 스킬 호출: CLI에서 `Not logged in · Please run /login`을 반환했다. 로그인 전까지 형식 검증과 공통 Python 실행만 확인 가능하다.
- Twelve Data 무료 배당·실적 발표 일정: API 키가 없어 계정별 제공 여부를 확인하지 못했다. 미확인 상태를 무료 제공 또는 미제공으로 단정하지 않는다.
