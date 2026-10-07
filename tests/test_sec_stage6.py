"""Company-specific filing-body facts and amendment disclosure."""

import hashlib
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sec import build_sec_bundle
from report import build_report_items, render_report


class Stage6BodyTests(unittest.TestCase):
    def bundle(self, amended=False):
        annual = "0001674101-26-000008"
        quarter = "0001628280-26-050609"
        amended_accn = "0001674101-26-000099"
        entries = [{"val": 100, "start": "2025-01-01", "end": "2025-12-31",
                    "filed": "2026-02-12", "form": "10-K", "accn": annual}]
        if amended:
            entries.append({"val": 110, "start": "2025-01-01", "end": "2025-12-31",
                            "filed": "2026-04-01", "form": "10-K/A", "accn": amended_accn})
        data = {"cik": 1674101, "entityName": "Vertiv Holdings Co", "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": entries}},
            "NetIncomeLoss": {"units": {"USD": entries}},
        }}}
        body = b"Vertiv Backlog Vertiv's estimated combined order backlog was $15.0 billion and $7.2 billion as of December 31, 2025 and 2024, respectively."
        filings = [{"form": form, "report_date": period, "filed": filed,
                    "accession_number": accn, "primary_document": "vrt.htm",
                    "url": f"https://www.sec.gov/Archives/edgar/data/1674101/{accn.replace('-', '')}/vrt.htm",
                    "raw": raw}
                   for form, period, filed, accn, raw in (
                       ("10-K", "2025-12-31", "2026-02-12", annual, body),
                       ("10-Q", "2026-06-30", "2026-07-29", quarter, b"Vertiv no verified notes"))]
        result = build_sec_bundle(data, b"companyfacts", "gpt", datetime(2026, 10, 7, tzinfo=timezone.utc),
                                  company={"ticker": "VRT", "cik": "0001674101", "exchange": "NYSE",
                                           "security_type": "Common Stock"}, filings=filings)
        return result, body, annual

    def test_verified_body_fact_has_original_url_hash_and_missing_categories(self):
        bundle, body, annual = self.bundle()
        fact = next(item for item in bundle["extracted-facts"]["facts"] if item["fact_id"] == "backlog_fy2025")
        source = next(item for item in bundle["sources"]["sources"] if item["source_id"] == fact["source_id"])
        self.assertEqual(fact["value"], 15_000_000_000)
        self.assertEqual(fact["category"], "business")
        self.assertEqual(source["accession_number"], annual)
        self.assertEqual(source["content_sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(source["url"], bundle["meta"]["sec_filings"][0]["url"])
        self.assertIn("customer", bundle["extracted-facts"]["missing_categories"])
        self.assertNotIn("filing_body_basis", bundle["meta"])

    def test_amended_numeric_source_discloses_original_body_limit(self):
        bundle, _body, _annual = self.bundle(amended=True)
        sentence = "수치는 정정본 기준, 본문 추출은 원본 10-K 기준"
        self.assertEqual(bundle["meta"]["filing_body_basis"], sentence)
        self.assertIn(sentence, bundle["extracted-facts"]["limitations"])
        self.assertIn(sentence, render_report(build_report_items(bundle), bundle))

    def test_company_without_body_rules_marks_every_category_missing(self):
        annual = "0000320193-25-000079"
        quarter = "0000320193-26-000020"
        data = {"cik": 320193, "entityName": "Apple Inc.", "facts": {"us-gaap": {}}}
        filings = [{"form": form, "report_date": period, "filed": "2026-07-31",
                    "accession_number": accession, "primary_document": "aapl.htm",
                    "url": f"https://www.sec.gov/Archives/edgar/data/320193/{accession.replace('-', '')}/aapl.htm",
                    "raw": b"Apple Inc. filing body"}
                   for form, period, accession in (("10-K", "2025-09-27", annual),
                                                   ("10-Q", "2026-06-27", quarter))]
        bundle = build_sec_bundle(data, b"aapl facts", "gpt", datetime(2026, 10, 7, tzinfo=timezone.utc),
                                  company={"ticker": "AAPL", "cik": "0000320193", "exchange": "NASDAQ",
                                           "security_type": "Common Stock"}, filings=filings)
        extracted = bundle["extracted-facts"]
        self.assertEqual(extracted["facts"], [])
        self.assertEqual(extracted["missing_categories"], ["business", "customer", "one_off", "debt"])
        schema = __import__("json").loads((Path(__file__).resolve().parents[1] / "schemas/v1/extracted-facts.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(extracted)
