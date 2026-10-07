import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { buildFinancialDashboard } from './dashboard.mjs';

// Astro rebundles this module into dist, so import.meta.url points at dist during a build.
const siteRoot = process.env.SITE_ROOT ? resolve(process.env.SITE_ROOT) : process.cwd();
const dataRoot = process.env.SITE_DATA_DIR ? resolve(process.env.SITE_DATA_DIR) : join(siteRoot, 'data', 'companies');

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

const safeTicker = ticker => {
  if (typeof ticker !== 'string') throw new Error(`Invalid ticker: ${ticker}`);
  const value = String(ticker).toUpperCase();
  if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(value)) throw new Error(`Invalid ticker: ${ticker}`);
  return value;
};

export function loadCompany(ticker, root = dataRoot) {
  ticker = safeTicker(ticker);
  const versions = {};
  for (const engine of ['claude', 'gpt']) {
    const engineRoot = join(root, ticker, engine);
    const pointerPath = join(engineRoot, 'current.json');
    let folder = engineRoot;
    if (existsSync(pointerPath)) {
      const pointer = readJson(pointerPath);
      const version = pointer.version_id || pointer.run_id;
      if (version === '.' || version === '..' || !/^[A-Za-z0-9._-]+$/.test(version || '')) {
        throw new Error(`Invalid selected version for ticker ${ticker}`);
      }
      folder = join(engineRoot, 'versions', version);
      if (!existsSync(join(folder, 'meta.json')) || !existsSync(join(folder, 'decision.json'))) {
        throw new Error(`Missing selected version for ticker ${ticker}: ${version}`);
      }
    }
    if (existsSync(join(folder, 'meta.json')) && existsSync(join(folder, 'decision.json'))) {
      const meta = readJson(join(folder, 'meta.json'));
      if (meta.ticker !== ticker) throw new Error(`Selected data ticker mismatch: expected ${ticker}`);
      versions[engine] = {
        meta,
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
      versions[engine].dashboard = buildFinancialDashboard(versions[engine].metrics);
    }
  }
  if (Object.keys(versions).length === 0) {
    const placeholder = engine => ({
      meta: { ticker, engine, sample: true, analysis_as_of: null },
      decision: { verdict: '판정 보류 (v0.1)', reason: '샘플 화면: 실제 공시 분석 전' },
      metrics: [], sources: [], reportItems: [], template: null, diagrams: {}, report: null,
      dashboard: buildFinancialDashboard([]),
    });
    versions.claude = placeholder('claude');
    versions.gpt = placeholder('gpt');
  }
  return versions;
}

export function listCompanies(root = dataRoot) {
  if (!existsSync(root)) return [];
  return readdirSync(root, { withFileTypes: true })
    .filter(entry => entry.isDirectory() && /^[A-Z][A-Z0-9.-]{0,9}$/.test(entry.name))
    .map(entry => entry.name)
    .filter(ticker => ['claude', 'gpt'].some(engine => {
      const engineRoot = join(root, ticker, engine);
      return existsSync(join(engineRoot, 'current.json')) ||
        (existsSync(join(engineRoot, 'meta.json')) && existsSync(join(engineRoot, 'decision.json')));
    }))
    .sort()
    .map(ticker => {
      const versions = loadCompany(ticker, root);
      const current = versions.gpt || versions.claude;
      return {
        ticker,
        name: current.meta.company_name || ticker,
        exchange: current.meta.exchange || null,
        versions,
      };
    });
}
