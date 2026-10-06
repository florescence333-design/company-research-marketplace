import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import ValidationError

from test_contract import ROOT, validate


class BundleTests(unittest.TestCase):
    def test_v01_decision_is_always_deferred(self):
        decision = {
            "schema_version": "v1-draft",
            "decision_policy_version": "v0.1",
            "verdict": "판정 보류 (v0.1)",
            "reason": "판정 세부 규칙 미정",
            "business_quality": None,
            "price_category": None,
        }
        validate("decision", decision)
        decision["verdict"] = "매수 검토"
        with self.assertRaises(ValidationError):
            validate("decision", decision)

    def test_bundle_cli_accepts_sample_and_rejects_inconsistent_run(self):
        source = ROOT / "examples" / "sample-rklb"
        command = [sys.executable, str(ROOT / "scripts" / "validate_bundle.py"), str(source)]
        good = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            for path in source.glob("*.json"):
                (bundle / path.name).write_bytes(path.read_bytes())
            metric = json.loads((bundle / "metrics.json").read_text(encoding="utf-8"))
            metric["run_id"] = "different-run"
            (bundle / "metrics.json").write_text(json.dumps(metric), encoding="utf-8")
            bad = subprocess.run(command[:-1] + [str(bundle)], cwd=ROOT, text=True, capture_output=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("run_id", bad.stdout)

    def test_metric_rejects_missing_value_without_reason(self):
        metrics = {
            "run_id": "run-rklb-001", "data_snapshot_id": "sec-rklb-001",
            "metrics": [{"metric_id": "revenue", "value": None, "status": "unavailable", "unit": "USD", "approximate": False}],
        }
        with self.assertRaises(ValidationError):
            validate("metrics", metrics)
        metrics["metrics"][0]["reason"] = "공시 수집 전"
        validate("metrics", metrics)


if __name__ == "__main__":
    unittest.main()
