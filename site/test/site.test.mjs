import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));

test('static dashboard and RKLB detail show their actual data status', () => {
  const index = readFileSync(join(root, 'dist/index.html'), 'utf8');
  const company = readFileSync(join(root, 'dist/company/RKLB/index.html'), 'utf8');
  assert.match(index, /RKLB/);
  assert.match(company, /판정 보류 \(v0\.1\)/);
  if (existsSync(join(root, 'data/companies/RKLB/gpt/meta.json'))) {
    assert.match(company, /SEC Company Facts/);
    assert.doesNotMatch(company, /class="badge sample">샘플 데이터/);
  } else {
    assert.match(company, /샘플 데이터/);
  }
  assert.match(company, /보고서/);
  assert.match(company, /비교/);
});

test('public build info contains only commit hash and build time', () => {
  const info = JSON.parse(readFileSync(join(root, 'dist/build-info.json'), 'utf8'));
  assert.deepEqual(Object.keys(info).sort(), ['built_at', 'commit_sha']);
  assert.match(info.commit_sha, /^[a-f0-9]{40}$/);
  assert.match(info.built_at, /^\d{4}-\d{2}-\d{2}T/);
});
