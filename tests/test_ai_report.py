import copy
import hashlib
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
        excerpt = "A verified excerpt for a web research source."
        self.bundle["sources"]["sources"].append({
            "source_id": "web-test", "url": "https://www.faa.gov/space", "title": "FAA space",
            "accessed_at": "2026-10-06T00:00:00Z", "location": "Commercial Space Transportation",
            "excerpt": excerpt, "content_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        })
        self.baseline = build_report_items(self.bundle)

    def researched(self, edited, indices=(0, 1, 15)):
        for index in indices:
            section = edited["sections"][index]
            section["status"] = "partial"
            section["body"] += " [해석] 확인된 사실은 미래 성과를 보장하지 않는다. 반대 논거: 비교 자료가 부족하다."
            section["source_ids"] = ["sec-001", "web-test"]
            section["search_queries"] = ["Rocket Lab FAA licensed launches"]
            if index == 11:
                section["body"] = "| 지표 | 2024년 | 2025년 |\n| --- | ---: | ---: |\n| 매출 (USD) | 200 | 300 |\n\n[해석] 매출이 증가했다. 반대 논거: 이 표만으로 수익성은 모른다."

    def test_accepts_researched_ai_section_revisions(self):
        edited = copy.deepcopy(self.baseline)
        self.researched(edited, range(16))
        self.assertEqual(validate_ai_changes(edited, self.bundle), [])

    def test_rejects_unchanged_or_unsourced_analysis(self):
        self.assertTrue(validate_ai_changes(self.baseline, self.bundle))
        edited = copy.deepcopy(self.baseline)
        self.researched(edited)
        edited["sections"][1]["source_ids"] = []
        self.assertTrue(validate_ai_changes(edited, self.bundle))

    def test_rejects_changed_verdict(self):
        edited = copy.deepcopy(self.baseline)
        self.researched(edited)
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
            self.researched(edited, range(16))
            edited["sections"][0]["status"] = "unavailable"  # Model-supplied status must be ignored.
            (folder / "report-items.json").write_text(json.dumps(edited, ensure_ascii=False), encoding="utf-8")
            finalize(folder, "claude-code")
            finalized = json.loads((folder / "report-items.json").read_text(encoding="utf-8"))
            self.assertEqual({section["status"] for section in finalized["sections"]}, {"complete"})
            self.assertEqual(json.loads((folder / "meta.json").read_text(encoding="utf-8"))["model"], "claude-code")
            self.assertEqual(validate_bundle(folder), [])
            edited["sections"][0]["body"] = "나중에 변조한 내용"
            (folder / "report-items.json").write_text(json.dumps(edited, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(any("보고서 본문" in error for error in validate_bundle(folder)))

    def test_review_subset_requires_research_for_each_selected_section(self):
        edited = copy.deepcopy(self.baseline)
        self.researched(edited, (2, 9))
        self.assertEqual(validate_ai_changes(edited, self.bundle, ["S03", "S10"]), [])
        del edited["sections"][9]["search_queries"]
        self.assertTrue(any("S10: 웹 검색어" in error for error in validate_ai_changes(edited, self.bundle, ["S03", "S10"])))

    def test_review_subset_creates_publish_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            from pathlib import Path
            folder = Path(temp)
            for name, obj in self.bundle.items():
                (folder / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
            write_report(folder)
            write_run_state(folder, True, False)
            edited = json.loads((folder / "report-items.json").read_text(encoding="utf-8"))
            self.researched(edited, (2, 9))
            (folder / "report-items.json").write_text(json.dumps(edited, ensure_ascii=False), encoding="utf-8")
            finalize(folder, "codex", ["S03", "S10"])
            self.assertEqual(json.loads((folder / "review-only.json").read_text(encoding="utf-8")), {"sections": ["S03", "S10"]})

    def test_web_excerpt_hash_must_match(self):
        with tempfile.TemporaryDirectory() as temp:
            from pathlib import Path
            folder = Path(temp)
            for name, obj in self.bundle.items():
                (folder / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
            write_report(folder)
            self.assertEqual(validate_bundle(folder), [])
            sources = copy.deepcopy(self.bundle["sources"])
            sources["sources"][-1]["excerpt"] = "tampered"
            (folder / "sources.json").write_text(json.dumps(sources), encoding="utf-8")
            self.assertTrue(any("SHA-256" in error for error in validate_bundle(folder)))


if __name__ == "__main__":
    unittest.main()
