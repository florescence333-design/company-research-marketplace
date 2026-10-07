import json
import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sec import build_sec_bundle, fetch_companyfacts, filing_cache_path, select_filings, validate_us_gaap


def companyfacts(cik=1674101, basis="us-gaap"):
    return {"cik": cik, "entityName": "Vertiv Holdings Co", "facts": {basis: {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [{"val": 100}]}},
        "NetIncomeLoss": {"units": {"USD": [{"val": 10}]}},
    }}}


def submissions():
    rows = [
        ("10-K", "2025-12-31", "2026-02-12", "0001674101-26-000010", "vrt-20251231.htm"),
        ("10-Q", "2026-06-30", "2026-07-29", "0001674101-26-000020", "vrt-20260630.htm"),
        ("10-Q", "2026-09-30", "2026-11-01", "0001674101-26-000030", "future.htm"),
        ("20-F", "2026-06-30", "2026-07-29", "0001674101-26-000040", "wrong.htm"),
    ]
    keys = ("form", "reportDate", "filingDate", "accessionNumber", "primaryDocument")
    return {"cik": 1674101, "filings": {"recent": dict(zip(keys, zip(*rows)))}}


class Stage4SecTests(unittest.TestCase):
    def test_us_gaap_gate_rejects_missing_or_ifrs_only_core_facts(self):
        for data in ({"cik": 1674101, "facts": {}}, {"cik": 1674101, "facts": None},
                     companyfacts(basis="ifrs-full"),
                     {"cik": 1674101, "facts": {"us-gaap": {"Assets": {"units": {"USD": [{"val": 1}]}}},
                                                 "ifrs-full": companyfacts(basis="ifrs-full")["facts"]["ifrs-full"]}}):
            with self.subTest(data=data):
                with self.assertRaisesRegex(ValueError, "지원 범위 밖: US-GAAP 재무 확인 불가"):
                    validate_us_gaap(data)
        self.assertIsNone(validate_us_gaap(companyfacts()))

    def test_selects_latest_valid_10k_and_10q_before_as_of(self):
        selected = select_filings(submissions(), 1674101, "2026-10-07")
        self.assertEqual([item["form"] for item in selected], ["10-K", "10-Q"])
        self.assertEqual([item["filed"] for item in selected], ["2026-02-12", "2026-07-29"])
        self.assertTrue(all("/1674101/" in item["url"] for item in selected))
        self.assertFalse(any("future" in item["url"] or "wrong" in item["url"] for item in selected))

    def test_filing_selection_rejects_malformed_latest_document(self):
        data = submissions()
        data["filings"]["recent"]["primaryDocument"] = ("../other.htm", *data["filings"]["recent"]["primaryDocument"][1:])
        with self.assertRaisesRegex(ValueError, "주소 검증 실패"):
            select_filings(data, 1674101, "2026-10-07")

    def test_filing_selection_rejects_malformed_filing_date(self):
        data = submissions()
        data["filings"]["recent"]["filingDate"] = ("2026-00-00", *data["filings"]["recent"]["filingDate"][1:])
        with self.assertRaisesRegex(ValueError, "공시 날짜 검증 실패"):
            select_filings(data, 1674101, "2026-10-07")

    def test_stale_companyfacts_cache_is_refetched_and_wrong_cik_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "facts.json"
            cache.write_text(json.dumps(companyfacts()), encoding="utf-8")
            os.utime(cache, (1, 1))
            with patch("sec._download_sec", return_value=json.dumps(companyfacts()).encode()) as get:
                data, _raw = fetch_companyfacts(cache, 1674101, max_age_hours=24)
                self.assertEqual(data["cik"], 1674101)
                get.assert_called_once()
            cache.write_text(json.dumps(companyfacts(cik=789019)), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CIK 불일치"):
                fetch_companyfacts(cache, 1674101, max_age_hours=24)

    def test_generic_bundle_keeps_ticker_and_sec_url_separate(self):
        facts = companyfacts()
        raw = json.dumps(facts).encode()
        filings = [{**item, "raw": f"{item['form']} raw".encode()} for item in select_filings(submissions(), 1674101, "2026-10-07")]
        bundle = build_sec_bundle(facts, raw, "gpt", datetime(2026, 10, 7, tzinfo=timezone.utc),
                                  company={"ticker": "VRT", "cik": "0001674101", "exchange": "NYSE",
                                           "security_type": "대표 상장주식"}, filings=filings)
        self.assertEqual(bundle["meta"]["ticker"], "VRT")
        self.assertEqual(bundle["meta"]["cik"], "0001674101")
        self.assertEqual([f["form"] for f in bundle["meta"]["sec_filings"]], ["10-K", "10-Q"])
        self.assertTrue(all("0001674101" in source["url"] for source in bundle["sources"]["sources"]))

    def test_generic_recalculator_checks_company_and_filing_hashes(self):
        import verify_sec_run
        facts = companyfacts()
        raw = json.dumps(facts).encode()
        filings = [{**item, "raw": f"{item['form']} raw".encode()} for item in select_filings(submissions(), 1674101, "2026-10-07")]
        bundle = build_sec_bundle(facts, raw, "gpt", datetime(2026, 10, 7, tzinfo=timezone.utc),
                                  company={"ticker": "VRT", "cik": "0001674101", "exchange": "NYSE",
                                           "security_type": "대표 상장주식"}, filings=filings)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / "run"
            run.mkdir()
            for name, value in bundle.items():
                (run / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
            raw_path = root / "data/sec/VRT/companyfacts.json"
            raw_path.parent.mkdir(parents=True)
            raw_path.write_bytes(raw)
            for filing in filings:
                path = filing_cache_path(root, "VRT", filing)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(filing["raw"])
            with patch.object(verify_sec_run, "ROOT", root):
                self.assertEqual(verify_sec_run.verify_run(run, raw_path), [])
                raw_path.write_bytes(json.dumps(companyfacts(cik=789019)).encode())
                self.assertTrue(verify_sec_run.verify_run(run, raw_path))

    def test_ifrs_only_command_creates_no_run_and_never_publishes(self):
        import company
        from s0 import S0Result

        with tempfile.TemporaryDirectory() as temp:
            with patch.object(company, "ROOT", Path(temp)), patch.object(sys, "argv", ["company.py", "VRT", "--engine", "gpt"]), \
                 patch.object(company, "load_s0", return_value=S0Result("VRT", True, "S0 통과", "0001674101", "Vertiv", "NYSE")), \
                 patch.object(company, "fetch_companyfacts", return_value=(companyfacts(basis="ifrs-full"), b"ifrs")), \
                 patch.object(company, "fetch_filing") as filing_download, patch.object(company, "fetch_submissions") as submissions_fetch, \
                 patch.object(company.subprocess, "run") as publish:
                stderr = io.StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit):
                    company.main()
                self.assertIn("US-GAAP 재무 확인 불가", stderr.getvalue())
                filing_download.assert_not_called()
                submissions_fetch.assert_not_called()
                publish.assert_not_called()
                self.assertFalse((Path(temp) / "runs").exists())


if __name__ == "__main__":
    unittest.main()
