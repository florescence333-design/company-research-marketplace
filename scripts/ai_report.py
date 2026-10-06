"""Finalize a model-written, sourced 16-section report without changing SEC facts."""

import argparse
import json
import re
from pathlib import Path

from company import write_run_state
from report import build_report_items, render_report, validate_report_items
from validate_bundle import validate_bundle
from visualize_run import build_visualization


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_ai_changes(report, bundle, section_ids=None):
    errors = validate_report_items(report, bundle)
    baseline = build_report_items(bundle)
    selected = set(section_ids) if section_ids else None
    if selected is not None:
        known = {section["section_id"] for section in baseline["sections"]}
        if selected - known:
            errors.append("알 수 없는 선택 섹션: " + ", ".join(sorted(selected - known)))
    changed = sum(new.get("body") != old["body"] for new, old in zip(report.get("sections", []), baseline["sections"])
                  if selected is None or new.get("section_id") in selected)
    if changed < (len(selected) if selected else 3):
        errors.append("선택 섹션 전부 또는 전체 실행의 3개 이상을 실질 수정해야 함")
    for section in report.get("sections", []):
        if selected is not None and section.get("section_id") not in selected:
            continue
        section_id = section.get("section_id")
        if not section.get("search_queries"):
            errors.append(f"{section_id}: 웹 검색어 기록 없음")
        if section.get("status") == "partial" and not section.get("source_ids"):
            errors.append(f"{section_id}: 부분 분석에 출처 ID 없음")
        if section.get("status") == "partial" and not any(s.startswith("web-") for s in section.get("source_ids", [])):
            errors.append(f"{section_id}: 웹 리서치 출처 ID 없음")
        if section.get("status") == "partial" and ("[해석]" not in section.get("body", "") or "반대 논거" not in section.get("body", "")):
            errors.append(f"{section_id}: [해석] 또는 반대 논거 없음")
        if section.get("status") == "unavailable" and "자료 확인 대기" not in section.get("body", ""):
            errors.append(f"{section_id}: 검색 후 미확인 상태 설명 없음")
        if section_id == "S12" and section.get("status") == "partial":
            body = section.get("body", "")
            if "|" not in body or not re.search(r"20\d{2}", body) or re.search(r"\b[a-z]+(?:_[a-z0-9]+)+\b", body):
                errors.append("S12: 한국어 지표명·연도별 표를 사용하고 내부 변수명은 본문에서 제외해야 함")
    if not report.get("sections") or "판정 보류 (v0.1)" not in report["sections"][-1].get("body", ""):
        errors.append("최종 판정 고정 문구 누락")
    return errors


def finalize(folder: Path, model: str, section_ids=None):
    if not model.strip():
        raise ValueError("AI 실행 모델 식별자가 필요함")
    meta = read_json(folder / "meta.json")
    if meta["sample"]:
        raise ValueError("합성 샘플은 AI 분석 완료로 표시할 수 없음")
    bundle = {name: read_json(folder / f"{name}.json")
              for name in ("meta", "metrics", "sources", "decision", "extracted-facts")}
    report = read_json(folder / "report-items.json")
    errors = validate_ai_changes(report, bundle, section_ids)
    if errors:
        raise ValueError("; ".join(errors))
    run = read_json(folder / "run.json")
    original = {}
    affected = [folder / name for name in ("meta.json", "report.md", "run.json", "validation.json",
                                            "diagrams/manifest.json", "diagrams/revenue.mmd", "review-only.json")]
    for path in affected:
        original[path] = path.read_bytes() if path.exists() else None
    try:
        meta["model"] = model
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (folder / "report.md").write_text(render_report(report, bundle), encoding="utf-8")
        (folder / "validation.json").unlink(missing_ok=True)
        no_viz = run["options"].get("no_viz", False)
        if not no_viz:
            build_visualization(folder)
        write_run_state(folder, no_viz, run["options"].get("original", False))
        review_marker = folder / "review-only.json"
        if section_ids:
            review_marker.write_text(json.dumps({"sections": sorted(set(section_ids))}, ensure_ascii=False) + "\n", encoding="utf-8")
        else:
            review_marker.unlink(missing_ok=True)
        errors = validate_bundle(folder)
        if errors:
            raise ValueError("; ".join(errors))
    except Exception:
        for path, content in original.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        raise
    return folder / "report.md"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--model", required=True, help="Actual AI provider/model label; use claude-code if exact model unknown")
    parser.add_argument("--sections", nargs="+", help="Only validate these reanalyzed section IDs; review runs only")
    args = parser.parse_args()
    try:
        print(finalize(args.bundle, args.model, args.sections))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
