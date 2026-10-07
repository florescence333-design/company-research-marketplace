import test from 'node:test';
import assert from 'node:assert/strict';
import { listCompanies } from '../src/lib/data.mjs';

test('published page model excludes local market snapshot numbers', () => {
  for (const { versions } of listCompanies()) {
    for (const version of Object.values(versions)) {
      assert.equal(Object.hasOwn(version, 'market'), false);
    }
  }
});
