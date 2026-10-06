import unittest
from unittest.mock import patch
from datetime import datetime, timezone

from test_contract import ROOT
import sys

sys.path.insert(0, str(ROOT / "scripts"))
from sec import annual_facts, build_sec_bundle, quarterly_eps_ttm, sec_user_agent


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
