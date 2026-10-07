import test from 'node:test';
import assert from 'node:assert/strict';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { basename, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));

test('static dashboard and RKLB detail show their actual data status', () => {
  const index = readFileSync(join(root, 'dist/index.html'), 'utf8');
  const company = readFileSync(join(root, 'dist/company/RKLB/index.html'), 'utf8');
  assert.match(index, /RKLB/);
  assert.match(company, /판정 보류 \(v0\.1\)/);
  const base = process.env.SITE_DATA_DIR ? join(process.env.SITE_DATA_DIR, 'RKLB') : join(root, 'data/companies/RKLB');
  const selectedEngine = ['gpt', 'claude'].find(engine => existsSync(join(base, engine, 'current.json'))) || 'gpt';
  const engineRoot = join(base, selectedEngine);
  const pointerPath = join(engineRoot, 'current.json');
  const pointer = existsSync(pointerPath) ? JSON.parse(readFileSync(pointerPath, 'utf8')) : null;
  const versionRoot = pointer ? join(engineRoot, 'versions', pointer.version_id || pointer.run_id) : engineRoot;
  if (existsSync(join(versionRoot, 'meta.json'))) {
    const selectedMeta = JSON.parse(readFileSync(join(versionRoot, 'meta.json'), 'utf8'));
    const anyAiReport = ['gpt', 'claude'].some(engine => {
      const base = process.env.SITE_DATA_DIR ? join(process.env.SITE_DATA_DIR, 'RKLB', engine) : join(root, 'data/companies/RKLB', engine);
      const currentPath = join(base, 'current.json');
      if (!existsSync(currentPath)) return false;
      const selected = JSON.parse(readFileSync(currentPath, 'utf8'));
      const metaPath = join(base, 'versions', selected.version_id || selected.run_id, 'meta.json');
      return existsSync(metaPath) && Boolean(JSON.parse(readFileSync(metaPath, 'utf8')).model);
    });
    assert.doesNotMatch(index, /class="badge sample">샘플 데이터/);
    assert.match(index, anyAiReport ? /SEC 공시 기반 AI 분석/ : /SEC 공시 기반 초안/);
    assert.match(company, /SEC Company Facts/);
    assert.doesNotMatch(company, /class="badge sample">샘플 데이터/);
    assert.match(company, selectedMeta.model ? /AI 분석 포함/ : /공시·코드 초안 · AI 평가 미실행/);
    if (existsSync(join(versionRoot, 'report-items.json'))) {
      assert.match(company, /S16 최종 결론/);
      assert.equal((company.match(/class="report-section"/g) || []).length, 16, 'each Master Template section has a readable report block');
    }
    if (existsSync(join(versionRoot, 'sources.json'))) {
      const sources = JSON.parse(readFileSync(join(versionRoot, 'sources.json'), 'utf8')).sources;
      assert.equal((company.match(/class="source-row"/g) || []).length, sources.length, 'every source is identified in the source tab');
      assert.match(company, /<code[^>]*>sec-001<\/code>/);
    }
    if (pointer) assert.ok(company.includes(pointer.run_id), 'built page must contain selected published run');
  } else {
    assert.match(company, /샘플 데이터/);
  }
  assert.match(company, /보고서/);
  assert.match(company, /비교/);
  assert.match(company, /기준 보고서 대비 정량 분석\(제품별 원가·고객 경제성 등\)은 보강 예정/);
  if (existsSync(join(root, 'data/companies/RKLB/gpt/current.json'))) {
    assert.match(company, /작성 완료/);
  }
});

test('public build info contains only commit hash and build time', () => {
  const info = JSON.parse(readFileSync(join(root, 'dist/build-info.json'), 'utf8'));
  assert.deepEqual(Object.keys(info).sort(), ['built_at', 'commit_sha']);
  if (existsSync(join(root, '..', '.git')) || existsSync(join(root, '.git')) || process.env.CF_PAGES_COMMIT_SHA) {
    assert.match(info.commit_sha, /^[a-f0-9]{40}$/);
  } else {
    assert.equal(info.commit_sha, null);
  }
  assert.match(info.built_at, /^\d{4}-\d{2}-\d{2}T/);
});

test('market widgets stay above the tabs while SEC cards live inside finance', () => {
  const company = readFileSync(join(root, 'dist/company/RKLB/index.html'), 'utf8');
  const tabs = company.indexOf('role="tablist"');
  const finance = company.indexOf('data-panel="1"');
  assert.ok(company.indexOf('id="tradingview-symbol-info"') > 0);
  assert.ok(company.indexOf('id="tradingview-fundamentals"') > 0);
  assert.ok(company.indexOf('id="tradingview-symbol-info"') < tabs);
  assert.ok(company.indexOf('id="financial-cards"') > finance);
  assert.ok(company.indexOf('id="warning-line"') > finance);
  assert.doesNotMatch(company, /data-metric="(?:price|market_cap|pe_ttm|range_52w|dividend_yield)"/);
});

test('plugin workspace without Git records no commit rather than failing the build', () => {
  const temporary = mkdtempSync(join(tmpdir(), 'company-build-info-'));
  try {
    const site = join(temporary, 'site');
    mkdirSync(join(site, 'scripts'), { recursive: true });
    copyFileSync(join(root, 'scripts', 'write-build-info.mjs'), join(site, 'scripts', 'write-build-info.mjs'));
    const env = { ...process.env };
    delete env.CF_PAGES_COMMIT_SHA;
    const result = spawnSync(process.execPath, [join(site, 'scripts', 'write-build-info.mjs')], {
      cwd: site, env, encoding: 'utf8',
    });
    assert.equal(result.status, 0, result.stderr);
    const info = JSON.parse(readFileSync(join(site, 'public', 'build-info.json'), 'utf8'));
    assert.deepEqual(Object.keys(info).sort(), ['built_at', 'commit_sha']);
    assert.equal(info.commit_sha, null);
  } finally {
    const resolved = resolve(temporary);
    assert.ok(resolved.startsWith(resolve(tmpdir()) + sep) && basename(resolved).startsWith('company-build-info-'));
    rmSync(resolved, { recursive: true, force: true });
  }
});
