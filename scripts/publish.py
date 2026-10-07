"""Validate a completed company run and atomically select it for the local site build."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from company import ROOT, verify_resume
from market_snapshot import refresh_market_snapshot
from validate_bundle import validate_bundle
from verify_sec_run import verify_run


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_ticker(ticker):
    if not isinstance(ticker, str) or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker.upper()):
        raise ValueError("안전하지 않은 티커")
    return ticker.upper()


def safe_engine(engine):
    if engine not in ("gpt", "claude"):
        raise ValueError("지원하지 않는 엔진")
    return engine


def safe_run_id(run_id):
    if not isinstance(run_id, str) or run_id in (".", "..") or not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
        raise ValueError("안전하지 않은 실행 ID")
    return run_id


def select_bundle(ticker, engine, run_id=None):
    ticker, engine = safe_ticker(ticker), safe_engine(engine)
    base = ROOT / "runs" / ticker / engine
    if run_id:
        folder = base / safe_run_id(run_id)
        if not folder.is_dir():
            raise ValueError("지정 실행 없음")
        if not folder.resolve().is_relative_to(base.resolve()):
            raise ValueError("실행 경로가 해당 기업 밖임")
        return folder
    candidates = []
    if base.exists():
        for folder in base.iterdir():
            try:
                if not folder.resolve().is_relative_to(base.resolve()):
                    continue
                meta = _json(folder / "meta.json")
                if meta.get("ticker") == ticker and meta.get("engine") == engine and not meta["sample"] and not (folder / "review-only.json").exists():
                    candidates.append((datetime.fromisoformat(meta["generated_at"]), folder))
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
    if not candidates:
        raise ValueError("게시 가능한 실제 실행 없음")
    candidates.sort(key=lambda item: item[0], reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise ValueError("최신 생성 시각 동률: --run-id 지정 필요")
    return candidates[0][1]


def check_bundle(folder, expected_ticker=None, expected_engine=None):
    errors = validate_bundle(folder)
    meta = _json(folder / "meta.json")
    ticker, engine = safe_ticker(meta.get("ticker")), safe_engine(meta.get("engine"))
    safe_run_id(meta.get("run_id"))
    if meta.get("ticker") != ticker:
        errors.append("묶음 티커는 대문자 정규형이어야 함")
    if expected_ticker is not None and ticker != safe_ticker(expected_ticker):
        errors.append("선택 경로와 묶음 티커 불일치")
    if expected_engine is not None and engine != safe_engine(expected_engine):
        errors.append("선택 경로와 묶음 엔진 불일치")
    if meta["sample"]:
        errors.append("합성 샘플 게시 금지")
    if (folder / "review-only.json").exists():
        errors.append("일부 섹션 검토본은 전체 보고서로 게시할 수 없음")
    if (folder / "analysis-progress.json").exists() and meta.get("model") is None:
        errors.append("섹션 묶음 작성 중인 보고서는 완료본으로 게시할 수 없음")
    try:
        verify_resume(folder, meta["ticker"], meta["engine"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        errors.append(f"실행 상태 확인 실패: {exc}")
    if ticker != "RKLB" and "sec_filings" not in meta:
        errors.append("기업별 SEC 원본 정보 없음")
    else:
        raw_path = (ROOT / "data" / "sec" / ticker / "companyfacts.json") if "sec_filings" in meta else (ROOT / "data" / "sec" / "rklb-companyfacts.json")
        errors.extend(verify_run(folder, raw_path))
    if errors:
        raise ValueError("; ".join(errors))
    validation = {"schema_version": "v1-draft", "run_id": meta["run_id"],
                  "data_snapshot_id": meta["data_snapshot_id"],
                  "checked_at": datetime.now(timezone.utc).isoformat(), "status": "passed",
                  "checks": ["schema", "references", "run_hashes", "sec_recalculation", "report_sections", "diagram_if_present"],
                  "report_sha256": hashlib.sha256((folder / "report.md").read_bytes()).hexdigest()}
    _write_json(folder / "validation.json", validation)
    run = _json(folder / "run.json")
    for step in run["steps"]:
        if step["step_id"] == "S6":
            step.update(state="completed", reason="로컬 게시 전 구조·원본 재계산·해시 검증 통과",
                        input_sha256=validation["report_sha256"],
                        output_sha256=hashlib.sha256((folder / "validation.json").read_bytes()).hexdigest())
    _write_json(folder / "run.json", run)
    post_errors = validate_bundle(folder)
    if post_errors:
        raise ValueError("; ".join(post_errors))
    return validation


def activate_local(folder: Path, site_root: Path, build_callback):
    """Change a tiny pointer for the build; restore it if build/test fails."""
    meta = _json(folder / "meta.json")
    ticker, engine = safe_ticker(meta.get("ticker")), safe_engine(meta.get("engine"))
    if meta.get("ticker") != ticker:
        raise ValueError("묶음 티커는 대문자 정규형이어야 함")
    run_id = safe_run_id(meta.get("run_id"))
    report_hash = hashlib.sha256((folder / "report.md").read_bytes()).hexdigest()
    diagram_path = folder / "diagrams" / "manifest.json"
    diagram_hash = hashlib.sha256(diagram_path.read_bytes()).hexdigest() if diagram_path.exists() else "no-viz"
    version_id = f"{run_id}-{hashlib.sha256((report_hash + diagram_hash).encode()).hexdigest()[:10]}"
    site_root = site_root.resolve()
    engine_root = (site_root / "data" / "companies" / ticker / engine).resolve()
    if not engine_root.is_relative_to(site_root):
        raise ValueError("게시 대상이 사이트 경로 밖임")
    engine_root.mkdir(parents=True, exist_ok=True)
    pointer_path = engine_root / "current.json"
    previous = pointer_path.read_bytes() if pointer_path.exists() else None
    if previous:
        prior = json.loads(previous)
        if datetime.fromisoformat(prior["analysis_as_of"]) > datetime.fromisoformat(meta["analysis_as_of"]):
            raise ValueError("오래된 분석이 최신 게시본을 교체할 수 없음")
    lock = engine_root / ".publish-lock"
    lock.mkdir()
    try:
        versions = engine_root / "versions"
        versions.mkdir(exist_ok=True)
        version = versions / version_id
        if not version.exists():
            staging = versions / f".staging-{uuid.uuid4().hex}"
            shutil.copytree(folder, staging)
            os.replace(staging, version)
        pointer = {"run_id": run_id, "version_id": version_id, "analysis_as_of": meta["analysis_as_of"],
                   "data_snapshot_id": meta["data_snapshot_id"],
                   "selected_at": datetime.now(timezone.utc).isoformat()}
        temporary = engine_root / f".current-{uuid.uuid4().hex}.json"
        _write_json(temporary, pointer)
        os.replace(temporary, pointer_path)
        try:
            build_callback()
        except Exception:
            if previous is None:
                pointer_path.unlink(missing_ok=True)
            else:
                restore = engine_root / f".restore-{uuid.uuid4().hex}.json"
                restore.write_bytes(previous)
                os.replace(restore, pointer_path)
            raise
        return version
    finally:
        lock.rmdir()


def build_site(ticker):
    print(refresh_market_snapshot(ticker))
    subprocess.run(["npm.cmd", "run", "build", "--prefix", "site"], cwd=ROOT, check=True)
    subprocess.run(["npm.cmd", "test", "--prefix", "site"], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    parser.add_argument("--engine", required=True, choices=("gpt", "claude"))
    parser.add_argument("--run-id")
    args = parser.parse_args()
    try:
        args.ticker = safe_ticker(args.ticker)
        folder = select_bundle(args.ticker, args.engine, args.run_id)
        check_bundle(folder, args.ticker, args.engine)
        version = activate_local(folder, ROOT / "site", lambda: build_site(args.ticker))
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"로컬 게시 실패: {exc}", file=sys.stderr)
        return 1
    print(f"로컬 게시 준비 완료: {version}")
    print("원격 GitHub·Cloudflare 배포는 아직 확인되지 않음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
