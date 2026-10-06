import unittest
from unittest.mock import patch
from datetime import datetime, timezone

from test_contract import ROOT
import sys

sys.path.insert(0, str(ROOT / "scripts"))
from sec import annual_facts, build_sec_bundle, quarterly_eps_ttm, quarterly_facts, sec_user_agent


def fact(value, start, end, filed, form="10-K", accession="0001819994-26-000001"):
    return {"val": value, "start": start, "end": end, "filed": filed, "form": form, "accn": accession}


class SecSelectionTests(unittest.TestCase):
    def setUp(self):
        self.as_of = "2026-10-06"

    def test_annual_selection_ignores_future_and_short_periods(self):
        entries = [
            fact(100, "2025-01-01", "2025-12-31", "2026-03-01"),
            fact(999, "2025-01-01", "2025-12-31", "2026-11-01"),
            fact(20, "2025-10-01", "2025-12-31", "2026-03-01"),
            fact(80, "2024-01-01", "2024-12-31", "2025-03-01"),
        ]
        self.assertEqual([item["val"] for item in annual_facts(entries, self.as_of)], [100, 80])

    def test_quarter_selection_excludes_ytd_and_future_filing(self):
        entries = [
            fact(12, "2026-04-01", "2026-06-30", "2026-08-10", "10-Q"),
            fact(20, "2026-01-01", "2026-06-30", "2026-08-10", "10-Q"),
            fact(99, "2026-04-01", "2026-06-30", "2026-11-10", "10-Q"),
            fact(8, "2025-04-01", "2025-06-30", "2025-08-10", "10-Q"),
        ]
        self.assertEqual([item["val"] for item in quarterly_facts(entries, self.as_of)], [12, 8])

    def test_latest_quarter_revenue_uses_same_quarter_prior_year(self):
        revenue = [
            fact(150, "2026-04-01", "2026-06-30", "2026-08-10", "10-Q"),
            fact(100, "2025-04-01", "2025-06-30", "2025-08-10", "10-Q"),
            fact(270, "2026-01-01", "2026-06-30", "2026-08-10", "10-Q"),
        ]
        data = {"cik": 1819994, "entityName": "Rocket Lab USA, Inc.", "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": revenue}}
        }}}
        bundle = build_sec_bundle(data, b"quarter", "gpt", datetime(2026, 10, 6, tzinfo=timezone.utc))
        metrics = {item["metric_id"]: item for item in bundle["metrics"]["metrics"]}
        self.assertEqual(metrics["revenue_quarter_latest"]["value"], 150)
        self.assertEqual(metrics["revenue_quarter_latest"]["period_start"], "2026-04-01")
        self.assertEqual(metrics["revenue_quarter_prior_year"]["value"], 100)
        self.assertEqual(metrics["revenue_quarter_yoy"]["value"], 50.0)

    def test_sec_identity_reads_process_without_logging_it(self):
        with patch.dict("os.environ", {"SEC_USER_AGENT": "Research Plugin contact@example.com"}):
            self.assertEqual(sec_user_agent(), "Research Plugin contact@example.com")

    def test_ttm_eps_requires_four_independent_quarters(self):
        entries = [
            fact(-0.1, "2025-01-01", "2025-03-31", "2025-05-01", "10-Q"),
            fact(-0.2, "2025-04-01", "2025-06-30", "2025-08-01", "10-Q"),
            fact(-0.3, "2025-07-01", "2025-09-30", "2025-11-01", "10-Q"),
            fact(-0.4, "2025-10-01", "2025-12-31", "2026-03-01", "10-K"),
        ]
        self.assertEqual(quarterly_eps_ttm(entries, self.as_of), -1.0)
        self.assertIsNone(quarterly_eps_ttm(entries[:3], self.as_of))

    def test_three_growth_intervals_require_four_annual_revenue_values(self):
        annual = [fact(value, f"{year}-01-01", f"{year}-12-31", f"{year + 1}-03-01")
                  for year, value in ((2022, 125), (2023, 150), (2024, 180), (2025, 216))]
        data = {"cik": 1819994, "entityName": "Rocket Lab USA, Inc.", "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": annual}}
        }}}
        bundle = build_sec_bundle(data, b"four years", "gpt", datetime(2026, 10, 6, tzinfo=timezone.utc))
        metrics = {item["metric_id"]: item for item in bundle["metrics"]["metrics"]}
        self.assertIn("revenue_fy2022", metrics)
        self.assertEqual(metrics["revenue_fy2022"]["value"], 125)
        for year in (2023, 2024, 2025):
            self.assertAlmostEqual(metrics[f"revenue_growth_fy{year}"]["value"], 20.0)
        self.assertAlmostEqual(metrics["revenue_cagr_3y"]["value"], 20.0)

    def test_operating_margin_keeps_loss_sign_and_rejects_zero_revenue(self):
        income = fact(-40, "2025-01-01", "2025-12-31", "2026-03-01")
        revenue = fact(200, "2025-01-01", "2025-12-31", "2026-03-01")
        data = {"cik": 1819994, "entityName": "Rocket Lab USA, Inc.", "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [revenue]}},
            "OperatingIncomeLoss": {"units": {"USD": [income]}},
        }}}
        bundle = build_sec_bundle(data, b"margin", "gpt", datetime(2026, 10, 6, tzinfo=timezone.utc))
        metrics = {item["metric_id"]: item for item in bundle["metrics"]["metrics"]}
        self.assertIn("operating_margin_fy2025", metrics)
        self.assertEqual(metrics["operating_margin_fy2025"]["value"], -20.0)
        revenue["val"] = 0
        bundle = build_sec_bundle(data, b"zero revenue", "gpt", datetime(2026, 10, 6, tzinfo=timezone.utc))
        metrics = {item["metric_id"]: item for item in bundle["metrics"]["metrics"]}
        self.assertEqual(metrics["operating_margin_fy2025"]["status"], "unavailable")

    def test_capex_reduces_free_cash_flow_even_when_ocf_is_negative(self):
        data = {"cik": 1819994, "entityName": "Rocket Lab USA, Inc.", "facts": {"us-gaap": {
            "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [fact(-30, "2025-01-01", "2025-12-31", "2026-03-01")]}},
            "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [fact(10, "2025-01-01", "2025-12-31", "2026-03-01")]}},
        }}}
        bundle = build_sec_bundle(data, b"cash flow", "gpt", datetime(2026, 10, 6, tzinfo=timezone.utc))
        metrics = {item["metric_id"]: item for item in bundle["metrics"]["metrics"]}
        self.assertIn("capex_fy2025", metrics)
        self.assertEqual(metrics["capex_fy2025"]["value"], 10)
        self.assertEqual(metrics["free_cash_flow_fy2025"]["value"], -40)

    def test_liabilities_ratio_requires_positive_equity_same_date(self):
        liabilities = {"val": 80, "end": "2026-06-30", "filed": "2026-08-01", "form": "10-Q", "accn": "0001819994-26-000001"}
        equity = {"val": 40, "end": "2026-06-30", "filed": "2026-08-01", "form": "10-Q", "accn": "0001819994-26-000001"}
        data = {"cik": 1819994, "entityName": "Rocket Lab USA, Inc.", "facts": {"us-gaap": {
            "Liabilities": {"units": {"USD": [liabilities]}},
            "StockholdersEquity": {"units": {"USD": [equity]}},
        }}}
        bundle = build_sec_bundle(data, b"balance", "gpt", datetime(2026, 10, 6, tzinfo=timezone.utc))
        metrics = {item["metric_id"]: item for item in bundle["metrics"]["metrics"]}
        self.assertIn("liabilities_to_equity", metrics)
        self.assertEqual(metrics["liabilities_to_equity"]["value"], 200.0)
        equity["val"] = 0
        bundle = build_sec_bundle(data, b"zero equity", "gpt", datetime(2026, 10, 6, tzinfo=timezone.utc))
        metrics = {item["metric_id"]: item for item in bundle["metrics"]["metrics"]}
        self.assertEqual(metrics["liabilities_to_equity"]["status"], "unavailable")

    def test_bundle_has_real_source_and_fixed_deferred_verdict(self):
        data = {"cik": 1819994, "entityName": "Rocket Lab USA, Inc.", "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [fact(515000000, "2025-01-01", "2025-12-31", "2026-03-01")]}}
        }}}
        bundle = build_sec_bundle(data, b"sample raw data", "gpt", datetime(2026, 10, 6, tzinfo=timezone.utc))
        self.assertFalse(bundle["meta"]["sample"])
        self.assertEqual(bundle["meta"]["cik"], "0001819994")
        self.assertEqual(bundle["decision"]["verdict"], "판정 보류 (v0.1)")
        revenue = next(m for m in bundle["metrics"]["metrics"] if m["metric_id"] == "revenue_fy2025")
        self.assertEqual(revenue["value"], 515000000)
        self.assertEqual(revenue["source_ids"], ["sec-001"])
        self.assertIn("RevenueFromContractWithCustomerExcludingAssessedTax", bundle["sources"]["sources"][0]["location"])

    def test_eps_fallback_uses_annual_plus_current_ytd_minus_prior_ytd(self):
        annual = fact(-200, "2025-01-01", "2025-12-31", "2026-03-01")
        current = fact(-60, "2026-01-01", "2026-06-30", "2026-08-01", "10-Q")
        prior = fact(-100, "2025-01-01", "2025-06-30", "2025-08-01", "10-Q")
        shares = fact(600, "2026-04-01", "2026-06-30", "2026-08-01", "10-Q")
        data = {"cik": 1819994, "entityName": "Rocket Lab USA, Inc.", "facts": {"us-gaap": {
            "NetIncomeLoss": {"units": {"USD": [annual, current, prior]}},
            "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [shares]}},
        }}}
        bundle = build_sec_bundle(data, b"fallback", "gpt", datetime(2026, 10, 6, tzinfo=timezone.utc))
        eps = next(m for m in bundle["metrics"]["metrics"] if m["metric_id"] == "eps_ttm")
        self.assertEqual(eps["value"], (-200 - 60 + 100) / 600)
        self.assertTrue(eps["approximate"])
        self.assertEqual(len(eps["source_ids"]), 4)


if __name__ == "__main__":
    unittest.main()
