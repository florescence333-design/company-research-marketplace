import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

// Astro rebundles this module into dist, so import.meta.url points at dist during a build.
const siteRoot = process.env.SITE_ROOT ? resolve(process.env.SITE_ROOT) : process.cwd();
const dataRoot = process.env.SITE_DATA_DIR ? resolve(process.env.SITE_DATA_DIR) : join(siteRoot, 'data', 'companies');

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

export function loadCompany(ticker = 'RKLB') {
  const versions = {};
  for (const engine of ['claude', 'gpt']) {
    const engineRoot = join(dataRoot, ticker, engine);
    const pointerPath = join(engineRoot, 'current.json');
    let folder = engineRoot;
    if (existsSync(pointerPath)) {
      const pointer = readJson(pointerPath);
      const version = pointer.version_id || pointer.run_id;
      folder = /^[A-Za-z0-9._-]+$/.test(version || '') ? join(engineRoot, 'versions', version) : '';
    }
    if (existsSync(join(folder, 'meta.json')) && existsSync(join(folder, 'decision.json'))) {
      versions[engine] = {
        meta: readJson(join(folder, 'meta.json')),
        decision: readJson(join(folder, 'decision.json')),
        metrics: existsSync(join(folder, 'metrics.json')) ? readJson(join(folder, 'metrics.json')).metrics : [],
        sources: existsSync(join(folder, 'sources.json')) ? readJson(join(folder, 'sources.json')).sources : [],
        reportItems: existsSync(join(folder, 'report-items.json')) ? readJson(join(folder, 'report-items.json')).sections : [],
        template: existsSync(join(folder, 'template.md')) ? readFileSync(join(folder, 'template.md'), 'utf8') : null,
        diagrams: existsSync(join(folder, 'diagrams/spec.json')) && existsSync(join(folder, 'diagrams/manifest.json'))
          ? Object.fromEntries(Object.entries(readJson(join(folder, 'diagrams/spec.json'))).map(([kind, diagram]) => [kind, {
              ...diagram,
              mermaid: existsSync(join(folder, `diagrams/${kind === 'flywheel' ? 'flywheel' : 'value-chain'}.mmd`))
                ? readFileSync(join(folder, `diagrams/${kind === 'flywheel' ? 'flywheel' : 'value-chain'}.mmd`), 'utf8') : null,
            }])) : {},
        report: existsSync(join(folder, 'report.md')) ? readFileSync(join(folder, 'report.md'), 'utf8') : null,
      };
    }
  }
  if (Object.keys(versions).length === 0) {
    const placeholder = engine => ({
      meta: { ticker, engine, sample: true, analysis_as_of: null },
      decision: { verdict: '판정 보류 (v0.1)', reason: '샘플 화면: 실제 공시 분석 전' },
      metrics: [], sources: [], reportItems: [], template: null, diagrams: {}, report: null,
    });
    versions.claude = placeholder('claude');
    versions.gpt = placeholder('gpt');
  }
  return versions;
}
