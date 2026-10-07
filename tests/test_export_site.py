import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from export_site import export_selected_versions, prune_stale_company_routes


class ExportSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.target = self.root / "target"

    def make_selection(self, ticker, engine="gpt", *, sample=False, model="test-model"):
        run_id = f"run-{ticker.lower()}"
        version_id = f"{run_id}-v1"
        folder = self.source / ticker / engine / "versions" / version_id
        folder.mkdir(parents=True)
        report = f"{ticker} synthetic fixture"
        (folder / "report.md").write_text(report, encoding="utf-8")
        (folder / "meta.json").write_text(json.dumps({"ticker": ticker, "engine": engine, "run_id": run_id,
            "model": model, "sample": sample, "data_snapshot_id": f"snap-{ticker}"}), encoding="utf-8")
        (folder / "validation.json").write_text(json.dumps({"status": "passed", "run_id": run_id,
            "data_snapshot_id": f"snap-{ticker}", "report_sha256": hashlib.sha256(report.encode()).hexdigest()}), encoding="utf-8")
        pointer = self.source / ticker / engine / "current.json"
        pointer.write_text(json.dumps({"run_id": run_id, "version_id": version_id,
            "data_snapshot_id": f"snap-{ticker}"}), encoding="utf-8")
        return folder, pointer

    def test_exports_only_validated_selected_versions_without_cross_company_data(self):
        self.make_selection("VRT")
        self.make_selection("MSFT")
        self.make_selection("RKLB", sample=True)
        unselected = self.source / "VRT/gpt/versions/unselected"
        unselected.mkdir()
        (unselected / "private.txt").write_text("do not export", encoding="utf-8")
        copied = export_selected_versions(self.source, self.target)
        self.assertEqual(sorted(Path(path).parts[2] for path in copied), ["MSFT", "VRT"])
        for ticker in ("VRT", "MSFT"):
            pointer = json.loads((self.target / "data/companies" / ticker / "gpt/current.json").read_text(encoding="utf-8"))
            report = (self.target / "data/companies" / ticker / "gpt/versions" / pointer["version_id"] / "report.md").read_text(encoding="utf-8")
            self.assertEqual(report, f"{ticker} synthetic fixture")
        self.assertFalse((self.target / "data/companies/VRT/gpt/versions/unselected").exists())
        self.assertFalse((self.target / "data/companies/RKLB").exists())

    def test_rejects_unsafe_pointer_and_company_mismatch(self):
        folder, pointer = self.make_selection("VRT")
        pointer.write_text(json.dumps({"run_id": "run-vrt", "version_id": ".."}), encoding="utf-8")
        with self.assertRaises(ValueError):
            export_selected_versions(self.source, self.target)
        pointer.write_text(json.dumps({"run_id": "run-vrt", "version_id": "run-vrt-v1"}), encoding="utf-8")
        meta_path = folder / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["ticker"] = "RKLB"
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        with self.assertRaises(ValueError):
            export_selected_versions(self.source, self.target)

    def test_market_snapshot_requires_matching_ticker_and_display_permission(self):
        self.make_selection("VRT")
        market = self.source / "VRT/market-snapshot.json"
        market.write_text(json.dumps({"ticker": "VRT", "source": "Twelve Data", "price": 42,
            "as_of": "2026-10-07", "fetched_at": "2026-10-07T00:00:00+00:00"}), encoding="utf-8")
        export_selected_versions(self.source, self.target, display_allowed=False)
        self.assertFalse((self.target / "data/companies/VRT/market-snapshot.json").exists())
        export_selected_versions(self.source, self.target, display_allowed=True)
        self.assertTrue((self.target / "data/companies/VRT/market-snapshot.json").exists())
        market.write_text(json.dumps({"ticker": "RKLB", "source": "Twelve Data", "price": 42}), encoding="utf-8")
        with self.assertRaises(ValueError):
            export_selected_versions(self.source, self.target, display_allowed=True)

    def test_export_removes_obsolete_fixed_company_route(self):
        route_dir = self.target / "src/pages/company"
        route_dir.mkdir(parents=True)
        (route_dir / "RKLB.astro").write_text("old fixed route", encoding="utf-8")
        (route_dir / "[ticker].astro").write_text("new dynamic route", encoding="utf-8")
        prune_stale_company_routes(self.target, {"src/pages/company/[ticker].astro"})
        self.assertFalse((route_dir / "RKLB.astro").exists())
        self.assertTrue((route_dir / "[ticker].astro").exists())


if __name__ == "__main__":
    unittest.main()
