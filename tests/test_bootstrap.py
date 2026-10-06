"""A plugin checkout must prepare a fresh Windows work folder without project .venv."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "The TA bootstrap is Windows-specific")
class BootstrapSmokeTests(unittest.TestCase):
    def test_fresh_folder_has_its_own_python_and_sample_run(self):
        script = ROOT / "scripts" / "bootstrap.py"
        self.assertTrue(script.is_file(), "plugin bootstrap entry point is missing")
        self.assertIsNotNone(shutil.which("uv"), "uv is required on the TA PC")
        self.assertIsNotNone(shutil.which("npm.cmd"), "Node.js/npm is required on the TA PC")
        with tempfile.TemporaryDirectory(prefix="company-plugin-ta-") as temporary:
            empty_folder = Path(temporary)
            self.assertEqual(list(empty_folder.iterdir()), [])
            setup = subprocess.run(
                ["uv", "run", "--no-project", "--python", "3.14", str(script)],
                cwd=empty_folder, capture_output=True, text=True, timeout=240,
            )
            self.assertEqual(setup.returncode, 0, setup.stdout + setup.stderr)
            workspace = empty_folder / ".company-research"
            python = workspace / ".venv" / "Scripts" / "python.exe"
            self.assertTrue(python.is_file())
            self.assertTrue((workspace / "site" / "node_modules" / "astro").is_dir())
            self.assertFalse((workspace / "data").exists(), "development data must not be copied")
            imports = subprocess.run(
                [str(python), "-c", "import jsonschema"], cwd=workspace,
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(imports.returncode, 0, imports.stdout + imports.stderr)
            sample = subprocess.run(
                [str(python), "scripts/company.py", "RKLB", "--engine", "claude", "--sample"],
                cwd=workspace, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(sample.returncode, 0, sample.stdout + sample.stderr)
            samples = list((workspace / "runs" / "RKLB" / "claude").glob("sample-*/meta.json"))
            self.assertEqual(len(samples), 1)
            self.assertTrue(json.loads(samples[0].read_text(encoding="utf-8"))["sample"])


if __name__ == "__main__":
    unittest.main()
