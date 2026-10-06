import json
import sys
import tempfile
import unittest
from pathlib import Path

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from visualize_run import build_visualization, verify_visualization


class VisualizationTests(unittest.TestCase):
    def test_diagram_is_bound_to_report_and_detects_change(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "meta.json").write_text(json.dumps({"run_id": "r1", "data_snapshot_id": "d1"}), encoding="utf-8")
            (folder / "metrics.json").write_text(json.dumps({"metrics": [
                {"metric_id": "revenue_fy2023", "status": "ok", "value": 100},
                {"metric_id": "revenue_fy2024", "status": "ok", "value": 200},
                {"metric_id": "revenue_fy2025", "status": "ok", "value": 300},
            ]}), encoding="utf-8")
            report = folder / "report.md"
            report.write_text("Original report", encoding="utf-8")
            build_visualization(folder)
            self.assertEqual(verify_visualization(folder), [])
            self.assertIn("FY2025", (folder / "diagrams" / "revenue.mmd").read_text(encoding="utf-8"))
            report.write_text("Changed report", encoding="utf-8")
            self.assertTrue(verify_visualization(folder))


if __name__ == "__main__":
    unittest.main()
