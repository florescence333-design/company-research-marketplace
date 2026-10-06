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
  const engineRoot = join(root, 'data/companies/RKLB/gpt');
  const pointerPath = join(engineRoot, 'current.json');
  const pointer = existsSync(pointerPath) ? JSON.parse(readFileSync(pointerPath, 'utf8')) : null;
  const versionRoot = pointer ? join(engineRoot, 'versions', pointer.version_id || pointer.run_id) : engineRoot;
  if (existsSync(join(versionRoot, 'meta.json'))) {
    assert.match(company, /SEC Company Facts/);
    assert.doesNotMatch(company, /class="badge sample">샘플 데이터/);
    if (existsSync(join(versionRoot, 'report-items.json'))) {
      assert.match(company, /S16 최종 결론/);
      assert.equal((company.match(/class="report-section"/g) || []).length, 16, 'each Master Template section has a readable report block');
    }
    if (pointer) assert.ok(company.includes(pointer.run_id), 'built page must contain selected published run');
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
