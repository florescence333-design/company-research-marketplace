"""Finalize a model-written, sourced 16-section report without changing SEC facts."""

import argparse
import json
import re
from pathlib import Path

from company import write_run_state
from report import build_report_items, recalculate_statuses, render_report, validate_report_items
from template_stage import validate_template
from validate_bundle import validate_bundle
from visualize_run import build_visualization


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_ai_changes(report, bundle, section_ids=None):
    errors = validate_report_items(report, bundle)
    baseline = build_report_items(bundle)
    items = {item["section_id"]: item for section in report.get("sections", [])
             for item in [section, *section.get("subsections", [])]}
    baseline_items = {item["section_id"]: item for item in baseline["sections"]}
    selected = set(section_ids) if section_ids else None
    if selected is not None:
        known = set(items)
        if selected - known:
            errors.append("알 수 없는 선택 섹션: " + ", ".join(sorted(selected - known)))
    changed = sum(item.get("body") != baseline_items.get(sid, {}).get("body")
                  for sid, item in items.items() if selected is None or sid in selected)
    if changed < (len(selected) if selected else 3):
        errors.append("선택 섹션 전부 또는 전체 실행의 3개 이상을 실질 수정해야 함")
    for section_id, section in items.items():
        if selected is not None and section_id not in selected:
            continue
        if not section.get("search_queries"):
            errors.append(f"{section_id}: 웹 검색어 기록 없음")
        if section.get("source_ids") and not any(s.startswith("web-") for s in section.get("source_ids", [])):
            errors.append(f"{section_id}: 웹 리서치 출처 ID 없음")
        if section.get("source_ids") and ("[해석]" not in section.get("body", "") or "반대 논거" not in section.get("body", "")):
            errors.append(f"{section_id}: [해석] 또는 반대 논거 없음")
        if not section.get("source_ids") and "자료 확인 대기" not in section.get("body", ""):
            errors.append(f"{section_id}: 검색 후 미확인 상태 설명 없음")
        if section_id == "S12" and section.get("source_ids"):
            body = section.get("body", "")
            if "|" not in body or not re.search(r"20\d{2}", body) or re.search(r"\b[a-z]+(?:_[a-z0-9]+)+\b", body):
                errors.append("S12: 한국어 지표명·연도별 표를 사용하고 내부 변수명은 본문에서 제외해야 함")
    if not report.get("sections") or "판정 보류 (v0.1)" not in report["sections"][-1].get("body", ""):
        errors.append("최종 판정 고정 문구 누락")
    return errors


def finalize(folder: Path, model: str, section_ids=None, checkpoint=False):
    if not model.strip():
        raise ValueError("AI 실행 모델 식별자가 필요함")
    meta = read_json(folder / "meta.json")
    if meta["sample"]:
        raise ValueError("합성 샘플은 AI 분석 완료로 표시할 수 없음")
    bundle = {name: read_json(folder / f"{name}.json")
              for name in ("meta", "metrics", "sources", "decision", "extracted-facts")}
    report = read_json(folder / "report-items.json")
    errors = validate_ai_changes(report, bundle, section_ids)
    if (folder / "template-notes.json").exists():
        errors.extend(validate_template(folder))
        if not errors:
            notes = read_json(folder / "template-notes.json")
            for parent in notes["sections"]:
                report_parent = next((s for s in report["sections"] if s["section_id"] == parent["section_id"]), None)
                actual = {s["section_id"] for s in report_parent.get("subsections", [])} if report_parent else set()
                expected = {s["section_id"] for s in parent["subsections"]}
                if actual != expected:
                    errors.append(f"{parent['section_id']}: 커스텀 하위 섹션 불일치")
    if errors:
        raise ValueError("; ".join(errors))
    run = read_json(folder / "run.json")
    original = {}
    affected = [folder / name for name in ("meta.json", "report-items.json", "report.md", "run.json", "validation.json",
                                            "diagrams/manifest.json", "diagrams/flywheel.mmd", "diagrams/value-chain.mmd", "review-only.json", "analysis-progress.json")]
    for path in affected:
        original[path] = path.read_bytes() if path.exists() else None
    try:
        if checkpoint:
            progress = read_json(folder / "analysis-progress.json") if (folder / "analysis-progress.json").exists() else {"completed_sections": []}
            verified_ids = set(progress["completed_sections"]) | set(section_ids or [])
        elif section_ids:
            verified_ids = set(section_ids)
        else:
            verified_ids = {item["section_id"] for section in report["sections"]
                            for item in (section, *section.get("subsections", []))}
        recalculate_statuses(report, verified_ids)
        (folder / "report-items.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not checkpoint:
            meta["model"] = model
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        bundle["meta"] = meta
        (folder / "report.md").write_text(render_report(report, bundle), encoding="utf-8")
        (folder / "validation.json").unlink(missing_ok=True)
        no_viz = run["options"].get("no_viz", False)
        if not checkpoint and not no_viz and (folder / "diagrams" / "spec.json").exists():
            build_visualization(folder)
        write_run_state(folder, no_viz, run["options"].get("original", False))
        review_marker = folder / "review-only.json"
        if checkpoint:
            progress = read_json(folder / "analysis-progress.json") if (folder / "analysis-progress.json").exists() else {"completed_sections": []}
            progress["completed_sections"] = sorted(set(progress["completed_sections"]) | set(section_ids or []))
            (folder / "analysis-progress.json").write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        elif section_ids:
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
    parser.add_argument("--checkpoint", action="store_true", help="Save a researched section bundle; requires --sections")
    args = parser.parse_args()
    try:
        if args.checkpoint and not args.sections:
            parser.error("--checkpoint requires --sections")
        print(finalize(args.bundle, args.model, args.sections, args.checkpoint))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
