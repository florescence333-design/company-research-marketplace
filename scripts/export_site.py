"""Prepare an isolated private-site checkout from tracked site code and selected runs."""

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def export_site(destination: Path):
    destination = destination.resolve()
    if not destination.is_relative_to((ROOT / "deploy").resolve()):
        raise ValueError("배포 체크아웃은 프로젝트 deploy/ 안에 두어야 함")
    destination.mkdir(parents=True, exist_ok=True)
    tracked = subprocess.check_output(["git", "-c", f"safe.directory={ROOT}", "ls-files", "-z", "--", "site"], cwd=ROOT).decode("utf-8").split("\0")
    copied = []
    for relative in filter(None, tracked):
        source = ROOT / relative
        if not source.is_file():
            continue
        target = destination / Path(relative).relative_to("site")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(str(target.relative_to(destination)))
    for engine in ("gpt", "claude"):
        source_root = ROOT / "site" / "data" / "companies" / "RKLB" / engine
        pointer_path = source_root / "current.json"
        if not pointer_path.exists():
            continue
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        version_id = pointer.get("version_id") or pointer.get("run_id")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", version_id or ""):
            raise ValueError("게시 포인터의 버전 ID가 안전하지 않음")
        version = source_root / "versions" / version_id
        validation = json.loads((version / "validation.json").read_text(encoding="utf-8"))
        if validation.get("status") != "passed" or validation.get("run_id") != pointer.get("run_id"):
            raise ValueError("검증되지 않은 사이트 결과")
        target_root = destination / "data" / "companies" / "RKLB" / engine
        target_version = target_root / "versions" / version_id
        if not target_version.exists():
            shutil.copytree(version, target_version)
        target_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pointer_path, target_root / "current.json")
        copied.append(str((target_root / "current.json").relative_to(destination)))
    market_source = ROOT / "site" / "data" / "market-snapshot.json"
    market_target = destination / "data" / "market-snapshot.json"
    # The individual API tiers may not grant external display or redistribution rights.
    # Keep the private-site checkout free of provider prices until those rights are verified.
    if market_source.exists() and os.environ.get("TWELVE_DATA_DISPLAY_ALLOWED") == "1":
        market = json.loads(market_source.read_text(encoding="utf-8"))
        allowed = {"source", "as_of", "price", "market_cap", "pe_ttm", "range_52w", "fetched_at"}
        if set(market) - allowed or market.get("source") != "Twelve Data":
            raise ValueError("시장 스냅샷 필드·출처 검증 실패")
        market_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(market_source, market_target)
        copied.append(str(market_target.relative_to(destination)))
    else:
        market_target.unlink(missing_ok=True)
    (destination / ".gitignore").write_text("node_modules/\ndist/\n.astro/\n.wrangler/\n.uv-cache/\n.dev.vars\n.dev.vars.*\n.env\n.env.*\npublic/build-info.json\n", encoding="utf-8")
    (destination / "README.md").write_text("# Private Company Research Site\n\nThis checkout contains the password-protected Astro Pages site and selected SEC-sourced RKLB data. Keep the GitHub repository private. Build: `npm ci && npm run build`; Cloudflare Pages output: `dist`. Configure AUTH_PASSWORD, SESSION_SECRET, and SESSION_VERSION in production and preview environments. See the public plugin repository's docs/DEPLOYMENT.md for validation steps.\n", encoding="utf-8")
    return copied


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "deploy" / "site-repo")
    args = parser.parse_args()
    copied = export_site(args.destination)
    print(f"준비된 사이트 코드 {len(copied)}개 파일; 대상: {args.destination}")
