import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "v1"


def validate(name, value):
    schema = json.loads((SCHEMA / f"{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)


class ContractTests(unittest.TestCase):
    def sample_meta(self):
        return {
            "schema_version": "v1-draft",
            "run_id": "run-rklb-001",
            "data_snapshot_id": "sec-rklb-001",
            "analysis_as_of": "2026-10-06T12:00:00+09:00",
            "generated_at": "2026-10-06T12:01:00+09:00",
            "ticker": "RKLB",
            "cik": "0001819994",
            "engine": "gpt",
            "sample": True,
            "code_version": "v0.1",
            "template_version": "sha256:test",
            "technical_defaults_version": "v1",
            "decision_policy_version": "v0.1",
        }

    def test_meta_accepts_complete_identity_and_rejects_naive_time(self):
        meta = self.sample_meta()
        validate("meta", meta)
        meta["analysis_as_of"] = "2026-10-06T12:00:00"
        with self.assertRaises(ValidationError):
            validate("meta", meta)

    def test_meta_rejects_unknown_engine(self):
        meta = self.sample_meta()
        meta["engine"] = "unknown"
        with self.assertRaises(ValidationError):
            validate("meta", meta)

    def test_common_fact_requires_reason_for_missing_value(self):
        schema = json.loads((SCHEMA / "common.schema.json").read_text(encoding="utf-8"))
        fact_schema = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/fact"}
        validator = Draft202012Validator(fact_schema, format_checker=FormatChecker())
        fact = {"status": "unavailable", "value": None, "unit": "USD", "approximate": False}
        self.assertTrue(list(validator.iter_errors(fact)))
        fact["reason"] = "공시 미확인"
        self.assertFalse(list(validator.iter_errors(fact)))
        fact["value"] = 0
        self.assertTrue(list(validator.iter_errors(fact)))

    def test_run_rejects_unknown_step_state(self):
        run = {
            "run_id": "run-rklb-001", "ticker": "RKLB", "engine": "gpt",
            "analysis_as_of": "2026-10-06T12:00:00+09:00",
            "data_snapshot_id": "sec-rklb-001",
            "steps": [{"step_id": "S1", "state": "completed", "output_sha256": "0" * 64}],
        }
        validate("run", run)
        run["steps"][0]["state"] = "magically-done"
        with self.assertRaises(ValidationError):
            validate("run", run)

    def test_source_requires_traceable_location(self):
        sources = {"sources": [{"source_id": "sec-1", "url": "https://www.sec.gov/", "title": "10-K", "accessed_at": "2026-10-06T12:00:00Z", "location": "Item 8"}]}
        validate("sources", sources)
        del sources["sources"][0]["location"]
        with self.assertRaises(ValidationError):
            validate("sources", sources)

    def test_sections_match_all_sixteen_master_headings(self):
        from scripts.build_sections import extract_sections

        master = ROOT / "docs" / "020. 기업분석_Master Template.md"
        sections = extract_sections(master.read_text(encoding="utf-8"))
        self.assertEqual(len(sections), 16)
        self.assertEqual(sections[0], {"section_id": "S01", "title": "기본 정보", "required": True})
        self.assertEqual(sections[13], {"section_id": "S14", "title": "밸류에이션", "required": True})
        self.assertEqual(sections[15]["title"], "최종 결론 (Summary & Action)")
        published = json.loads((ROOT / "template" / "sections.json").read_text(encoding="utf-8"))
        self.assertEqual(published["sections"], sections)


if __name__ == "__main__":
    unittest.main()
