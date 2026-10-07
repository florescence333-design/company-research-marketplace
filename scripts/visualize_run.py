"""Validate and publish two report-grounded Mermaid business diagrams."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _items(folder: Path) -> dict:
    report = json.loads((folder / "report-items.json").read_text(encoding="utf-8"))
    return {item["section_id"]: item for section in report["sections"]
            for item in [section, *section.get("subsections", [])]}


def validate_spec(folder: Path, spec: dict) -> list[str]:
    errors = []
    items = _items(folder)
    if set(spec) != {"flywheel", "value_chain"}:
        return ["플라이휠·밸류체인 도식 두 개가 필요함"]
    for kind, diagram in spec.items():
        refs = diagram.get("section_ids", [])
        if len(refs) < 2 or any(sid not in items or items[sid]["status"] not in ("complete", "partial") for sid in refs):
            errors.append(f"{kind}: 분석 완료된 보고서 섹션 두 개 이상을 근거로 지정해야 함")
        if len(diagram.get("explanation", [])) not in (3, 4) or any(not line.strip() for line in diagram["explanation"]):
            errors.append(f"{kind}: 쉬운 설명 3~4줄 필요")
        mermaid = diagram.get("mermaid", "")
        if not mermaid.startswith("flowchart ") or "-->" not in mermaid:
            errors.append(f"{kind}: Mermaid 흐름도 필요")
        if kind == "flywheel" and (not 5 <= len(diagram.get("elements", [])) <= 7 or
                                    len(set(diagram.get("elements", []))) != len(diagram.get("elements", [])) or
                                    mermaid.count("-->") < 5 or "위험" not in mermaid):
            errors.append("flywheel: 5~7개 요소의 순환 화살표와 위험 표시 필요")
        if kind == "value_chain" and ("직접" not in mermaid or "외부" not in mermaid):
            errors.append("value_chain: 자체 제작·외부 의존 구분 필요")
    return errors


def build_visualization(folder: Path):
    report_path = folder / "report.md"
    report_hash = digest(report_path)
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    spec = json.loads((folder / "diagrams" / "spec.json").read_text(encoding="utf-8"))
    errors = validate_spec(folder, spec)
    if errors:
        raise ValueError("; ".join(errors))
    if digest(report_path) != report_hash:
        raise ValueError("도식 생성 중 기준 보고서가 변경됨")
    diagram_dir = folder / "diagrams"
    hashes = {}
    for kind, name in (("flywheel", "flywheel.mmd"), ("value_chain", "value-chain.mmd")):
        path = diagram_dir / name
        path.write_text(spec[kind]["mermaid"].rstrip() + "\n", encoding="utf-8")
        hashes[name] = digest(path)
    manifest = {"report_run_id": meta["run_id"], "data_snapshot_id": meta["data_snapshot_id"],
                "report_sha256": report_hash, "spec_sha256": digest(diagram_dir / "spec.json"),
                "diagram_sha256": hashes, "kind": "report_grounded_business_diagrams"}
    (diagram_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if digest(report_path) != report_hash:
        raise ValueError("도식 생성 중 기준 보고서가 변경됨")
    return diagram_dir


def verify_visualization(folder: Path):
    try:
        manifest = json.loads((folder / "diagrams" / "manifest.json").read_text(encoding="utf-8"))
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        if manifest["report_run_id"] != meta["run_id"] or manifest["data_snapshot_id"] != meta["data_snapshot_id"]:
            return ["도식 기준 실행·스냅샷 불일치"]
        if manifest["report_sha256"] != digest(folder / "report.md"):
            return ["도식 기준 보고서 해시 불일치"]
        if manifest["spec_sha256"] != digest(folder / "diagrams" / "spec.json"):
            return ["도식 설명·근거 파일 해시 불일치"]
        for name, expected in manifest["diagram_sha256"].items():
            if expected != digest(folder / "diagrams" / name):
                return [f"{name} 도식 파일 해시 불일치"]
        return validate_spec(folder, json.loads((folder / "diagrams" / "spec.json").read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return [f"도식 검증 실패: {exc}"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    print(build_visualization(args.bundle))
