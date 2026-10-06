"""Validate a minimal company bundle against the v1 draft contract."""

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas" / "v1"
REQUIRED = ("meta", "metrics", "decision", "sources")
OPTIONAL = ("extracted-facts",)


def validate_bundle(folder: Path) -> list[str]:
    errors = []
    objects = {}
    for name in REQUIRED + tuple(name for name in OPTIONAL if (folder / f"{name}.json").exists()):
        path = folder / f"{name}.json"
        try:
            objects[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{name}.json: 읽기 실패: {exc}")
            continue
        schema = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for error in validator.iter_errors(objects[name]):
            location = "/".join(map(str, error.path)) or "root"
            errors.append(f"{name}.json/{location}: {error.message}")
    if "meta" in objects:
        meta = objects["meta"]
        for name in ("metrics", "decision", "extracted-facts"):
            obj = objects.get(name)
            if not isinstance(obj, dict):
                continue
            for key in ("run_id", "data_snapshot_id"):
                if key in obj and obj[key] != meta.get(key):
                    errors.append(f"{name}.json/{key}: meta.json과 불일치")
    if "metrics" in objects and "sources" in objects:
        sources = {item.get("source_id") for item in objects["sources"].get("sources", [])}
        for index, metric in enumerate(objects["metrics"].get("metrics", [])):
            for source_id in metric.get("source_ids", []):
                if source_id not in sources:
                    errors.append(f"metrics.json/metrics/{index}/source_ids: 알 수 없는 {source_id}")
    if "extracted-facts" in objects and "sources" in objects:
        sources = {item.get("source_id") for item in objects["sources"].get("sources", [])}
        for index, fact in enumerate(objects["extracted-facts"].get("facts", [])):
            if fact.get("source_id") not in sources:
                errors.append(f"extracted-facts.json/facts/{index}/source_id: 알 수 없는 출처")
    report_path = folder / "report-items.json"
    if report_path.exists() and all(name in objects for name in REQUIRED):
        from report import render_report, validate_report_items
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            errors.extend(f"report-items.json: {error}" for error in validate_report_items(report, objects))
            if (folder / "report.md").read_text(encoding="utf-8") != render_report(report, objects):
                errors.append("report-items.json: 보고서 본문과 report.md 불일치")
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            errors.append(f"report-items.json: 읽기 실패: {exc}")
    run_path = folder / "run.json"
    if run_path.exists():
        try:
            run = json.loads(run_path.read_text(encoding="utf-8"))
            schema = json.loads((SCHEMAS / "run.schema.json").read_text(encoding="utf-8"))
            errors.extend(f"run.json: {error.message}" for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(run))
            if "meta" in objects and (run.get("run_id") != objects["meta"].get("run_id") or run.get("data_snapshot_id") != objects["meta"].get("data_snapshot_id")):
                errors.append("run.json: meta.json과 실행·스냅샷 ID 불일치")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"run.json: 읽기 실패: {exc}")
    if (folder / "diagrams" / "manifest.json").exists():
        from visualize_run import verify_visualization
        errors.extend(verify_visualization(folder))
    validation_path = folder / "validation.json"
    if validation_path.exists():
        try:
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
            schema = json.loads((SCHEMAS / "validation.schema.json").read_text(encoding="utf-8"))
            errors.extend(f"validation.json: {error.message}" for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(validation))
            if "meta" in objects and (validation.get("run_id") != objects["meta"].get("run_id") or validation.get("data_snapshot_id") != objects["meta"].get("data_snapshot_id")):
                errors.append("validation.json: meta.json과 실행·스냅샷 ID 불일치")
            if validation.get("report_sha256") != hashlib.sha256((folder / "report.md").read_bytes()).hexdigest():
                errors.append("validation.json: 보고서 해시 불일치")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"validation.json: 읽기 실패: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    errors = validate_bundle(args.bundle)
    for error in errors:
        print(error)
    if errors:
        return 1
    print("v1 draft schema validation passed; financial and decision checks are separate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
