import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from report import build_report_items, render_report, validate_report_items
from sec import build_sec_bundle


class ReportTests(unittest.TestCase):
    def setUp(self):
        def fact(value, start, end):
            return {"val": value, "start": start, "end": end, "filed": "2026-03-01", "form": "10-K", "accn": "0001819994-26-000001"}
        data = {"cik": 1819994, "entityName": "Rocket Lab USA, Inc.", "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
                fact(300, "2025-01-01", "2025-12-31"), fact(200, "2024-01-01", "2024-12-31"), fact(100, "2023-01-01", "2023-12-31")]}}
        }}}
        self.bundle = build_sec_bundle(data, b"test", "gpt", datetime(2026, 10, 6, tzinfo=timezone.utc))

    def test_report_keeps_exact_sixteen_template_sections_and_deferred_verdict(self):
        report = build_report_items(self.bundle)
        self.assertEqual(len(report["sections"]), 16)
        self.assertEqual(report["sections"][0]["section_id"], "S01")
        self.assertEqual(report["sections"][-1]["section_id"], "S16")
        self.assertEqual(validate_report_items(report, self.bundle), [])
        rendered = render_report(report, self.bundle)
        self.assertIn("판정 보류 (v0.1)", rendered)
        self.assertIn("50.0%", rendered)
        self.assertIn("자료 확인 대기", rendered)

    def test_validator_rejects_missing_section_and_unknown_reference(self):
        report = build_report_items(self.bundle)
        report["sections"].pop()
        self.assertTrue(validate_report_items(report, self.bundle))
        report = build_report_items(self.bundle)
        report["sections"][0]["source_ids"] = ["made-up"]
        self.assertTrue(validate_report_items(report, self.bundle))


if __name__ == "__main__":
    unittest.main()
