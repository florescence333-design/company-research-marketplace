import test from 'node:test';
import assert from 'node:assert/strict';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { basename, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { listCompanies } from '../src/lib/data.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));

test('static dashboard and every published detail show their actual data status', () => {
  const index = readFileSync(join(root, 'dist/index.html'), 'utf8');
  const published = listCompanies();
  assert.ok(published.length > 0, 'expected at least one selected company');
  for (const listed of published) {
    const { ticker, versions } = listed;
    const company = readFileSync(join(root, 'dist/company', ticker, 'index.html'), 'utf8');
    assert.ok(index.includes(`/company/${ticker}/`), `${ticker} must appear in the index`);
    assert.match(company, /판정 보류 \(v0\.1\)/);
    const selected = versions.gpt || versions.claude;
    const base = process.env.SITE_DATA_DIR ? join(process.env.SITE_DATA_DIR, ticker) : join(root, 'data/companies', ticker);
    const selectedEngine = versions.gpt ? 'gpt' : 'claude';
    const pointerPath = join(base, selectedEngine, 'current.json');
    const pointer = existsSync(pointerPath) ? JSON.parse(readFileSync(pointerPath, 'utf8')) : null;
    if (selected.meta.sample) {
      assert.match(company, /샘플 데이터/);
    } else {
      assert.match(company, /SEC Company Facts/);
      assert.doesNotMatch(company, /class="badge sample">샘플 데이터/);
      assert.match(company, selected.meta.model ? /AI 분석 포함/ : /공시·코드 초안 · AI 평가 미실행/);
      if (selected.reportItems.length) {
        assert.match(company, /S16 최종 결론/);
        assert.equal((company.match(/class="report-section"/g) || []).length, 16, `${ticker}: sixteen report sections`);
      }
      assert.equal((company.match(/class="source-row"/g) || []).length, selected.sources.length,
        `${ticker}: every source is identified in the source tab`);
      if (selected.sources.length) assert.match(company, /<code[^>]*>sec-001<\/code>/);
      if (pointer) assert.ok(company.includes(pointer.run_id), `${ticker}: built page must contain selected run`);
    }
    assert.match(company, /보고서/);
    assert.match(company, /비교/);
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
  for (const { ticker } of listCompanies()) {
    const company = readFileSync(join(root, 'dist/company', ticker, 'index.html'), 'utf8');
    const tabs = company.indexOf('role="tablist"');
    const finance = company.indexOf('data-panel="1"');
    assert.ok(company.indexOf('id="tradingview-symbol-info"') > 0);
    assert.ok(company.indexOf('id="tradingview-fundamentals"') > 0);
    assert.ok(company.indexOf('id="tradingview-symbol-info"') < tabs);
    assert.ok(company.indexOf('id="financial-cards"') > finance);
    assert.ok(company.indexOf('id="warning-line"') > finance);
    assert.doesNotMatch(company, /data-metric="(?:price|market_cap|pe_ttm|range_52w|dividend_yield)"/);
  }
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
