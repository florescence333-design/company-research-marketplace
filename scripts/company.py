"""Run the small, reproducible company-analysis path (v0.1)."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from report import write_report
from template_stage import create_template_draft, validate_template
from sec import build_sec_bundle, fetch_10k, fetch_companyfacts
from s0 import load_s0
from validate_bundle import validate_bundle
from visualize_run import build_visualization, verify_visualization


ROOT = Path(__file__).resolve().parents[1]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_run_state(output: Path, no_viz: bool, original: bool) -> None:
    meta = json.loads((output / "meta.json").read_text(encoding="utf-8"))
    template_ready = not original and not validate_template(output)
    viz_ready = not no_viz and (output / "diagrams" / "manifest.json").exists()
    steps = [
        {"step_id": "S0", "state": "completed"},
        {"step_id": "S0.5", "state": "completed" if template_ready else "pending",
         "reason": "커스텀 템플릿 검증 완료" if template_ready else "웹 리서치 기반 커스텀 템플릿 작성 대기"},
        {"step_id": "S1", "state": "completed", "output_sha256": file_hash(output / "sources.json")},
        {"step_id": "S2", "state": "completed", "output_sha256": file_hash(output / "metrics.json")},
        {"step_id": "S3", "state": "completed" if (output / "extracted-facts.json").exists() and
         json.loads((output / "extracted-facts.json").read_text(encoding="utf-8"))["facts"] else "pending",
         "reason": "2025 10-K 일부 사업 사실만 추출; 나머지는 자료 확인 대기"},
        {"step_id": "S4", "state": "completed", "input_sha256": file_hash(output / "metrics.json"),
         "output_sha256": file_hash(output / "report.md"), "reason": "부분 보고서; 판정 보류 (v0.1)"},
        {"step_id": "S5", "state": "completed" if viz_ready else "pending",
         "reason": "보고서 기반 플라이휠·밸류체인 완료" if viz_ready else "AI 보고서 완료 후 생성 대기",
         **({"input_sha256": file_hash(output / "report.md"), "output_sha256": file_hash(output / "diagrams" / "manifest.json")} if viz_ready else {})},
        {"step_id": "S6", "state": "pending", "reason": "전체 게시 검증 전"},
        {"step_id": "S7", "state": "pending", "reason": "원격 게시 전"},
    ]
    run = {"run_id": meta["run_id"], "ticker": meta["ticker"], "engine": meta["engine"],
           "analysis_as_of": meta["analysis_as_of"], "data_snapshot_id": meta["data_snapshot_id"],
           "options": {"no_viz": no_viz, "original": original}, "steps": steps}
    (output / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify_resume(output: Path, ticker: str, engine: str) -> dict:
    meta = json.loads((output / "meta.json").read_text(encoding="utf-8"))
    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    if meta["ticker"] != ticker or meta["engine"] != engine or run["run_id"] != meta["run_id"]:
        raise ValueError("재개 대상의 티커·엔진·실행 ID 불일치")
    for step in run["steps"]:
        path = {"S1": "sources.json", "S2": "metrics.json", "S4": "report.md", "S5": "diagrams/manifest.json"}.get(step["step_id"])
        if step["step_id"] == "S5" and step.get("reason") == "검증된 매출 추이 도식만 생성":
            path = "diagrams/revenue.mmd"  # legacy run verification
        if step["state"] == "completed" and path and step.get("output_sha256") != file_hash(output / path):
            raise ValueError(f"{step['step_id']} 출력 해시 불일치; 새 실행 필요")
    return run


def find_recent_incomplete(ticker: str, engine: str, no_viz: bool, original: bool) -> list[Path]:
    base = ROOT / "runs" / ticker / engine
    candidates = []
    if not base.exists():
        return candidates
    now = datetime.now(timezone.utc)
    for folder in base.iterdir():
        path = folder / "run.json"
        if not path.is_file():
            continue
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
            age = now - datetime.fromisoformat(run["analysis_as_of"])
            if run["ticker"] == ticker and run["engine"] == engine and run.get("options") == {"no_viz": no_viz, "original": original} \
                    and timedelta(0) <= age <= timedelta(hours=24) and next((s for s in run["steps"] if s["step_id"] == "S7"), {}).get("state") != "completed":
                candidates.append(folder)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
    return candidates


def write_real_run(output: Path, engine: str) -> None:
    now = datetime.now(timezone.utc)
    cache = ROOT / "data" / "sec" / "rklb-companyfacts.json"
    data, raw = fetch_companyfacts(cache)
    try:
        business_raw = fetch_10k(ROOT / "data" / "sec" / "rklb-2025-10k.htm")
    except (OSError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        business_raw = None
        print(f"SEC 10-K 본문 수집 실패: {type(exc).__name__}; 관련 섹션 자료 확인 대기", file=sys.stderr)
    bundle = build_sec_bundle(data, raw, engine, now, business_raw)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"Output directory is not empty: {output}")
    for name, obj in bundle.items():
        (output / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(output)
    create_template_draft(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    parser.add_argument("--engine", choices=("claude", "gpt"), required=True)
    parser.add_argument("--sample", action="store_true", help="Copy visibly synthetic RKLB example")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--site-data", action="store_true", help="Compatibility alias; real runs publish locally by default")
    parser.add_argument("--no-viz", action="store_true")
    parser.add_argument("--viz-only", action="store_true")
    parser.add_argument("--original", action="store_true", help="Use the unmodified Master Template")
    parser.add_argument("--new", action="store_true", help="Force a new run")
    parser.add_argument("--run-id", help="Resume a named run for the same ticker and engine")
    args = parser.parse_args()
    if args.new and args.run_id or args.no_viz and args.viz_only or args.viz_only and args.original:
        parser.error("잘못된 옵션 조합: --new/--run-id, --no-viz/--viz-only, --viz-only/--original")
    if args.run_id and (not re.fullmatch(r"[A-Za-z0-9._-]+", args.run_id) or args.output):
        parser.error("--run-id는 안전한 실행 ID여야 하며 --output과 함께 사용할 수 없음")
    if args.site_data and (args.sample or args.output):
        parser.error("--site-data는 기본 실제 실행에서만 사용 가능")
    if args.viz_only and not args.run_id:
        parser.error("--viz-only는 --run-id로 기존 실행을 지정해야 함")
    ticker = args.ticker.upper()
    if args.sample:
        if ticker != "RKLB":
            parser.error("합성 예시는 현재 RKLB만 지원")
    else:
        eligibility = load_s0(ticker)
        if not eligibility.eligible:
            parser.error(eligibility.reason)
        if ticker != "RKLB":
            parser.error(f"{ticker}: S0 통과; SEC 수집기 일반화는 4단계에서 연결")
    if not args.run_id and not args.new and not args.sample and not args.output:
        candidates = find_recent_incomplete(ticker, args.engine, args.no_viz, args.original)
        if len(candidates) > 1:
            parser.error("재개 가능한 실행이 여러 개임: --run-id로 지정하거나 --new 사용")
        if candidates:
            args.run_id = candidates[0].name
            print(f"기존 실행 재개: {args.run_id}", file=sys.stderr)
    run_id = args.run_id or f"{'sample' if args.sample else 'sec'}-{ticker.lower()}-{uuid.uuid4().hex[:12]}"
    output = args.output or ROOT / "runs" / ticker / args.engine / run_id
    if args.run_id:
        if not output.is_dir():
            parser.error(f"기존 실행 없음: {run_id}")
        try:
            run = verify_resume(output, ticker, args.engine)
            if args.viz_only:
                if (output / "diagrams" / "manifest.json").exists() and verify_visualization(output):
                    parser.error("도식 기준 보고서가 변경되어 재생성 중단")
                build_visualization(output)
                write_run_state(output, False, run["options"].get("original", False))
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
    elif args.sample:
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
            write_run_state(output, args.no_viz, args.original)
        except (OSError, ValueError, RuntimeError) as exc:
            parser.error(str(exc))
    errors = validate_bundle(output)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if not args.sample and args.output is None:
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "publish.py"), ticker,
                                 "--engine", args.engine, "--run-id", output.name], cwd=ROOT)
        if result.returncode:
            return result.returncode
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
