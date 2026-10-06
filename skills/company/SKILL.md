---
name: company
description: Create a sourced US-GAAP company research bundle for a ticker. The investment verdict is held at 판정 보류 (v0.1) until policy details are approved.
---

For a request such as `/company RKLB` or `$company RKLB`, run the plugin's `scripts/company.py` in its repository root with the current engine (`claude` in Claude Code, `gpt` in Codex). Pass the ticker as the first argument and `--engine` explicitly. In the current smoke-test stage, add `--sample` only when the user requests a synthetic example. Never describe a synthetic example as a real analysis.

After the script runs, validate the output directory with `scripts/validate_bundle.py`. Report the output path, source status, and that the verdict remains `판정 보류 (v0.1)`. Do not compute an investment recommendation, reverse DCF, accounting warning, or forced avoidance decision. If real data collection or credentials are unavailable, state that clearly instead of inventing numbers.

The Master Template source is `docs/020. 기업분석_Master Template.md`; its 16 top-level sections are recorded in `template/sections.json`. Preserve their IDs and titles. The v1 schema is a draft until actual RKLB SEC data passes step 4 validation.
