---
name: company
description: Create a sourced US-GAAP company research bundle for a ticker. The investment verdict is held at 판정 보류 (v0.1) until policy details are approved.
---

For a request such as `/company RKLB` or `$company RKLB`, run the plugin's `scripts/company.py` in its repository root with the current engine (`claude` in Claude Code, `gpt` in Codex). Pass the ticker as the first argument and `--engine` explicitly. Set `SEC_USER_AGENT` to an identifying name and contact email before real SEC access; the collector can read it from the Windows User environment when the current process does not see it. Never print or write its value into a file. Add `--sample` only when the user requests a synthetic example. Never describe a synthetic example as a real analysis.

After the script runs, validate the output directory with `scripts/validate_bundle.py`; for real SEC data also run `scripts/verify_sec_run.py` against the cached raw snapshot. The script creates `report-items.json` and `report.md` with the 16 Master Template headings. Its financial sections are partial; sections lacking verified evidence say `자료 확인 대기`. Report the output path, source status, and that the verdict remains `판정 보류 (v0.1)`. Do not compute an investment recommendation, reverse DCF, accounting warning, or forced avoidance decision. If real data collection or credentials are unavailable, state that clearly instead of inventing numbers.

Forward supported user options to the script: `--new`, `--run-id`, `--no-viz`, `--viz-only`, `--original`. `--viz-only` requires an existing `--run-id` and rejects a changed report. The default reuses one matching incomplete run from the last 24 hours; use `--new` to force a fresh SEC snapshot. The Mermaid diagram currently shows verified annual revenue chronology only; business flywheel and value chain remain pending.

The Master Template source is `docs/020. 기업분석_Master Template.md`; its 16 top-level sections are recorded in `template/sections.json`. Preserve their IDs and titles. The v1 schema remains a draft after initial RKLB validation because broader disclosures and non-December fiscal years are not verified.
