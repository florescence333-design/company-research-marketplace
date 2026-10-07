import sys
import unittest
import io
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from s0 import TICKERS_URL, _get_json, assess, load_s0


def filing_rows(forms, years):
    return [{"form": form, "reportDate": f"{year}-12-31", "filingDate": f"{year + 1}-02-01"}
            for form, year in zip(forms, years)]


def submission(sic="3760", forms=None, years=None, former=None):
    forms = forms if forms is not None else ["10-K"] * 5 + ["10-Q"]
    years = years if years is not None else [2025, 2024, 2023, 2022, 2021, 2026]
    rows = filing_rows(forms, years)
    return {"sic": sic, "entityType": "operating", "tickers": ["RKLB"],
            "exchanges": ["Nasdaq"], "fiscalYearEnd": "1231", "formerNames": former or [],
            "filings": {"recent": {key: [row[key] for row in rows]
                                    for key in ("form", "reportDate", "filingDate")}, "files": []}}


LISTING = {"cik": 1819994, "ticker": "RKLB", "name": "Rocket Lab Corp", "exchange": "Nasdaq"}


class S0Tests(unittest.TestCase):
    def test_financial_sic_boundaries_and_missing(self):
        for sic in ("6000", "6021", "6211", "6331", "6798", "6799"):
            with self.subTest(sic=sic):
                result = assess("RKLB", LISTING, submission(sic=sic))
                self.assertFalse(result.eligible)
                self.assertEqual(result.reason, f"지원 범위 밖: 금융·보험·부동산(SIC {sic})")
        for sic in ("5999", "6800", "7389"):
            with self.subTest(sic=sic):
                self.assertTrue(assess("RKLB", LISTING, submission(sic=sic)).eligible)
        self.assertEqual(assess("RKLB", LISTING, submission(sic=None)).reason, "적합성 확인 실패: SIC 없음")

    def test_20f_rejected_and_spac_history_is_counted_after_merger(self):
        old = [{"name": "Vector Acquisition Corp", "to": "2021-08-30T00:00:00Z"}]
        self.assertTrue(assess("RKLB", LISTING, submission(former=old)).eligible)
        short = submission(forms=["10-K"] * 4 + ["10-Q"], years=[2024, 2023, 2022, 2020, 2025], former=old)
        self.assertIn("4개 미만", assess("RKLB", LISTING, short).reason)
        foreign = submission(forms=["20-F"] * 5, years=[2025, 2024, 2023, 2022, 2021])
        foreign["entityType"] = "other"
        self.assertIn("20-F", assess("RKLB", LISTING, foreign).reason)
        mixed = submission(forms=["20-F", "10-K", "10-K", "10-K", "10-K", "10-Q"],
                           years=[2025, 2024, 2023, 2022, 2021, 2026])
        self.assertIn("20-F", assess("RKLB", LISTING, mixed).reason)

    def test_uncertain_identity_or_history_stops(self):
        wrong = {**LISTING, "ticker": "VRT"}
        self.assertIn("적합성 확인 실패", assess("RKLB", wrong, submission()).reason)
        mismatched_exchange = submission()
        mismatched_exchange["exchanges"] = ["NYSE"]
        self.assertIn("적합성 확인 실패", assess("RKLB", LISTING, mismatched_exchange).reason)
        ambiguous = submission()
        ambiguous["filings"]["recent"]["reportDate"] = [""] * 6
        self.assertIn("적합성 확인 실패", assess("RKLB", LISTING, ambiguous).reason)

    def test_loader_fetches_only_ticker_and_submissions_metadata(self):
        urls = []
        ticker_map = {"fields": ["cik", "name", "ticker", "exchange"],
                      "data": [[1819994, "Rocket Lab Corp", "RKLB", "Nasdaq"]]}

        def get_json(url):
            urls.append(url)
            return ticker_map if url.endswith("company_tickers_exchange.json") else submission()

        self.assertTrue(load_s0("RKLB", get_json=get_json).eligible)
        self.assertEqual(len(urls), 2)
        self.assertTrue(all("companyfacts" not in url and "Archives" not in url for url in urls))
        self.assertEqual(load_s0("BAD", get_json=get_json).reason, "적합성 확인 실패: 티커 식별 불가")

    def test_loader_uses_older_submissions_metadata_for_four_years(self):
        ticker_map = {"fields": ["cik", "name", "ticker", "exchange"],
                      "data": [[1819994, "Rocket Lab Corp", "RKLB", "Nasdaq"]]}
        recent = submission(forms=["10-K", "10-K", "10-Q"], years=[2025, 2024, 2026])
        recent["filings"]["files"] = [{"name": "CIK0001819994-submissions-001.json"}]
        old = submission(forms=["10-K", "10-K"], years=[2023, 2022])["filings"]["recent"]
        urls = []

        def get_json(url):
            urls.append(url)
            if url.endswith("company_tickers_exchange.json"):
                return ticker_map
            if url.endswith("CIK0001819994.json"):
                return recent
            return old

        result = load_s0("RKLB", get_json=get_json)
        self.assertTrue(result.eligible)
        self.assertEqual(result.fiscal_years, (2022, 2023, 2024, 2025))
        self.assertEqual(len(urls), 3)

    def test_loader_network_failure_fails_closed(self):
        def fail(_url):
            raise TimeoutError("offline")

        self.assertEqual(load_s0("RKLB", get_json=fail).reason, "적합성 확인 실패: SEC 메타데이터 조회 실패")

    def test_http_fetch_does_not_request_compressed_body_without_decoder(self):
        captured = []

        def urlopen(request, timeout):
            captured.append(request)
            return io.BytesIO(json.dumps({"data": []}).encode())

        with patch("s0.sec_user_agent", return_value="test@example.com"), patch("s0.urllib.request.urlopen", urlopen):
            self.assertEqual(_get_json(TICKERS_URL), {"data": []})
        self.assertNotIn("Accept-encoding", captured[0].headers)


if __name__ == "__main__":
    unittest.main()
