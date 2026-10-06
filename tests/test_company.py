import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_contract import ROOT


class CompanyCommandTests(unittest.TestCase):
    def test_sample_run_for_both_engines_validates(self):
        for engine in ("claude", "gpt"):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory() as temp:
                command = [sys.executable, str(ROOT / "scripts" / "company.py"), "RKLB", "--engine", engine, "--sample", "--output", temp]
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                bundle = Path(temp)
                meta = json.loads((bundle / "meta.json").read_text(encoding="utf-8"))
                self.assertEqual(meta["engine"], engine)
                self.assertTrue(meta["sample"])
                decision = json.loads((bundle / "decision.json").read_text(encoding="utf-8"))
                self.assertEqual(decision["verdict"], "판정 보류 (v0.1)")
                checked = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_bundle.py"), temp], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

    def test_conflicting_visualization_options_are_rejected(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "company.py"), "RKLB", "--engine", "gpt",
                                 "--no-viz", "--viz-only", "--run-id", "one"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("잘못된 옵션 조합", result.stderr)


if __name__ == "__main__":
    unittest.main()
