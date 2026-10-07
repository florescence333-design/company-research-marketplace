"""Prepare an isolated private-site checkout from tracked site code and selected runs."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_id(value):
    return isinstance(value, str) and value not in (".", "..") and bool(re.fullmatch(r"[A-Za-z0-9._-]+", value))


def _tree_hashes(folder):
    result = {}
    for path in folder.rglob("*"):
        if path.is_symlink():
            raise ValueError("게시 버전에 외부 경로 연결이 있음")
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def export_selected_versions(source_companies: Path, destination: Path, display_allowed=False, include_drafts=False):
    """Copy validated selections; optionally include code drafts for a dev preview."""
    copied = []
    if not source_companies.exists():
        return copied
    if source_companies.is_symlink():
        raise ValueError("기업 데이터 루트에 외부 경로 연결이 있음")
    source_companies = source_companies.resolve()
    destination = destination.resolve()
    for company in sorted(source_companies.iterdir()):
        if not company.is_dir():
            continue
        ticker = company.name
        if company.is_symlink() or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker):
            raise ValueError("안전하지 않은 기업 데이터 경로")
        exported = False
        for engine in ("gpt", "claude"):
            source_root = company / engine
            pointer_path = source_root / "current.json"
            if not pointer_path.exists():
                continue
            if source_root.is_symlink() or pointer_path.is_symlink():
                raise ValueError("게시 포인터에 외부 경로 연결이 있음")
            pointer = _json(pointer_path)
            version_id = pointer.get("version_id") or pointer.get("run_id")
            if not _safe_id(version_id) or not _safe_id(pointer.get("run_id")):
                raise ValueError("게시 포인터의 실행·버전 ID가 안전하지 않음")
            version = source_root / "versions" / version_id
            if version.is_symlink() or not version.is_dir() or not version.resolve().is_relative_to(source_companies):
                raise ValueError("선택 버전 경로가 해당 기업 밖이거나 없음")
            meta = _json(version / "meta.json")
            if meta.get("sample") or (meta.get("model") is None and not include_drafts):
                # Synthetic examples never export; drafts require an explicit dev-only request.
                continue
            if meta.get("ticker") != ticker or meta.get("engine") != engine or meta.get("run_id") != pointer.get("run_id"):
                raise ValueError("선택 포인터와 기업·엔진·실행 메타데이터 불일치")
            validation = _json(version / "validation.json")
            if validation.get("status") != "passed" or validation.get("run_id") != pointer.get("run_id"):
                raise ValueError("검증되지 않은 사이트 결과")
            snapshot = pointer.get("data_snapshot_id")
            if snapshot and (meta.get("data_snapshot_id") != snapshot or validation.get("data_snapshot_id") != snapshot):
                raise ValueError("선택 포인터와 SEC 스냅샷 불일치")
            report_hash = hashlib.sha256((version / "report.md").read_bytes()).hexdigest()
            if validation.get("report_sha256") != report_hash:
                raise ValueError("게시 보고서 해시 불일치")
            source_hashes = _tree_hashes(version)
            target_root = destination / "data" / "companies" / ticker / engine
            target_version = target_root / "versions" / version_id
            if not target_version.parent.resolve().is_relative_to(destination):
                raise ValueError("내보내기 대상이 사이트 경로 밖임")
            if target_version.is_symlink() or (target_root / "current.json").is_symlink():
                raise ValueError("기존 사이트 선택본에 외부 경로 연결이 있음")
            if target_version.exists():
                if _tree_hashes(target_version) != source_hashes:
                    raise ValueError("같은 버전 ID의 기존 사이트 자료가 다름")
            else:
                shutil.copytree(version, target_version)
            target_root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pointer_path, target_root / "current.json")
            copied.append(str((target_root / "current.json").relative_to(destination)))
            exported = True
        market_source = company / "market-snapshot.json"
        market_target = destination / "data" / "companies" / ticker / "market-snapshot.json"
        if market_target.is_symlink() or not market_target.parent.resolve().is_relative_to(destination):
            raise ValueError("기존 시장 스냅샷에 외부 경로 연결이 있음")
        if display_allowed and exported and market_source.exists():
            if market_source.is_symlink():
                raise ValueError("시장 스냅샷에 외부 경로 연결이 있음")
            market = _json(market_source)
            allowed = {"ticker", "source", "as_of", "price", "market_cap", "pe_ttm", "range_52w", "fetched_at"}
            if set(market) - allowed or market.get("source") != "Twelve Data" or market.get("ticker") != ticker:
                raise ValueError("시장 스냅샷 필드·출처·기업 불일치")
            market_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(market_source, market_target)
            copied.append(str(market_target.relative_to(destination)))
        else:
            market_target.unlink(missing_ok=True)
    legacy_market = destination / "data" / "market-snapshot.json"
    if legacy_market.is_symlink():
        raise ValueError("기존 시장 스냅샷에 외부 경로 연결이 있음")
    legacy_market.unlink(missing_ok=True)
    return copied


def prune_stale_company_routes(destination: Path, copied_site_paths):
    """Remove obsolete fixed ticker routes after switching to [ticker].astro."""
    destination = destination.resolve()
    route_dir = destination / "src" / "pages" / "company"
    if not route_dir.is_dir():
        return
    for route in route_dir.glob("*.astro"):
        relative = route.relative_to(destination).as_posix()
        if relative in copied_site_paths or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}\.astro", route.name):
            continue
        if route.is_symlink() or not route.resolve().is_relative_to(destination):
            raise ValueError("오래된 기업 경로가 사이트 밖을 가리킴")
        route.unlink()


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
        if target.is_symlink() or not target.parent.resolve().is_relative_to(destination):
            raise ValueError("사이트 코드 내보내기 경로가 대상 밖임")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(str(target.relative_to(destination)))
    prune_stale_company_routes(destination, set(copied))
    copied.extend(export_selected_versions(ROOT / "site" / "data" / "companies", destination,
                                           display_allowed=os.environ.get("TWELVE_DATA_DISPLAY_ALLOWED") == "1"))
    (destination / ".gitignore").write_text("node_modules/\ndist/\n.astro/\n.wrangler/\n.uv-cache/\n.dev.vars\n.dev.vars.*\n.env\n.env.*\npublic/build-info.json\n", encoding="utf-8")
    (destination / "README.md").write_text("# Private Company Research Site\n\nThis checkout contains the password-protected Astro Pages site and selected SEC-sourced company data. Keep the GitHub repository private. Build: `npm ci && npm run build`; Cloudflare Pages output: `dist`. Configure AUTH_PASSWORD, SESSION_SECRET, and SESSION_VERSION in production and preview environments. See the public plugin repository's docs/DEPLOYMENT.md for validation steps.\n", encoding="utf-8")
    return copied


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "deploy" / "site-repo")
    args = parser.parse_args()
    copied = export_site(args.destination)
    print(f"준비된 사이트 코드 {len(copied)}개 파일; 대상: {args.destination}")
