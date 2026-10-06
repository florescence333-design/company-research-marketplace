import test from 'node:test';
import assert from 'node:assert/strict';
import { onRequest as guard } from '../functions/_middleware.js';
import { onRequest as login } from '../functions/login.js';

const secrets = { AUTH_PASSWORD: 'long-random-test-password', SESSION_SECRET: 'test-signing-secret', SESSION_VERSION: 'v1' };
const ctx = (url, env = secrets, cookie = '', method = 'GET', body) => ({
  request: new Request(url, { method, headers: cookie ? { Cookie: cookie, 'Content-Type': 'application/x-www-form-urlencoded' } : { 'Content-Type': 'application/x-www-form-urlencoded' }, body }),
  env,
  next: async () => new Response('protected content'),
});

test('only the exact build-info path is public', async () => {
  const publicResponse = await guard(ctx('https://example.test/build-info.json', {}));
  assert.equal(publicResponse.status, 200);
  assert.equal(publicResponse.headers.get('Cache-Control'), 'no-store');
  const other = await guard(ctx('https://example.test/data/companies/RKLB/meta.json'));
  assert.equal(other.status, 302);
  assert.equal(other.headers.get('Location'), 'https://example.test/login');
});

test('missing secrets fail closed', async () => {
  const response = await guard(ctx('https://example.test/data.json', {}));
  assert.equal(response.status, 503);
  assert.notEqual(await response.text(), 'protected content');
});

test('signed cookie grants access and version change revokes it', async () => {
  const form = new URLSearchParams({ password: secrets.AUTH_PASSWORD });
  const loggedIn = await login(ctx('https://example.test/login', secrets, '', 'POST', form));
  assert.equal(loggedIn.status, 303);
  const setCookie = loggedIn.headers.get('Set-Cookie');
  assert.match(setCookie, /HttpOnly/);
  assert.match(setCookie, /Secure/);
  assert.match(setCookie, /SameSite=Lax/);
  assert.match(setCookie, /Max-Age=2592000/);
  const cookie = setCookie.split(';')[0];
  const authorized = await guard(ctx('https://example.test/data.json', secrets, cookie));
  assert.equal(authorized.status, 200);
  assert.equal(authorized.headers.get('Cache-Control'), 'private, no-store');
  const revoked = await guard(ctx('https://example.test/data.json', { ...secrets, SESSION_VERSION: 'v2' }, cookie));
  assert.equal(revoked.status, 302);
});

test('wrong password does not issue a session', async () => {
  const form = new URLSearchParams({ password: 'wrong' });
  const response = await login(ctx('https://example.test/login', secrets, '', 'POST', form));
  assert.equal(response.status, 401);
  assert.equal(response.headers.get('Set-Cookie'), null);
});
