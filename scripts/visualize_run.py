"""Generate a conservative Mermaid chronology from verified annual revenue."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_visualization(folder: Path):
    report_path = folder / "report.md"
    report_hash = digest(report_path)
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))["metrics"]
    annual = sorted((m for m in metrics if m["metric_id"].startswith("revenue_fy") and m["status"] == "ok"),
                    key=lambda m: m["metric_id"])
    if len(annual) < 2:
        raise ValueError("연간 매출 2개 이상이 없어 도식을 만들 수 없음")
    labels = [f"Y{i}[\"FY{m['metric_id'][-4:]} 매출 {m['value'] / 1_000_000:,.1f}M USD\"]" for i, m in enumerate(annual)]
    content = "flowchart LR\n  " + " --> ".join(labels) + "\n"
    if digest(report_path) != report_hash:
        raise ValueError("도식 생성 중 기준 보고서가 변경됨")
    diagram_dir = folder / "diagrams"
    diagram_dir.mkdir(exist_ok=True)
    diagram_path = diagram_dir / "revenue.mmd"
    diagram_path.write_text(content, encoding="utf-8")
    manifest = {"report_run_id": meta["run_id"], "data_snapshot_id": meta["data_snapshot_id"],
                "report_sha256": report_hash, "diagram_sha256": digest(diagram_path),
                "kind": "verified_revenue_chronology"}
    (diagram_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if digest(report_path) != report_hash:
        raise ValueError("도식 생성 중 기준 보고서가 변경됨")
    return diagram_path


def verify_visualization(folder: Path):
    try:
        manifest = json.loads((folder / "diagrams" / "manifest.json").read_text(encoding="utf-8"))
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        if manifest["report_run_id"] != meta["run_id"] or manifest["data_snapshot_id"] != meta["data_snapshot_id"]:
            return ["도식 기준 실행·스냅샷 불일치"]
        if manifest["report_sha256"] != digest(folder / "report.md"):
            return ["도식 기준 보고서 해시 불일치"]
        if manifest["diagram_sha256"] != digest(folder / "diagrams" / "revenue.mmd"):
            return ["도식 파일 해시 불일치"]
        return []
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return [f"도식 검증 실패: {exc}"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    print(build_visualization(args.bundle))
