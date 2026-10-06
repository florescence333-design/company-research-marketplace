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
            (folder / "report-items.json").write_text(json.dumps({"sections": [
                {"section_id": sid, "status": "partial"} for sid in ("S04", "S08", "S09")
            ]}), encoding="utf-8")
            report = folder / "report.md"
            report.write_text("Original report", encoding="utf-8")
            (folder / "diagrams").mkdir()
            (folder / "diagrams" / "spec.json").write_text(json.dumps({
                "flywheel": {"section_ids": ["S04", "S09"], "explanation": ["a", "b", "c"],
                             "elements": ["A", "B", "C", "D", "E"],
                             "mermaid": "flowchart LR\n A -->|more| B -->|more| C -->|more| D -->|more| E -->|more| A\n X[위험] -.-> A"},
                "value_chain": {"section_ids": ["S04", "S08"], "explanation": ["a", "b", "c"],
                                "mermaid": "flowchart LR\n A[외부] --> B[직접 제작] --> C[고객]"},
            }), encoding="utf-8")
            build_visualization(folder)
            self.assertEqual(verify_visualization(folder), [])
            self.assertTrue((folder / "diagrams" / "flywheel.mmd").exists())
            self.assertTrue((folder / "diagrams" / "value-chain.mmd").exists())
            report.write_text("Changed report", encoding="utf-8")
            self.assertTrue(verify_visualization(folder))


if __name__ == "__main__":
    unittest.main()
