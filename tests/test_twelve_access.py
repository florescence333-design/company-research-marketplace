import sys
import unittest

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from check_twelve_access import classify_response


class TwelveAccessTests(unittest.TestCase):
    def test_plan_denial_is_distinct_from_quota_and_empty_success(self):
        self.assertEqual(classify_response({"status": "error", "message": "Upgrade your plan"}), "plan_unavailable")
        self.assertEqual(classify_response({"status": "error", "message": "API credits exhausted"}), "quota_or_rate_limit")
        self.assertEqual(classify_response({"status": "ok", "earnings": {}}), "accessible")
        self.assertEqual(classify_response({"dividends": []}), "accessible")


if __name__ == "__main__":
    unittest.main()
