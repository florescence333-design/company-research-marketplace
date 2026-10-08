import json
import copy
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from report import build_report_items, recalculate_statuses, render_report, validate_report_items
from sec import build_sec_bundle


class ReportTests(unittest.TestCase):
    def test_status_is_derived_from_evidence_content_and_validation(self):
        report = {"sections": [
            {"section_id": "S01", "status": "complete", "body": "[해석] 사실. 반대 논거: 반례.", "source_ids": ["sec-001"]},
            {"section_id": "S02", "status": "complete", "body": "본문만", "source_ids": ["sec-001"]},
            {"section_id": "S03", "status": "complete", "body": "[해석] 사실. 반대 논거: 반례.", "source_ids": []},
        ]}
        recalculate_statuses(report)
        self.assertEqual([s["status"] for s in report["sections"]], ["partial", "partial", "unavailable"])
        recalculate_statuses(report, verified_ids={"S01", "S02", "S03"})
        self.assertEqual([s["status"] for s in report["sections"]], ["complete", "partial", "unavailable"])

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

    def test_ai_title_requires_recorded_model_and_every_section_complete(self):
        bundle = copy.deepcopy(self.bundle)
        report = build_report_items(bundle)
        for section in report["sections"]:
            section["status"] = "complete"
        report["sections"][0]["subsections"] = [{"section_id": "S01-A", "title": "추가 분석",
                                                   "status": "complete", "body": "본문", "source_ids": []}]
        bundle["meta"]["model"] = "codex"
        self.assertTrue(render_report(report, bundle).startswith("# RKLB 기업분석 — AI 분석 보고서\n"))
        self.assertIn("최종 판정: **판정 보류 (v0.1)**", render_report(report, bundle))

        report["sections"][0]["subsections"][0]["status"] = "partial"
        self.assertTrue(render_report(report, bundle).startswith("# RKLB 기업분석 — v0.1 부분 보고서\n"))
        report["sections"][0]["subsections"][0]["status"] = "complete"
        report["sections"][1]["status"] = "unavailable"
        self.assertTrue(render_report(report, bundle).startswith("# RKLB 기업분석 — v0.1 부분 보고서\n"))
        report["sections"][1]["status"] = "complete"
        bundle["meta"]["model"] = None
        self.assertTrue(render_report(report, bundle).startswith("# RKLB 기업분석 — v0.1 부분 보고서\n"))

    def test_generic_company_intro_uses_its_own_ticker_and_filing_year(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["meta"].update(ticker="AAPL", company_name="Apple Inc.", cik="0000320193")
        intro = build_report_items(bundle)["sections"][0]["body"]
        self.assertIn("Apple Inc. · 티커 AAPL · CIK 0000320193", intro)
        self.assertIn("2025년 10-K", intro)
        self.assertNotIn("RKLB", intro)

    def test_validator_rejects_missing_section_and_unknown_reference(self):
        report = build_report_items(self.bundle)
        report["sections"].pop()
        self.assertTrue(validate_report_items(report, self.bundle))
        report = build_report_items(self.bundle)
        report["sections"][0]["source_ids"] = ["made-up"]
        self.assertTrue(validate_report_items(report, self.bundle))

    def test_10k_facts_remain_traceable_in_relevant_sections(self):
        self.bundle["extracted-facts"] = {"facts": [
            {"fact_id": "backlog_fy2024", "value": 1_067_000_000, "unit": "USD", "source_id": "filing-a"},
            {"fact_id": "backlog_fy2025", "value": 1_847_300_000, "unit": "USD", "source_id": "filing-b"},
        ]}
        self.bundle["sources"]["sources"].extend([
            {"source_id": "filing-a"}, {"source_id": "filing-b"},
        ])
        report = build_report_items(self.bundle)
        section = report["sections"][8]
        self.assertEqual(section["section_id"], "S09")
        self.assertIn("1,847,300,000 USD", section["body"])
        self.assertEqual(section["fact_ids"], ["backlog_fy2024", "backlog_fy2025"])
        self.assertEqual(validate_report_items(report, self.bundle), [])
        report["sections"][8]["fact_ids"] = ["unverified-fact"]
        self.assertTrue(validate_report_items(report, self.bundle))

    def test_customer_concentration_is_labeled_approximate_and_sourced(self):
        self.bundle["extracted-facts"] = {"facts": [
            {"fact_id": "top5_revenue_share_approx_fy2025", "value": 49, "unit": "%", "source_id": "filing-a"},
            {"fact_id": "top5_backlog_share_approx_fy2025", "value": 77, "unit": "%", "source_id": "filing-b"},
        ]}
        self.bundle["sources"]["sources"].extend([{"source_id": "filing-a"}, {"source_id": "filing-b"}])
        report = build_report_items(self.bundle)
        customers = report["sections"][4]
        self.assertIn("매출의 약 49%", customers["body"])
        self.assertIn("수주잔고의 약 77%", customers["body"])
        self.assertEqual(customers["source_ids"], ["filing-a", "filing-b"])
        self.assertEqual(validate_report_items(report, self.bundle), [])

    def test_four_year_revenue_history_is_visible_as_three_growth_intervals_and_cagr(self):
        entries = [{"val": value, "start": f"{year}-01-01", "end": f"{year}-12-31",
                    "filed": f"{year + 1}-03-01", "form": "10-K", "accn": "0001819994-26-000001"}
                   for year, value in ((2022, 125), (2023, 150), (2024, 180), (2025, 216))]
        data = {"cik": 1819994, "entityName": "Rocket Lab USA, Inc.", "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": entries}}
        }}}
        bundle = build_sec_bundle(data, b"report growth", "gpt", datetime(2026, 10, 6, tzinfo=timezone.utc))
        report = build_report_items(bundle)
        section = report["sections"][1]
        self.assertIn("2023년 20.0%", section["body"])
        self.assertIn("2024년 20.0%", section["body"])
        self.assertIn("2025년 20.0%", section["body"])
        self.assertIn("3년 CAGR 20.0%", section["body"])
        self.assertEqual(validate_report_items(report, bundle), [])

    def test_report_labels_latest_standalone_quarter_and_prior_year(self):
        def fact(value, start, end, filed, form):
            return {"val": value, "start": start, "end": end, "filed": filed,
                    "form": form, "accn": "0001819994-26-000001"}
        data = {"cik": 1819994, "entityName": "Rocket Lab USA, Inc.", "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
                fact(300, "2025-01-01", "2025-12-31", "2026-03-01", "10-K"),
                fact(150, "2026-04-01", "2026-06-30", "2026-08-10", "10-Q"),
                fact(100, "2025-04-01", "2025-06-30", "2025-08-10", "10-Q"),
            ]}}
        }}}
        bundle = build_sec_bundle(data, b"report quarter", "gpt", datetime(2026, 10, 6, tzinfo=timezone.utc))
        report = build_report_items(bundle)
        section = report["sections"][1]
        self.assertIn("2026-04-01~2026-06-30 단독 분기 매출 150 USD", section["body"])
        self.assertIn("전년 같은 분기 대비 50.0%", section["body"])
        self.assertEqual(len([x for x in section["metric_ids"] if x.startswith("revenue_quarter")]), 3)
        self.assertEqual(validate_report_items(report, bundle), [])


if __name__ == "__main__":
    unittest.main()
