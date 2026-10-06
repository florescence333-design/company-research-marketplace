"""Finalize a model-written, sourced 16-section report without changing SEC facts."""

import argparse
import json
from pathlib import Path

from company import write_run_state
from report import build_report_items, render_report, validate_report_items
from validate_bundle import validate_bundle
from visualize_run import build_visualization


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_ai_changes(report, bundle):
    errors = validate_report_items(report, bundle)
    baseline = build_report_items(bundle)
    changed = sum(new.get("body") != old["body"] for new, old in zip(report.get("sections", []), baseline["sections"]))
    if changed < 3:
        errors.append("AI가 수정한 섹션이 3개 미만임")
    for section in report.get("sections", []):
        if section.get("status") == "partial" and not section.get("source_ids"):
            errors.append(f"{section.get('section_id')}: 부분 분석에 출처 ID 없음")
    if not report.get("sections") or "판정 보류 (v0.1)" not in report["sections"][-1].get("body", ""):
        errors.append("최종 판정 고정 문구 누락")
    return errors


def finalize(folder: Path, model: str):
    if not model.strip():
        raise ValueError("AI 실행 모델 식별자가 필요함")
    meta = read_json(folder / "meta.json")
    if meta["sample"]:
        raise ValueError("합성 샘플은 AI 분석 완료로 표시할 수 없음")
    bundle = {name: read_json(folder / f"{name}.json")
              for name in ("meta", "metrics", "sources", "decision", "extracted-facts")}
    report = read_json(folder / "report-items.json")
    errors = validate_ai_changes(report, bundle)
    if errors:
        raise ValueError("; ".join(errors))
    run = read_json(folder / "run.json")
    original = {}
    affected = [folder / name for name in ("meta.json", "report.md", "run.json", "validation.json",
                                            "diagrams/manifest.json", "diagrams/revenue.mmd")]
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
    args = parser.parse_args()
    try:
        print(finalize(args.bundle, args.model))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
