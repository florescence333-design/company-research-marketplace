import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const siteRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const dataRoot = process.env.SITE_DATA_DIR ? resolve(process.env.SITE_DATA_DIR) : join(siteRoot, 'data', 'companies');

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

export function loadCompany(ticker = 'RKLB') {
  const versions = {};
  for (const engine of ['claude', 'gpt']) {
    const folder = join(dataRoot, ticker, engine);
    if (existsSync(join(folder, 'meta.json')) && existsSync(join(folder, 'decision.json'))) {
      versions[engine] = {
        meta: readJson(join(folder, 'meta.json')),
        decision: readJson(join(folder, 'decision.json')),
        metrics: existsSync(join(folder, 'metrics.json')) ? readJson(join(folder, 'metrics.json')).metrics : [],
        sources: existsSync(join(folder, 'sources.json')) ? readJson(join(folder, 'sources.json')).sources : [],
        report: existsSync(join(folder, 'report.md')) ? readFileSync(join(folder, 'report.md'), 'utf8') : null,
      };
    }
  }
  if (Object.keys(versions).length === 0) {
    const placeholder = engine => ({
      meta: { ticker, engine, sample: true, analysis_as_of: null },
      decision: { verdict: '판정 보류 (v0.1)', reason: '샘플 화면: 실제 공시 분석 전' },
      metrics: [], sources: [], report: null,
    });
    versions.claude = placeholder('claude');
    versions.gpt = placeholder('gpt');
  }
  return versions;
}
