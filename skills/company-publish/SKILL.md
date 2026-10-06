---
name: company-publish
description: Validate a real company bundle and build the protected local site, keeping the prior selected result if the build fails.
---

For `/company-publish RKLB` or `$company-publish RKLB`, run `scripts/publish.py RKLB --engine <current engine>` from the plugin root. Add `--run-id <folder name>` when the user specifies one. This command rejects synthetic samples, stale results, changed run outputs, invalid section references, SEC source mismatches, and report/diagram hash changes. It selects the result for the local Astro site and runs its build and tests. A failed build restores the prior selected result.

Report the selected run, validation result, local site path, and remote status separately. Local build success does not mean GitHub push or Cloudflare Pages deployment succeeded. Do not claim a public or protected remote page until its commit hash and authentication are checked on the actual deployment. Never print or commit credentials or the local SEC User-Agent.
