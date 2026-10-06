"""Run the small, reproducible company-analysis path (v0.1)."""

import argparse
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sec import build_sec_bundle, fetch_companyfacts
from validate_bundle import validate_bundle


ROOT = Path(__file__).resolve().parents[1]


def write_real_run(output: Path, engine: str) -> None:
    now = datetime.now(timezone.utc)
    cache = ROOT / "data" / "sec" / "rklb-companyfacts.json"
    data, raw = fetch_companyfacts(cache)
    bundle = build_sec_bundle(data, raw, engine, now)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"Output directory is not empty: {output}")
    for name, obj in bundle.items():
        (output / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# RKLB 공시 기반 재무 스냅샷", "", f"기준 시각: {bundle['meta']['analysis_as_of']}",
             "자료: SEC Company Facts. 아래 수치는 공시 태그에서 코드로 추린 값이며 16단계 기업 분석은 아직 작성되지 않았습니다.",
             "", "| 항목 | 값 | 기간 종료 | 출처 ID |", "| --- | ---: | --- | --- |"]
    for metric in bundle["metrics"]["metrics"]:
        if metric["status"] == "ok":
            value = f"{metric['value']:,} {metric['unit']}" + (" (근사)" if metric["approximate"] else "")
            lines.append(f"| {metric['metric_id']} | {value} | {metric['period_end']} | {', '.join(metric['source_ids'])} |")
    lines.extend(["", "투자 판정: **판정 보류 (v0.1)**. 판정 엔진과 16단계 해석은 미구현입니다."])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    parser.add_argument("--engine", choices=("claude", "gpt"), required=True)
    parser.add_argument("--sample", action="store_true", help="Copy visibly synthetic RKLB example")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--site-data", action="store_true", help="Copy validated bundle to local ignored site/data")
    args = parser.parse_args()
    ticker = args.ticker.upper()
    if ticker != "RKLB":
        parser.error("The v0.1 collector currently supports RKLB only")
    run_id = f"{'sample' if args.sample else 'sec'}-{ticker.lower()}-{uuid.uuid4().hex[:12]}"
    output = args.output or ROOT / "runs" / ticker / args.engine / run_id
    if args.sample:
        output.mkdir(parents=True, exist_ok=True)
        if any(output.iterdir()):
            parser.error(f"Output directory is not empty: {output}")
        for source in (ROOT / "examples" / "sample-rklb").glob("*.json"):
            shutil.copy2(source, output / source.name)
        meta_path = output / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta.update(run_id=run_id, engine=args.engine, generated_at=datetime.now(timezone.utc).isoformat())
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for filename in ("metrics.json", "decision.json"):
            path = output / filename
            data = json.loads(path.read_text(encoding="utf-8"))
            data["run_id"] = run_id
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        try:
            write_real_run(output, args.engine)
        except (OSError, ValueError, RuntimeError) as exc:
            parser.error(str(exc))
    errors = validate_bundle(output)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.site_data:
        destination = ROOT / "site" / "data" / "companies" / ticker / args.engine
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("meta.json", "metrics.json", "sources.json", "decision.json", "report.md"):
            source = output / name
            if source.exists():
                shutil.copy2(source, destination / name)
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
