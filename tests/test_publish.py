import json
import sys
import tempfile
import unittest
from pathlib import Path

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from publish import activate_local


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        (self.bundle / "meta.json").write_text(json.dumps({"run_id": "new-run", "ticker": "RKLB", "engine": "gpt",
            "analysis_as_of": "2026-10-06T14:00:00+00:00", "data_snapshot_id": "snap-new", "sample": False}), encoding="utf-8")
        (self.bundle / "report.md").write_text("new report", encoding="utf-8")
        self.site = self.root / "site"
        self.site.mkdir()
        self.engine = self.site / "data" / "companies" / "RKLB" / "gpt"
        self.engine.mkdir(parents=True)
        (self.engine / "current.json").write_text(json.dumps({"run_id": "old-run", "analysis_as_of": "2026-10-01T00:00:00+00:00"}), encoding="utf-8")

    def test_build_failure_restores_old_pointer(self):
        def fail():
            raise RuntimeError("build failed")
        with self.assertRaises(RuntimeError):
            activate_local(self.bundle, self.site, fail)
        pointer = json.loads((self.engine / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(pointer["run_id"], "old-run")

    def test_success_switches_pointer_after_build(self):
        seen = []
        def build():
            seen.append(json.loads((self.engine / "current.json").read_text(encoding="utf-8"))["run_id"])
        activate_local(self.bundle, self.site, build)
        self.assertEqual(seen, ["new-run"])
        self.assertEqual(json.loads((self.engine / "current.json").read_text(encoding="utf-8"))["run_id"], "new-run")
        pointer = json.loads((self.engine / "current.json").read_text(encoding="utf-8"))
        self.assertTrue((self.engine / "versions" / pointer["version_id"] / "report.md").exists())

    def test_older_analysis_cannot_replace_newer_one(self):
        (self.engine / "current.json").write_text(json.dumps({"run_id": "old-run", "analysis_as_of": "2026-10-07T00:00:00+00:00"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            activate_local(self.bundle, self.site, lambda: None)


if __name__ == "__main__":
    unittest.main()
