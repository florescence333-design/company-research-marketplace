"""Recalculate an RKLB SEC bundle against its cached raw Company Facts snapshot."""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from sec import build_sec_bundle
from validate_bundle import validate_bundle


ROOT = Path(__file__).resolve().parents[1]


def verify_run(folder: Path, raw_path: Path) -> list[str]:
    errors = validate_bundle(folder)
    if errors:
        return errors
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    if meta.get("sample"):
        return ["합성 샘플은 SEC 원본 대조 대상이 아님"]
    raw = raw_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if meta["data_snapshot_id"] != f"sec-companyfacts-{digest[:16]}":
        return ["원본 SEC 스냅샷 해시 불일치"]
    expected = build_sec_bundle(json.loads(raw), raw, meta["engine"], datetime.fromisoformat(meta["analysis_as_of"]))
    for name in ("metrics", "sources"):
        actual = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
        if name == "metrics":
            actual = actual["metrics"]
            expected_value = expected[name]["metrics"]
        else:
            actual = actual["sources"]
            expected_value = expected[name]["sources"]
        if actual != expected_value:
            errors.append(f"{name}.json: SEC 원본으로 재계산한 값과 불일치")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "sec" / "rklb-companyfacts.json")
    args = parser.parse_args()
    try:
        errors = verify_run(args.bundle, args.raw)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        errors = [f"검증 불가: {exc}"]
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print("SEC 원본 스냅샷 해시·출처·재무 수치 재계산 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
