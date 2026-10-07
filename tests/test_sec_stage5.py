"""Fiscal-period normalization for ticker-specific SEC bundles."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sec import build_sec_bundle
from report import build_report_items


def entry(value, start, end, form, filed, accn):
    return {"val": value, "start": start, "end": end, "form": form,
            "filed": filed, "accn": accn}


class Stage5PeriodTests(unittest.TestCase):
    def bundle(self, ticker, facts, annual_end, quarter_end, annual_accn, quarter_accn):
        cik = "0000789019" if ticker == "MSFT" else "0001674101"
        data = {"cik": int(cik), "entityName": ticker, "facts": {"us-gaap": facts}}
        filings = [{"form": form, "report_date": end, "filed": "2026-07-29",
                    "accession_number": accn, "primary_document": f"{ticker.lower()}.htm",
                    "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}/{ticker.lower()}.htm",
                    "raw": form.encode()}
                   for form, end, accn in (("10-K", annual_end, annual_accn),
                                           ("10-Q", quarter_end, quarter_accn))]
        result = build_sec_bundle(data, b"synthetic companyfacts", "gpt",
                                  datetime(2026, 10, 7, tzinfo=timezone.utc),
                                  company={"ticker": ticker, "cik": cik, "exchange": "NASDAQ",
                                           "security_type": "Common Stock"}, filings=filings)
        return ({m["metric_id"]: m for m in result["metrics"]["metrics"]},
                {s["source_id"]: s for s in result["sources"]["sources"]})

    def test_latest_10k_gives_derived_fourth_quarter_and_direct_annual_ttm(self):
        annual_accn = "0001193125-26-323660"
        q3_accn = "0001193125-26-191507"
        facts = {}
        for name, annual, nine in (("RevenueFromContractWithCustomerExcludingAssessedTax", 400, 280),
                                   ("OperatingIncomeLoss", 180, 120), ("NetIncomeLoss", 150, 110)):
            facts[name] = {"units": {"USD": [
                entry(annual, "2025-07-01", "2026-06-30", "10-K", "2026-07-29", annual_accn),
                entry(nine, "2025-07-01", "2026-03-31", "10-Q", "2026-04-29", q3_accn)]}}
        facts["EarningsPerShareDiluted"] = {"units": {"USD/shares": [
            entry(20, "2025-07-01", "2026-06-30", "10-K", "2026-07-29", annual_accn),
            entry(15, "2025-07-01", "2026-03-31", "10-Q", "2026-04-29", q3_accn)]}}
        metrics, sources = self.bundle("MSFT", facts, "2026-06-30", "2026-03-31", annual_accn, q3_accn)
        for name, expected, annual_value in (("revenue", 120, 400), ("operating_income", 60, 180),
                                             ("net_income", 40, 150)):
            latest = metrics[f"{name}_quarter_latest"]
            self.assertEqual(latest["value"], expected)
            self.assertEqual(latest["period_start"], "2026-04-01")
            self.assertEqual(latest["period_end"], "2026-06-30")
            self.assertEqual(latest["calculation"], "annual_minus_nine_months")
            self.assertEqual({sources[s]["accession_number"] for s in latest["source_ids"]},
                             {annual_accn, q3_accn})
            self.assertEqual(metrics[f"{name}_ttm"]["value"], annual_value)
            self.assertNotIn("calculation", metrics[f"{name}_ttm"])
        self.assertEqual(metrics["eps_annual"]["value"], 20)
        self.assertEqual(metrics["eps_ttm"]["value"], 20)
        self.assertEqual(metrics["eps_quarter_latest"]["status"], "unavailable")

    def test_latest_10q_uses_standalone_quarter_and_three_originals_for_ttm(self):
        annual_accn = "0001674101-26-000008"
        q2_accn = "0001628280-26-050609"
        prior_accn = "0001674101-25-000008"
        facts = {}
        for name, annual, current, current_ytd, prior_ytd in (
                ("RevenueFromContractWithCustomerExcludingAssessedTax", 1000, 300, 550, 450),
                ("OperatingIncomeLoss", 200, 70, 120, 90),
                ("NetIncomeLoss", 150, 55, 100, 80)):
            facts[name] = {"units": {"USD": [
                entry(annual, "2025-01-01", "2025-12-31", "10-K", "2026-02-13", annual_accn),
                entry(current, "2026-04-01", "2026-06-30", "10-Q", "2026-07-29", q2_accn),
                entry(current_ytd, "2026-01-01", "2026-06-30", "10-Q", "2026-07-29", q2_accn),
                entry(prior_ytd, "2025-01-01", "2025-06-30", "10-Q", "2025-07-30", prior_accn)]}}
        facts["EarningsPerShareDiluted"] = {"units": {"USD/shares": [
            entry(3.4, "2025-01-01", "2025-12-31", "10-K", "2026-02-13", annual_accn),
            entry(1.2, "2026-04-01", "2026-06-30", "10-Q", "2026-07-29", q2_accn)]}}
        metrics, sources = self.bundle("VRT", facts, "2025-12-31", "2026-06-30", annual_accn, q2_accn)
        for name, latest, ttm in (("revenue", 300, 1100), ("operating_income", 70, 230),
                                  ("net_income", 55, 170)):
            self.assertEqual(metrics[f"{name}_quarter_latest"]["value"], latest)
            self.assertNotIn("calculation", metrics[f"{name}_quarter_latest"])
            item = metrics[f"{name}_ttm"]
            self.assertEqual(item["value"], ttm)
            self.assertEqual(item["period_start"], "2025-07-01")
            self.assertEqual(item["period_end"], "2026-06-30")
            self.assertEqual(item["calculation"], "annual_plus_current_ytd_minus_prior_ytd")
            self.assertEqual({sources[s]["accession_number"] for s in item["source_ids"]},
                             {annual_accn, q2_accn, prior_accn})
        self.assertEqual(metrics["eps_quarter_latest"]["value"], 1.2)
        self.assertEqual(metrics["eps_ttm"]["status"], "unavailable")

    def test_missing_comparable_tag_or_unit_never_derives_value(self):
        annual_accn = "0001193125-26-323660"
        q3_accn = "0001193125-26-191507"
        facts = {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
                entry(400, "2025-07-01", "2026-06-30", "10-K", "2026-07-29", annual_accn)]}},
            "Revenues": {"units": {"USD": [
                entry(280, "2025-07-01", "2026-03-31", "10-Q", "2026-04-29", q3_accn)]}},
            "OperatingIncomeLoss": {"units": {"USD": [
                entry(180, "2025-07-01", "2026-06-30", "10-K", "2026-07-29", annual_accn)],
                "EUR": [entry(120, "2025-07-01", "2026-03-31", "10-Q", "2026-04-29", q3_accn)]}},
        }
        metrics, _ = self.bundle("MSFT", facts, "2026-06-30", "2026-03-31", annual_accn, q3_accn)
        self.assertEqual(metrics["revenue_quarter_latest"]["status"], "unavailable")
        self.assertEqual(metrics["operating_income_quarter_latest"]["status"], "unavailable")

    def test_report_labels_a_derived_latest_quarter(self):
        annual_accn = "0001193125-26-323660"
        q3_accn = "0001193125-26-191507"
        facts = {"RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            entry(400, "2025-07-01", "2026-06-30", "10-K", "2026-07-29", annual_accn),
            entry(280, "2025-07-01", "2026-03-31", "10-Q", "2026-04-29", q3_accn)]}}}
        cik = "0000789019"
        data = {"cik": int(cik), "entityName": "Microsoft", "facts": {"us-gaap": facts}}
        filings = [{"form": form, "report_date": end, "filed": "2026-07-29",
                    "accession_number": accn, "primary_document": "msft.htm",
                    "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}/msft.htm",
                    "raw": form.encode()}
                   for form, end, accn in (("10-K", "2026-06-30", annual_accn),
                                           ("10-Q", "2026-03-31", q3_accn))]
        bundle = build_sec_bundle(data, b"facts", "gpt", datetime(2026, 10, 7, tzinfo=timezone.utc),
                                  company={"ticker": "MSFT", "cik": cik, "exchange": "NASDAQ",
                                           "security_type": "Common Stock"}, filings=filings)
        report = build_report_items(bundle)
        growth = next(item for item in report["sections"] if item["section_id"] == "S02")
        self.assertIn("계산한 단독 분기", growth["body"])

    def test_disclosed_fourth_quarter_eps_is_used_without_arithmetic(self):
        annual_accn = "0001193125-26-323660"
        q3_accn = "0001193125-26-191507"
        facts = {"EarningsPerShareDiluted": {"units": {"USD/shares": [
            entry(17.95, "2025-07-01", "2026-06-30", "10-K", "2026-07-29", annual_accn),
            entry(4.81, "2026-04-01", "2026-06-30", "10-K", "2026-07-29", annual_accn),
            entry(13.14, "2025-07-01", "2026-03-31", "10-Q", "2026-04-29", q3_accn)]}}}
        metrics, sources = self.bundle("MSFT", facts, "2026-06-30", "2026-03-31", annual_accn, q3_accn)
        quarter = metrics["eps_quarter_latest"]
        self.assertEqual(quarter["value"], 4.81)
        self.assertNotIn("calculation", quarter)
        self.assertEqual(sources[quarter["source_ids"][0]]["accession_number"], annual_accn)

    def test_amended_10k_replaces_annual_and_fourth_quarter_basis(self):
        annual_accn = "0001193125-26-323660"
        amended_accn = "0001193125-26-333333"
        q3_accn = "0001193125-26-191507"
        facts = {"RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            entry(400, "2025-07-01", "2026-06-30", "10-K", "2026-07-29", annual_accn),
            entry(420, "2025-07-01", "2026-06-30", "10-K/A", "2026-08-15", amended_accn),
            entry(280, "2025-07-01", "2026-03-31", "10-Q", "2026-04-29", q3_accn)]}}}
        metrics, sources = self.bundle("MSFT", facts, "2026-06-30", "2026-03-31", annual_accn, q3_accn)
        self.assertEqual(metrics["revenue_fy2026"]["value"], 420)
        self.assertEqual(metrics["revenue_quarter_latest"]["value"], 140)
        self.assertEqual(metrics["revenue_ttm"]["value"], 420)
        self.assertIn(amended_accn, {sources[s]["accession_number"] for s in
                                     metrics["revenue_quarter_latest"]["source_ids"]})

    def test_amended_10q_replaces_standalone_and_cumulative_values(self):
        annual_accn = "0001674101-26-000008"
        q2_accn = "0001628280-26-050609"
        amended_accn = "0001628280-26-055555"
        prior_accn = "0001674101-25-000008"
        facts = {"RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            entry(1000, "2025-01-01", "2025-12-31", "10-K", "2026-02-13", annual_accn),
            entry(300, "2026-04-01", "2026-06-30", "10-Q", "2026-07-29", q2_accn),
            entry(550, "2026-01-01", "2026-06-30", "10-Q", "2026-07-29", q2_accn),
            entry(320, "2026-04-01", "2026-06-30", "10-Q/A", "2026-08-15", amended_accn),
            entry(570, "2026-01-01", "2026-06-30", "10-Q/A", "2026-08-15", amended_accn),
            entry(450, "2025-01-01", "2025-06-30", "10-Q", "2025-07-30", prior_accn)]}}}
        metrics, sources = self.bundle("VRT", facts, "2025-12-31", "2026-06-30", annual_accn, q2_accn)
        self.assertEqual(metrics["revenue_quarter_latest"]["value"], 320)
        self.assertEqual(metrics["revenue_ttm"]["value"], 1120)
        self.assertIn(amended_accn, {sources[s]["accession_number"] for s in metrics["revenue_ttm"]["source_ids"]})

    def test_conflicting_revenue_tags_suppress_dependent_ratios(self):
        annual_accn = "0001193125-26-323660"
        q3_accn = "0001193125-26-191507"
        facts = {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
                entry(400, "2025-07-01", "2026-06-30", "10-K", "2026-07-29", annual_accn),
                entry(300, "2024-07-01", "2025-06-30", "10-K", "2026-07-29", annual_accn)]}},
            "Revenues": {"units": {"USD": [
                entry(500, "2025-07-01", "2026-06-30", "10-K", "2026-07-29", annual_accn)]}},
            "OperatingIncomeLoss": {"units": {"USD": [
                entry(100, "2025-07-01", "2026-06-30", "10-K", "2026-07-29", annual_accn)]}},
        }
        metrics, _ = self.bundle("MSFT", facts, "2026-06-30", "2026-03-31", annual_accn, q3_accn)
        self.assertEqual(metrics["revenue_fy2026"]["status"], "unavailable")
        self.assertNotIn("operating_margin_fy2026", metrics)
        self.assertNotIn("revenue_growth_fy2026", metrics)


if __name__ == "__main__":
    unittest.main()
