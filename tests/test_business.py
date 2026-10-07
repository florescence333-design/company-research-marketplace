import sys
import unittest

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from business import extract_business_facts, extract_company_filing_facts


class BusinessExtractionTests(unittest.TestCase):
    def test_extracts_only_supported_10k_phrases(self):
        html = b'''<p>Our backlog increased from $1,067.0 million as of December 31, 2024 to $1,847.3 million as of December 31, 2025, of which $1,371.7 million is related to space systems and $475.6 million is related to launch services.</p>
        <p>As of December 31, 2025, we had over 2,600 full-time permanent employees worldwide.</p>
        <p>75 successful launches and over 200 spacecraft deployed as of December 31, 2025.</p>
        <p>Neutron, a medium-lift launch vehicle, which we expect will provide payloads up to 13,000 kg for reusable configuration launches.</p>
        <p>For the year ended December 31, 2025, our top five customers accounted for approximately 49% of our revenues and our top five backlog customers accounted for approximately 77% of our backlog in the aggregate as of December 31, 2025.</p>
        <table><tr><td>Year Ended December 31, 2025</td><td>Launch Services</td><td>Space Systems</td><td>Total</td></tr><tr><td>Revenues by recognition model</td><td>Point-in-time</td><td>$ 159,308</td><td>$ 107,432</td><td>$ 266,740</td><td>Over-time</td><td>39,734</td><td>295,325</td><td>335,059</td><td>Total revenue by recognition model</td><td>$ 199,042</td><td>$ 402,757</td><td>$ 601,799</td></tr></table>'''
        facts = extract_business_facts(html)
        self.assertEqual(facts["backlog_fy2025"]["value"], 1_847_300_000)
        self.assertEqual(facts["employees_min_fy2025"]["value"], 2600)
        self.assertEqual(facts["launch_revenue_fy2025"]["value"], 199_042_000)
        self.assertEqual(facts["space_revenue_fy2025"]["value"], 402_757_000)
        self.assertEqual(facts["neutron_planned_capacity_kg"]["value"], 13_000)
        self.assertEqual(facts["top5_revenue_share_approx_fy2025"]["value"], 49)
        self.assertEqual(facts["top5_backlog_share_approx_fy2025"]["value"], 77)

    def test_absent_phrase_is_not_inferred(self):
        self.assertEqual(extract_business_facts(b"<p>Backlog and customers.</p>"), {})

    def test_company_rules_require_matching_filing_and_section(self):
        filing = {"form": "10-K", "report_date": "2025-12-31", "raw": b""}
        filing["raw"] = b"<p>Vertiv</p><h2>Backlog</h2><p>Vertiv's estimated combined order backlog was $15.0 billion and $7.2 billion as of December 31, 2025 and 2024, respectively.</p>"
        facts = extract_company_filing_facts("VRT", filing)
        self.assertEqual(facts["backlog_fy2025"]["value"], 15_000_000_000)
        self.assertEqual(facts["backlog_fy2024"]["category"], "business")
        self.assertEqual(extract_company_filing_facts("MSFT", filing), {})
        self.assertEqual(extract_company_filing_facts("VRT", {**filing, "report_date": "2024-12-31"}), {})
        self.assertEqual(extract_company_filing_facts("VRT", {**filing, "raw": filing["raw"].replace(b"<h2>Backlog</h2>", b"<h2>Outlook</h2>")}), {})

    def test_vrt_quarter_debt_and_one_off_are_bounded_by_note(self):
        raw = b"<p>Vertiv</p><h2>(6) DEBT</h2><p>Long-term debt, net, consisted of the following as of June 30, 2026 and December 31, 2025: Total long-term debt, net of current portion $ 2,939.8 $ 2,892.1 Senior Notes On March 3, 2026, Vertiv Holdings Co issued $ 2,100.0 in aggregate principal amount of senior unsecured notes</p><h2>(7) INCOME TAXES</h2>"
        facts = extract_company_filing_facts("VRT", {"form": "10-Q", "report_date": "2026-06-30", "raw": raw})
        self.assertEqual(facts["long_term_debt_net_2026q2"]["value"], 2_939_800_000)
        self.assertEqual(facts["senior_notes_issued_2026h1"]["value"], 2_100_000_000)
        self.assertEqual(facts["senior_notes_issued_2026h1"]["category"], "one_off")
        self.assertEqual(extract_company_filing_facts("VRT", {"form": "10-Q", "report_date": "2026-06-30", "raw": raw.replace(b"(6) DEBT", b"(6) OTHER")}), {})

    def test_msft_customer_and_debt_do_not_confuse_investments(self):
        raw = b"<p>Microsoft</p><p>Revenue allocated to remaining performance obligations, which includes unearned revenue and amounts expected to be invoiced and recognized as revenue in future periods, was $ 684 billion as of June 30, 2026.</p><p>Current year net income and diluted EPS were positively impacted by net gains from investments in OpenAI, which resulted in an increase in net income and diluted EPS of $5.0 billion and $0.67, respectively.</p><p>Total debt investments $ 99,999</p><h2>NOTE 10 - DEBT</h2><p>The components of long-term debt were as follows: (In millions) June 30, 2026 June 30, 2025 Total debt 40,294 43,151 Current portion of long-term debt ( 9,227 ) ( 2,999 ) Long-term debt $ 31,067 $ 40,152</p><h2>NOTE 11 - OTHER</h2><p>No sales to an individual customer or country other than the United States accounted for more than 10% of revenue for fiscal years 2026, 2025, or 2024.</p>"
        facts = extract_company_filing_facts("MSFT", {"form": "10-K", "report_date": "2026-06-30", "raw": raw})
        self.assertEqual(facts["remaining_performance_obligations_fy2026"]["value"], 684_000_000_000)
        self.assertEqual(facts["openai_net_income_impact_fy2026"]["value"], 5_000_000_000)
        self.assertEqual(facts["total_debt_fy2026"]["value"], 40_294_000_000)
        self.assertEqual(facts["long_term_debt_fy2026"]["value"], 31_067_000_000)
        self.assertEqual(facts["individual_customer_revenue_ceiling_fy2026"]["value"], 10)


if __name__ == "__main__":
    unittest.main()
