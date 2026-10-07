import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from publish import activate_local, check_bundle, select_bundle


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

    def test_multiple_tickers_keep_independent_pointers_and_versions(self):
        for ticker, run_id in (("VRT", "vrt-run"), ("MSFT", "msft-run")):
            bundle = self.root / f"bundle-{ticker}"
            bundle.mkdir()
            (bundle / "meta.json").write_text(json.dumps({"run_id": run_id, "ticker": ticker, "engine": "gpt",
                "analysis_as_of": "2026-10-06T14:00:00+00:00", "data_snapshot_id": f"snap-{ticker}", "sample": True}), encoding="utf-8")
            (bundle / "report.md").write_text(f"{ticker} synthetic report", encoding="utf-8")
            activate_local(bundle, self.site, lambda: None)
        for ticker, run_id in (("VRT", "vrt-run"), ("MSFT", "msft-run")):
            root = self.site / "data" / "companies" / ticker / "gpt"
            pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
            self.assertEqual(pointer["run_id"], run_id)
            self.assertEqual((root / "versions" / pointer["version_id"] / "report.md").read_text(encoding="utf-8"), f"{ticker} synthetic report")
        self.assertEqual(json.loads((self.engine / "current.json").read_text(encoding="utf-8"))["run_id"], "old-run")

    def test_invalid_ticker_engine_and_run_id_cannot_escape_site(self):
        original = json.loads((self.bundle / "meta.json").read_text(encoding="utf-8"))
        for field, value in (("ticker", ".."), ("ticker", "VRT/../RKLB"), ("engine", "../gpt"), ("run_id", "..")):
            bad = {**original, field: value}
            (self.bundle / "meta.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                activate_local(self.bundle, self.site, lambda: None)
        (self.bundle / "meta.json").write_text(json.dumps(original), encoding="utf-8")
        for ticker, engine, run_id in (("..", "gpt", None), ("RKLB", "../gpt", None), ("RKLB", "gpt", "..")):
            with self.assertRaises(ValueError):
                select_bundle(ticker, engine, run_id)

    def test_failed_second_company_build_restores_only_that_company(self):
        vrt = self.root / "bundle-vrt"
        vrt.mkdir()
        (vrt / "meta.json").write_text(json.dumps({"run_id": "vrt-old", "ticker": "VRT", "engine": "gpt",
            "analysis_as_of": "2026-10-06T14:00:00+00:00", "data_snapshot_id": "vrt-snap", "sample": True}), encoding="utf-8")
        (vrt / "report.md").write_text("VRT report", encoding="utf-8")
        activate_local(vrt, self.site, lambda: None)
        msft = self.root / "bundle-msft"
        msft.mkdir()
        (msft / "meta.json").write_text(json.dumps({"run_id": "msft-new", "ticker": "MSFT", "engine": "gpt",
            "analysis_as_of": "2026-10-06T14:00:00+00:00", "data_snapshot_id": "msft-snap", "sample": True}), encoding="utf-8")
        (msft / "report.md").write_text("MSFT report", encoding="utf-8")
        msft_root = self.site / "data/companies/MSFT/gpt"
        msft_root.mkdir(parents=True)
        previous = {"run_id": "msft-old", "analysis_as_of": "2026-10-01T00:00:00+00:00"}
        (msft_root / "current.json").write_text(json.dumps(previous), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            activate_local(msft, self.site, lambda: (_ for _ in ()).throw(RuntimeError("build failed")))
        self.assertEqual(json.loads((self.site / "data/companies/VRT/gpt/current.json").read_text(encoding="utf-8"))["run_id"], "vrt-old")
        self.assertEqual(json.loads((msft_root / "current.json").read_text(encoding="utf-8")), previous)

    def test_real_non_rklb_bundle_uses_its_own_sec_cache_for_recalculation(self):
        (self.bundle / "meta.json").write_text(json.dumps({"run_id": "vrt-run", "ticker": "VRT", "engine": "gpt",
            "analysis_as_of": "2026-10-06T14:00:00+00:00", "data_snapshot_id": "vrt-snap", "sample": False,
            "sec_filings": []}), encoding="utf-8")
        with patch("publish.validate_bundle", return_value=[]), patch("publish.verify_resume", return_value={}), \
             patch("publish.verify_run", return_value=["fixture stop"]) as recalculate:
            with self.assertRaisesRegex(ValueError, "fixture stop"):
                check_bundle(self.bundle, "VRT", "gpt")
            self.assertEqual(recalculate.call_args.args[1], ROOT / "data" / "sec" / "VRT" / "companyfacts.json")

    def test_non_rklb_without_company_specific_sec_manifest_is_rejected(self):
        (self.bundle / "meta.json").write_text(json.dumps({"run_id": "vrt-run", "ticker": "VRT", "engine": "gpt",
            "analysis_as_of": "2026-10-06T14:00:00+00:00", "data_snapshot_id": "vrt-snap", "sample": False}), encoding="utf-8")
        with patch("publish.validate_bundle", return_value=[]), patch("publish.verify_resume", return_value={}), \
             patch("publish.verify_run") as recalculate:
            with self.assertRaisesRegex(ValueError, "기업별 SEC 원본 정보 없음"):
                check_bundle(self.bundle, "VRT", "gpt")
            recalculate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
