import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from market_snapshot import normalize_provider_data, refresh_market_snapshot


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

    def test_refresh_keeps_ticker_snapshots_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            calls = []
            def request(path, _key):
                calls.append(path)
                return {"datetime": "2026-10-07", "close": "12.5"} if path.startswith("/quote") else {}
            with patch("market_snapshot.user_api_key", return_value="test-key"), patch("market_snapshot._request", side_effect=request):
                refresh_market_snapshot("VRT", Path(temporary))
                refresh_market_snapshot("MSFT", Path(temporary))
            vrt = json.loads((Path(temporary) / "site/data/companies/VRT/market-snapshot.json").read_text(encoding="utf-8"))
            msft = json.loads((Path(temporary) / "site/data/companies/MSFT/market-snapshot.json").read_text(encoding="utf-8"))
            self.assertEqual(vrt["ticker"], "VRT")
            self.assertEqual(msft["ticker"], "MSFT")
            self.assertTrue(any("VRT" in path for path in calls))
            self.assertTrue(any("MSFT" in path for path in calls))

    def test_no_key_clears_only_the_requested_ticker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "site/data/companies"
            for ticker in ("VRT", "MSFT"):
                folder = root / ticker
                folder.mkdir(parents=True)
                (folder / "market-snapshot.json").write_text("{}", encoding="utf-8")
            with patch("market_snapshot.user_api_key", return_value=""):
                refresh_market_snapshot("VRT", Path(temporary))
            self.assertFalse((root / "VRT/market-snapshot.json").exists())
            self.assertTrue((root / "MSFT/market-snapshot.json").exists())

    def test_provider_symbol_mismatch_never_becomes_another_company_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            def request(path, _key):
                return {"symbol": "RKLB", "datetime": "2026-10-07", "close": "42"} if path.startswith("/quote") else {}
            with patch("market_snapshot.user_api_key", return_value="test-key"), patch("market_snapshot._request", side_effect=request):
                result = refresh_market_snapshot("VRT", Path(temporary))
            self.assertIn("확인 불가", result)
            self.assertFalse((Path(temporary) / "site/data/companies/VRT/market-snapshot.json").exists())


if __name__ == "__main__":
    unittest.main()
