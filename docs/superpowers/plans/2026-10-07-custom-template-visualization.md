# Custom template and analysis visuals implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a company-specific 16-section framework before analysis, preserve detailed section work in batches, and publish two report-grounded business diagrams.

**Architecture:** Keep SEC metrics immutable. Add a template artifact and notes contract to each run; store sub-sections under their parent section in report-items. Generate diagrams only from completed sourced report text and bind them to its hash. The site reads the artifact files and presents them in their own tabs.

**Tech Stack:** Python 3.14, JSON Schema, Astro, Mermaid.

**Spec:** User request of 2026-10-07 and private local `docs/reference/` quality examples. The latter never enters the public plugin.

## Global Constraints

- Preserve 16 top-level Master Template IDs and titles; allow nested identifiers such as `S04-A`.
- `metrics.json` remains the source for financial numbers; decision stays `판정 보류 (v0.1)`.
- Web research and source traceability are mandatory for template and each analysis section.
- Never package or commit `docs/reference/`.

## Review Focus

- Missing template: analysis must not silently claim S0.5 complete.
- Incomplete batch: saved progress must not publish as a finished report.
- New sub-section: validate parent relation and preserve 16 major sections.
- Stale diagram: reject when report hash changes.
- Unsourced diagram claim: require report section references.

---

### Task 1: Template contract and S0.5

**Files:** `scripts/template_stage.py`, `scripts/company.py`, `scripts/validate_bundle.py`, `tests/test_template_stage.py`.

**Interfaces:** `create_template_draft(folder)` writes `template.md` and `template-notes.json`; `validate_template(folder)` returns errors. S0.5 remains pending until the custom framework is completed and validated.

- [ ] Write contract tests and verify failure.
- [ ] Implement draft, validation, and run-state integration.
- [ ] Run focused tests.

### Task 2: Nested analysis and saved batches

**Files:** `schemas/v1/report-items.schema.json`, `scripts/report.py`, `scripts/ai_report.py`, `skills/company/SKILL.md`, `tests/test_ai_report.py`.

**Interfaces:** Parent section has optional `subsections`; `ai_report.py --checkpoint` validates and saves one bundle without publishing; finalization requires all major and custom sections.

- [ ] Write tests for nested IDs and partial checkpoint.
- [ ] Implement schema, renderer, validator, and skill workflow.
- [ ] Run focused tests.

### Task 3: Report-grounded diagrams

**Files:** `scripts/visualize_run.py`, `scripts/company.py`, `scripts/publish.py`, `tests/test_visualize.py`.

**Interfaces:** `build_visualization(folder)` reads a report-derived diagram specification and writes two Mermaid files plus a hash manifest; code-only run leaves S5 pending.

- [ ] Write tests for two diagrams, references, and stale hashes.
- [ ] Implement diagram contract and generation.
- [ ] Run focused tests.

### Task 4: Site tabs and private-data barrier

**Files:** `site/src/lib/data.mjs`, `site/src/pages/company/RKLB.astro`, `site/test/site.test.mjs`, `.gitignore`.

- [ ] Test template body, report TOC, and two diagrams in build output.
- [ ] Implement UI changes; retain financial trend in finance tab only.
- [ ] Verify build/tests and tracked files exclude references.

### Task 5: RKLB GPT review

**Files:** Local ignored run artifacts under `runs/RKLB/gpt/`.

- [ ] Web-research and write a fresh custom template with suitability, change table, detailed checks and analogies.
- [ ] Analyze S03 and S04-A only with sources, then generate two review diagrams from sourced report material.
- [ ] Validate and compare scope, depth, and evidence against private quality examples without copying them.
