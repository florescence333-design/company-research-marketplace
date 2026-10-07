import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_contract import ROOT


class CompanyCommandTests(unittest.TestCase):
    def test_s0_rejection_never_collects_or_creates_run(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import company
        from s0 import S0Result

        with tempfile.TemporaryDirectory() as temp:
            with patch.object(company, "ROOT", Path(temp)), patch.object(sys, "argv", ["company.py", "JPM", "--engine", "gpt"]), \
                 patch.object(company, "load_s0", return_value=S0Result("JPM", False, "지원 범위 밖: 금융·보험·부동산(SIC 6021)")), \
                 patch.object(company, "write_real_run") as collect, patch.object(company.subprocess, "run") as publish:
                with self.assertRaises(SystemExit):
                    company.main()
                collect.assert_not_called()
                publish.assert_not_called()
                self.assertFalse((Path(temp) / "runs").exists())

    def test_s0_pass_for_other_company_enters_its_own_collector(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import company
        from s0 import S0Result

        with tempfile.TemporaryDirectory() as temp:
            eligible = S0Result("VRT", True, "S0 통과", "0001674101", "Vertiv", "NYSE")
            with patch.object(company, "ROOT", Path(temp)), patch.object(sys, "argv", ["company.py", "VRT", "--engine", "gpt"]), \
                 patch.object(company, "load_s0", return_value=eligible), \
                 patch.object(company, "write_real_run", side_effect=ValueError("fixture stop")) as collect:
                with self.assertRaises(SystemExit):
                    company.main()
                self.assertEqual(collect.call_args.args[2], eligible)
                self.assertFalse((Path(temp) / "runs").exists())

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
