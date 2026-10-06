import sys
import unittest

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from business import extract_business_facts


class BusinessExtractionTests(unittest.TestCase):
    def test_extracts_only_supported_10k_phrases(self):
        html = b'''<p>Our backlog increased from $1,067.0 million as of December 31, 2024 to $1,847.3 million as of December 31, 2025, of which $1,371.7 million is related to space systems and $475.6 million is related to launch services.</p>
        <p>As of December 31, 2025, we had over 2,600 full-time permanent employees worldwide.</p>
        <p>75 successful launches and over 200 spacecraft deployed as of December 31, 2025.</p>
        <p>Neutron, a medium-lift launch vehicle, which we expect will provide payloads up to 13,000 kg for reusable configuration launches.</p>
        <table><tr><td>Year Ended December 31, 2025</td><td>Launch Services</td><td>Space Systems</td><td>Total</td></tr><tr><td>Revenues by recognition model</td><td>Point-in-time</td><td>$ 159,308</td><td>$ 107,432</td><td>$ 266,740</td><td>Over-time</td><td>39,734</td><td>295,325</td><td>335,059</td><td>Total revenue by recognition model</td><td>$ 199,042</td><td>$ 402,757</td><td>$ 601,799</td></tr></table>'''
        facts = extract_business_facts(html)
        self.assertEqual(facts["backlog_fy2025"]["value"], 1_847_300_000)
        self.assertEqual(facts["employees_min_fy2025"]["value"], 2600)
        self.assertEqual(facts["launch_revenue_fy2025"]["value"], 199_042_000)
        self.assertEqual(facts["space_revenue_fy2025"]["value"], 402_757_000)
        self.assertEqual(facts["neutron_planned_capacity_kg"]["value"], 13_000)

    def test_absent_phrase_is_not_inferred(self):
        self.assertEqual(extract_business_facts(b"<p>Backlog and customers.</p>"), {})


if __name__ == "__main__":
    unittest.main()
