import sys
import unittest

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from market_snapshot import normalize_provider_data


class MarketSnapshotTests(unittest.TestCase):
    def test_extracts_only_expected_quote_and_statistics_fields(self):
        quote = {"symbol": "RKLB", "currency": "USD", "datetime": "2026-10-06", "close": "42.10",
                 "fifty_two_week": {"low": "19.30", "high": "53.20"}, "apikey": "must-not-copy"}
        stats = {"statistics": {"valuations_metrics": {"market_capitalization": 1000000000,
                                                        "trailing_pe": -30}}, "apikey": "must-not-copy"}
        result = normalize_provider_data(quote, stats)
        self.assertEqual(result["price"], 42.1)
        self.assertEqual(result["range_52w"], {"low": 19.3, "high": 53.2})
        self.assertEqual(result["market_cap"], 1000000000)
        self.assertIsNone(result["pe_ttm"])
        self.assertNotIn("apikey", str(result))

    def test_missing_plan_fields_remain_null(self):
        result = normalize_provider_data({"status": "error", "message": "plan unavailable"}, None)
        self.assertIsNone(result["price"])
        self.assertIsNone(result["market_cap"])


if __name__ == "__main__":
    unittest.main()
