import json
import sys
import tempfile
import unittest
from pathlib import Path

from test_contract import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from template_stage import create_template_draft, render_template, validate_template


class TemplateStageTests(unittest.TestCase):
    def test_draft_is_not_complete_and_completed_notes_require_real_framework(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "meta.json").write_text(json.dumps({"run_id": "r", "data_snapshot_id": "d"}), encoding="utf-8")
            (folder / "sources.json").write_text(json.dumps({"sources": [{"source_id": "web-1"}]}), encoding="utf-8")
            create_template_draft(folder)
            self.assertTrue(validate_template(folder))
            notes = json.loads((folder / "template-notes.json").read_text(encoding="utf-8"))
            notes.update(status="completed", suitability="부분 적합", suitability_reason="핵심 사업에 맞춘다",
                         source_ids=["web-1"], search_queries=["company investor relations"])
            for section in notes["sections"]:
                section.update(rationale="원본 질문이 해당한다", checklist=["매출 구조 확인"],
                               metric_definitions=["성장률 = 올해/전년-1"], analogy="사업의 속도계")
            notes["sections"][3]["subsections"].append({"section_id": "S04-A", "title": "신사업",
                "change_type": "신설", "rationale": "별도 평가", "checklist": ["상용화?"],
                "metric_definitions": ["일정 차이 = 실제-계획"], "analogy": "시험 전 학생"})
            (folder / "template-notes.json").write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")
            (folder / "template.md").write_text(render_template(notes), encoding="utf-8")
            self.assertEqual(validate_template(folder), [])
            self.assertIn("S04-A", (folder / "template.md").read_text(encoding="utf-8"))
