const encoder = new TextEncoder();
const COOKIE_NAME = 'research_session';
const SESSION_SECONDS = 30 * 24 * 60 * 60;

function constantTimeEquals(left, right) {
  const a = encoder.encode(left);
  const b = encoder.encode(right);
  let different = a.length ^ b.length;
  for (let index = 0; index < Math.max(a.length, b.length); index++) {
    different |= (a[index] || 0) ^ (b[index] || 0);
  }
  return different === 0;
}

function toBase64Url(bytes) {
  return btoa(String.fromCharCode(...bytes)).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');
}

function fromBase64Url(value) {
  const normalized = value.replaceAll('-', '+').replaceAll('_', '/');
  return Uint8Array.from(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')), character => character.charCodeAt(0));
}

async function hmac(secret, value) {
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', key, encoder.encode(value)));
}

export function configured(env) {
  return Boolean(env?.AUTH_PASSWORD && env?.SESSION_SECRET && env?.SESSION_VERSION);
}

export function matchesPassword(candidate, expected) {
  return constantTimeEquals(candidate, expected);
}

export async function issueCookie(env) {
  const payload = toBase64Url(encoder.encode(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + SESSION_SECONDS, version: env.SESSION_VERSION })));
  const signature = toBase64Url(await hmac(env.SESSION_SECRET, payload));
  return `${COOKIE_NAME}=${payload}.${signature}; Path=/; Max-Age=${SESSION_SECONDS}; HttpOnly; Secure; SameSite=Lax`;
}

export async function hasValidSession(request, env) {
  const cookieHeader = request.headers.get('Cookie') || '';
  const cookie = cookieHeader.split(';').map(part => part.trim()).find(part => part.startsWith(`${COOKIE_NAME}=`));
  if (!cookie) return false;
  try {
    const [payload, signature, extra] = cookie.slice(COOKIE_NAME.length + 1).split('.');
    if (!payload || !signature || extra) return false;
    const expected = toBase64Url(await hmac(env.SESSION_SECRET, payload));
    if (!constantTimeEquals(signature, expected)) return false;
    const data = JSON.parse(new TextDecoder().decode(fromBase64Url(payload)));
    return data.version === env.SESSION_VERSION && Number.isInteger(data.exp) && data.exp > Math.floor(Date.now() / 1000);
  } catch {
    return false;
  }
}
