import test from 'node:test';
import assert from 'node:assert/strict';
import { loadCompany } from '../src/lib/data.mjs';

test('published page model excludes local market snapshot numbers', () => {
  const versions = loadCompany('RKLB');
  for (const version of Object.values(versions)) {
    assert.equal(Object.hasOwn(version, 'market'), false);
  }
});
