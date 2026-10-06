"""S0.5 custom framework contract and Markdown renderer."""

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER = json.loads((ROOT / "template" / "sections.json").read_text(encoding="utf-8"))["sections"]
KINDS = {"원본 그대로", "보강", "신설", "전면 교체"}


def render_metric_definition(definition):
    if isinstance(definition, str):
        return definition
    if not isinstance(definition, dict):
        raise ValueError("지표 정의는 문자열 또는 필드 객체여야 함")
    required = ("metric", "formula", "unit", "period", "source")
    if any(not isinstance(definition.get(key), str) or not definition[key].strip() for key in required):
        raise ValueError("지표 정의 객체의 이름·공식·단위·기간·출처 누락")
    result = (f"{definition['metric']} = {definition['formula']} · 단위: {definition['unit']} · "
              f"기간: {definition['period']} · 출처: {definition['source']}")
    if definition.get("note"):
        result += f" · 주의: {definition['note']}"
    return result


def create_template_draft(folder: Path) -> None:
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    notes = {
        "schema_version": "v1-draft", "run_id": meta["run_id"],
        "data_snapshot_id": meta["data_snapshot_id"], "status": "draft",
        "suitability": "평가 대기", "suitability_reason": "웹 리서치 후 작성",
        "source_ids": [], "search_queries": [],
        "sections": [{"section_id": s["section_id"], "title": s["title"],
                      "change_type": "원본 그대로", "rationale": "평가 대기",
                      "checklist": [], "metric_definitions": [], "analogy": "작성 대기",
                      "subsections": []} for s in MASTER],
    }
    (folder / "template-notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "template.md").write_text(render_template(notes), encoding="utf-8")


def render_template(notes: dict) -> str:
    lines = ["# 기업별 커스텀 분석 프레임워크", "", "## 적합성 판정", "",
             f"**{notes['suitability']}** — {notes['suitability_reason']}", "",
             "## 원본 대비 개정 구분표", "", "| 섹션 | 구분 | 이유 |", "| --- | --- | --- |"]
    for section in notes["sections"]:
        lines.append(f"| {section['section_id']} {section['title']} | {section['change_type']} | {section['rationale']} |")
        for sub in section.get("subsections", []):
            lines.append(f"| {sub['section_id']} {sub['title']} | 신설 | {sub['rationale']} |")
    lines.extend(["", "## 섹션별 상세 프레임워크", ""])
    for section in notes["sections"]:
        for item, level in [(section, "###"), *[(sub, "####") for sub in section.get("subsections", [])]]:
            lines.extend([f"{level} {item['section_id']} {item['title']}", "",
                          f"**개정 이유:** {item['rationale']}", "", "**확인할 질문·체크리스트**", ""])
            lines.extend(f"- {check}" for check in item["checklist"])
            lines.extend(["", "**지표 정의**", ""])
            lines.extend(f"- {render_metric_definition(definition)}" for definition in item["metric_definitions"])
            lines.extend(["", f"**쉬운 비유:** {item['analogy']}", ""])
    if notes["source_ids"]:
        lines.extend(["## 프레임워크 출처", "", ", ".join(notes["source_ids"]), ""])
    return "\n".join(lines)


def validate_template(folder: Path) -> list[str]:
    path = folder / "template-notes.json"
    if not path.exists() or not (folder / "template.md").exists():
        return ["S0.5 템플릿 산출물 없음"]
    try:
        notes = json.loads(path.read_text(encoding="utf-8"))
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        if notes["status"] != "completed":
            return ["S0.5 커스텀 템플릿 미완료"]
        errors = []
        if (notes["run_id"], notes["data_snapshot_id"]) != (meta["run_id"], meta["data_snapshot_id"]):
            errors.append("S0.5 실행·스냅샷 ID 불일치")
        if not notes["search_queries"] or not notes["source_ids"] or notes["suitability"] == "평가 대기":
            errors.append("S0.5 적합성 평가의 검색·출처 기록 없음")
        source_ids = {s["source_id"] for s in json.loads((folder / "sources.json").read_text(encoding="utf-8"))["sources"]}
        if set(notes["source_ids"]) - source_ids or not any(s.startswith("web-") for s in notes["source_ids"]):
            errors.append("S0.5 웹 출처 ID 불일치 또는 누락")
        sections = notes["sections"]
        if [(s["section_id"], s["title"]) for s in sections] != [(s["section_id"], s["title"]) for s in MASTER]:
            errors.append("S0.5 원본 16개 대섹션 ID·제목·순서 불일치")
        seen = set()
        for section in sections:
            for item in [section, *section.get("subsections", [])]:
                sid = item["section_id"]
                if sid in seen or (item is not section and not re.fullmatch(re.escape(section["section_id"]) + r"-[A-Z]", sid)):
                    errors.append(f"S0.5 하위 섹션 ID 오류: {sid}")
                seen.add(sid)
                if item["change_type"] not in KINDS or not item["rationale"] or not item["checklist"] or not item["metric_definitions"] or not item["analogy"]:
                    errors.append(f"S0.5 상세 프레임워크 누락: {sid}")
        if (folder / "template.md").read_text(encoding="utf-8") != render_template(notes):
            errors.append("S0.5 template.md와 template-notes.json 불일치")
        return errors
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return [f"S0.5 템플릿 검증 실패: {exc}"]


def sync_report_subsections(folder: Path) -> None:
    """Create pending report slots for every custom subsection without erasing analysis."""
    if validate_template(folder):
        raise ValueError("검증된 커스텀 템플릿만 보고서에 반영할 수 있음")
    from report import render_report
    notes = json.loads((folder / "template-notes.json").read_text(encoding="utf-8"))
    report = json.loads((folder / "report-items.json").read_text(encoding="utf-8"))
    bundle = {name: json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
              for name in ("meta", "metrics", "sources", "decision", "extracted-facts")}
    for section, framework in zip(report["sections"], notes["sections"]):
        existing = {sub["section_id"]: sub for sub in section.get("subsections", [])}
        section["subsections"] = [existing.get(sub["section_id"], {
            "section_id": sub["section_id"], "title": sub["title"], "status": "unavailable",
            "body": "자료 확인 대기: 커스텀 프레임워크에 따라 웹 리서치 후 작성한다.",
            "source_ids": [], "metric_ids": [], "fact_ids": [], "search_queries": [],
        }) for sub in framework["subsections"]]
    (folder / "report-items.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "report.md").write_text(render_report(report, bundle), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--render", action="store_true", help="Write template.md from edited notes")
    args = parser.parse_args()
    if args.render:
        notes = json.loads((args.bundle / "template-notes.json").read_text(encoding="utf-8"))
        (args.bundle / "template.md").write_text(render_template(notes), encoding="utf-8")
    errors = validate_template(args.bundle)
    if args.render and not errors:
        sync_report_subsections(args.bundle)
    for error in errors:
        print(error)
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
