import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, join, resolve, sep } from 'node:path';

const data = await import('../src/lib/data.mjs');

function writeCompany(root, ticker, name, exchange, revenue) {
  const engineRoot = join(root, ticker, 'gpt');
  const folder = join(engineRoot, 'versions', `synthetic-${ticker.toLowerCase()}-v1`);
  mkdirSync(folder, { recursive: true });
  writeFileSync(join(engineRoot, 'current.json'), JSON.stringify({ run_id: `synthetic-${ticker.toLowerCase()}`, version_id: `synthetic-${ticker.toLowerCase()}-v1` }));
  writeFileSync(join(folder, 'meta.json'), JSON.stringify({ ticker, company_name: name, exchange, engine: 'gpt', model: 'test-model', sample: false }));
  writeFileSync(join(folder, 'decision.json'), JSON.stringify({ verdict: '판정 보류 (v0.1)', reason: 'test fixture' }));
  writeFileSync(join(folder, 'metrics.json'), JSON.stringify({ metrics: [{ metric_id: 'revenue_fy2025', value: revenue, unit: 'USD', status: 'ok' }] }));
  writeFileSync(join(folder, 'sources.json'), JSON.stringify({ sources: [{ source_id: `sec-${ticker}`, title: `${ticker} source`, url: 'https://www.sec.gov/', location: 'fixture' }] }));
}

test('company index discovers each published ticker and keeps its data separate', () => {
  assert.equal(typeof data.listCompanies, 'function', 'site data module must expose published companies');
  const temporary = mkdtempSync(join(tmpdir(), 'company-list-'));
  try {
    writeCompany(temporary, 'RKLB', 'Rocket Lab', 'NASDAQ', 100);
    writeCompany(temporary, 'VRT', 'Vertiv Holdings', 'NYSE', 200);
    writeCompany(temporary, 'MSFT', 'Microsoft', 'NASDAQ', 300);
    writeCompany(temporary, 'BAD TICKER', 'Bad', 'NYSE', 400);
    const companies = data.listCompanies(temporary);
    assert.deepEqual(companies.map(company => company.ticker), ['MSFT', 'RKLB', 'VRT']);
    assert.equal(companies.find(company => company.ticker === 'VRT').name, 'Vertiv Holdings');
    assert.equal(companies.find(company => company.ticker === 'VRT').exchange, 'NYSE');
    assert.equal(companies.find(company => company.ticker === 'VRT').versions.gpt.metrics[0].value, 200);
    assert.equal(companies.find(company => company.ticker === 'MSFT').versions.gpt.sources[0].source_id, 'sec-MSFT');
    assert.notEqual(companies.find(company => company.ticker === 'RKLB').versions.gpt.metrics[0].value, 200);
  } finally {
    const safe = resolve(temporary);
    assert.ok(safe.startsWith(resolve(tmpdir()) + sep) && basename(safe).startsWith('company-list-'));
    rmSync(safe, { recursive: true, force: true });
  }
});

test('company loader rejects traversal and mismatched metadata', () => {
  assert.throws(() => data.loadCompany(), /ticker/i);
  assert.throws(() => data.loadCompany('../RKLB'), /ticker/i);
  const temporary = mkdtempSync(join(tmpdir(), 'company-mismatch-'));
  try {
    writeCompany(temporary, 'VRT', 'Vertiv Holdings', 'NYSE', 200);
    writeFileSync(join(temporary, 'VRT', 'gpt', 'versions', 'synthetic-vrt-v1', 'meta.json'), JSON.stringify({ ticker: 'RKLB', company_name: 'Rocket Lab', engine: 'gpt', sample: false }));
    assert.throws(() => data.loadCompany('VRT', temporary), /ticker/i);
  } finally {
    const safe = resolve(temporary);
    assert.ok(safe.startsWith(resolve(tmpdir()) + sep) && basename(safe).startsWith('company-mismatch-'));
    rmSync(safe, { recursive: true, force: true });
  }
});

test('company loader rejects invalid or missing selected versions', () => {
  const temporary = mkdtempSync(join(tmpdir(), 'company-version-'));
  try {
    writeCompany(temporary, 'VRT', 'Vertiv Holdings', 'NYSE', 200);
    writeFileSync(join(temporary, 'VRT', 'gpt', 'current.json'), JSON.stringify({ version_id: '..' }));
    assert.throws(() => data.loadCompany('VRT', temporary), /version/i);
    writeFileSync(join(temporary, 'VRT', 'gpt', 'current.json'), JSON.stringify({ version_id: 'missing-version' }));
    assert.throws(() => data.loadCompany('VRT', temporary), /version/i);
  } finally {
    const safe = resolve(temporary);
    assert.ok(safe.startsWith(resolve(tmpdir()) + sep) && basename(safe).startsWith('company-version-'));
    rmSync(safe, { recursive: true, force: true });
  }
});
