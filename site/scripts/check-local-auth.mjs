import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const values = Object.fromEntries(readFileSync(resolve(root, '.dev.vars'), 'utf8').split(/\r?\n/).filter(Boolean).map(line => {
  const index = line.indexOf('=');
  return [line.slice(0, index), line.slice(index + 1)];
}));
const base = 'http://127.0.0.1:8788';
const publicInfo = await fetch(`${base}/build-info.json`);
assert.equal(publicInfo.status, 200);
assert.deepEqual(Object.keys(await publicInfo.json()).sort(), ['built_at', 'commit_sha']);
assert.equal(publicInfo.headers.get('Cache-Control'), 'no-store');

for (const path of ['/', '/company/RKLB/', '/_astro/example.css', '/data/companies/RKLB/gpt/meta.json']) {
  const response = await fetch(`${base}${path}`, { redirect: 'manual' });
  assert.equal(response.status, 302, `expected ${path} to require login`);
}
const loginPage = await fetch(`${base}/login`);
assert.equal(loginPage.status, 200);
const login = await fetch(`${base}/login`, {
  method: 'POST', redirect: 'manual',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({ password: values.AUTH_PASSWORD }),
});
assert.equal(login.status, 303);
const cookie = login.headers.get('set-cookie').split(';')[0];
const protectedPage = await fetch(`${base}/company/RKLB/`, { headers: { Cookie: cookie }, redirect: 'manual' });
assert.equal(protectedPage.status, 200);
assert.equal(protectedPage.headers.get('Cache-Control'), 'private, no-store');
const csp = protectedPage.headers.get('Content-Security-Policy');
assert.match(csp, /script-src 'self' https:\/\/s3\.tradingview\.com;/);
assert.match(csp, /frame-src https:\/\/\*\.tradingview\.com https:\/\/tradingview-widget\.com https:\/\/\*\.tradingview-widget\.com;/);
assert.doesNotMatch(csp, /script-src[^;]*https:\/\/(?!s3\.tradingview\.com)/);
const invalid = await fetch(`${base}/company/RKLB/`, { headers: { Cookie: cookie + 'broken' }, redirect: 'manual' });
assert.equal(invalid.status, 302);
console.log('Pages local auth passed: public build info, protected content, signed session, invalid cookie');
