"""Recalculate a SEC bundle from its ticker-specific cached raw originals."""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from sec import build_sec_bundle, filing_cache_path
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
    data = json.loads(raw)
    if data.get("cik") != int(meta["cik"]):
        return ["SEC Company Facts CIK·묶음 티커 불일치"]
    filings = None
    business_raw = None
    if "sec_filings" in meta:
        if hashlib.sha256(raw).hexdigest() != meta.get("companyfacts_sha256"):
            return ["Company Facts 원본 해시 불일치"]
        expected_raw = ROOT / "data" / "sec" / meta["ticker"] / "companyfacts.json"
        if raw_path.resolve() != expected_raw.resolve():
            return ["회사별 Company Facts 캐시 경로 불일치"]
        filings = []
        if [item["form"] for item in meta["sec_filings"]] != ["10-K", "10-Q"]:
            return ["원본 공시 형식 불일치"]
        as_of = datetime.fromisoformat(meta["analysis_as_of"]).date().isoformat()
        for item in meta["sec_filings"]:
            expected_url = (f"https://www.sec.gov/Archives/edgar/data/{int(meta['cik'])}/"
                            f"{item['accession_number'].replace('-', '')}/{item['primary_document']}")
            if item["url"] != expected_url or item["filed"] > as_of or item["report_date"] > as_of:
                return ["원본 공시 주소·기준일 불일치"]
            filing_raw = filing_cache_path(ROOT, meta["ticker"], item).read_bytes()
            if hashlib.sha256(filing_raw).hexdigest() != item["sha256"]:
                return [f"{item['form']} 원본 해시 불일치"]
            filings.append({**item, "raw": filing_raw})
        business_raw = filings[0]["raw"]
        if meta.get("filing_sha256") != hashlib.sha256(business_raw).hexdigest():
            return ["10-K 원본 해시 불일치"]
        digest = hashlib.sha256(raw + b"".join(item["raw"] for item in filings)).hexdigest()
    else:
        if meta.get("filing_sha256"):
            business_raw = (ROOT / "data" / "sec" / "rklb-2025-10k.htm").read_bytes()
            if hashlib.sha256(business_raw).hexdigest() != meta["filing_sha256"]:
                return ["10-K 원본 해시 불일치"]
        digest = hashlib.sha256(raw + (business_raw or b"")).hexdigest()
    if meta["data_snapshot_id"] != f"sec-snapshot-{digest[:16]}":
        return ["원본 SEC 스냅샷 해시 불일치"]
    company = {key: meta[key] for key in ("ticker", "cik", "exchange", "security_type")} if filings else None
    expected = build_sec_bundle(data, raw, meta["engine"], datetime.fromisoformat(meta["analysis_as_of"]),
                                business_raw, company=company, filings=filings)
    if meta.get("filing_body_basis") != expected["meta"].get("filing_body_basis"):
        errors.append("meta.json: 정정 공시 본문 한계 고지 불일치")
    for name in ("metrics", "sources", "extracted-facts"):
        actual = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
        if name == "metrics":
            actual = actual["metrics"]
            expected_value = expected[name]["metrics"]
        elif name == "sources":
            # Web research extends the source catalog, but may never replace
            # or alter a source reconstructed from the SEC snapshot.
            actual = [source for source in actual["sources"] if source.get("source_id", "").startswith("sec-")]
            expected_value = expected[name]["sources"]
        else:
            fields = ("facts", "missing_categories", "limitations")
            actual = {key: actual[key] for key in fields if key in actual}
            expected_value = {key: expected[name][key] for key in fields if key in expected[name]}
        if actual != expected_value:
            errors.append(f"{name}.json: SEC 원본으로 재계산한 값과 불일치")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--raw", type=Path)
    args = parser.parse_args()
    try:
        meta = json.loads((args.bundle / "meta.json").read_text(encoding="utf-8"))
        default_raw = (ROOT / "data" / "sec" / meta["ticker"] / "companyfacts.json") if "sec_filings" in meta else (ROOT / "data" / "sec" / "rklb-companyfacts.json")
        errors = verify_run(args.bundle, args.raw or default_raw)
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
