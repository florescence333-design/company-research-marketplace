import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from ai_report import finalize, validate_ai_changes
from company import write_run_state
from report import build_report_items, write_report
from sec import build_sec_bundle
from validate_bundle import validate_bundle


class AiReportTests(unittest.TestCase):
    def setUp(self):
        entry = {"val": 300, "start": "2025-01-01", "end": "2025-12-31",
                 "filed": "2026-03-01", "form": "10-K", "accn": "0001819994-26-000001"}
        data = {"cik": 1819994, "entityName": "Rocket Lab USA, Inc.", "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [entry]}}
        }}}
        self.bundle = build_sec_bundle(data, b"AI test", "claude", datetime(2026, 10, 6, tzinfo=timezone.utc))
        self.baseline = build_report_items(self.bundle)

    def test_accepts_three_sourced_ai_section_revisions(self):
        edited = copy.deepcopy(self.baseline)
        for index in (0, 1, 15):
            edited["sections"][index]["body"] += " 확인된 매출 수치에 대한 해석은 미래 성장을 보장하지 않는다."
            edited["sections"][index]["source_ids"] = ["sec-001"]
        self.assertEqual(validate_ai_changes(edited, self.bundle), [])

    def test_rejects_unchanged_or_unsourced_analysis(self):
        self.assertTrue(validate_ai_changes(self.baseline, self.bundle))
        edited = copy.deepcopy(self.baseline)
        for index in (0, 1, 15):
            edited["sections"][index]["body"] += " 추가 분석."
            edited["sections"][index]["source_ids"] = ["sec-001"]
        edited["sections"][1]["source_ids"] = []
        self.assertTrue(validate_ai_changes(edited, self.bundle))

    def test_rejects_changed_verdict(self):
        edited = copy.deepcopy(self.baseline)
        for index in (0, 1, 15):
            edited["sections"][index]["body"] += " 추가 분석."
            edited["sections"][index]["source_ids"] = ["sec-001"]
        edited["sections"][15]["body"] = "매수 검토"
        self.assertTrue(validate_ai_changes(edited, self.bundle))

    def test_finalized_report_has_model_and_detects_later_body_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            from pathlib import Path
            folder = Path(temp)
            for name, obj in self.bundle.items():
                (folder / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
            write_report(folder)
            write_run_state(folder, True, False)
            edited = json.loads((folder / "report-items.json").read_text(encoding="utf-8"))
            for index in (0, 1, 15):
                edited["sections"][index]["body"] += " SEC 매출 근거에 따른 추가 해석이다."
                edited["sections"][index]["source_ids"] = ["sec-001"]
            (folder / "report-items.json").write_text(json.dumps(edited, ensure_ascii=False), encoding="utf-8")
            finalize(folder, "claude-code")
            self.assertEqual(json.loads((folder / "meta.json").read_text(encoding="utf-8"))["model"], "claude-code")
            self.assertEqual(validate_bundle(folder), [])
            edited["sections"][0]["body"] = "나중에 변조한 내용"
            (folder / "report-items.json").write_text(json.dumps(edited, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(any("보고서 본문" in error for error in validate_bundle(folder)))


if __name__ == "__main__":
    unittest.main()
