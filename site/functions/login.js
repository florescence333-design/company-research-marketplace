import { configured, issueCookie, matchesPassword } from './auth.js';

const form = `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>로그인 · Company Research</title><style>body{font:15px system-ui;background:#101918;color:#e8eee8;display:grid;place-items:center;min-height:100vh;margin:0}main{width:min(360px,calc(100% - 40px));background:#172320;border:1px solid #30413e;border-radius:14px;padding:32px}h1{font-size:22px}p{color:#9bb0a5;font-size:13px;line-height:1.6}input,button{box-sizing:border-box;width:100%;padding:12px;border-radius:7px;font:inherit}input{background:#0e1916;border:1px solid #476055;color:white}button{background:#b7e4cd;border:0;margin-top:14px;font-weight:700;cursor:pointer}</style></head><body><main><h1>Company Research</h1><p>사이트 비밀번호를 입력해 주세요.</p><form method="post" action="/login"><label for="password">비밀번호</label><input id="password" name="password" type="password" autocomplete="current-password" required><button>열기</button></form></main></body></html>`;

export async function onRequest(context) {
  if (!configured(context.env)) return new Response('Authentication unavailable', { status: 503, headers: { 'Cache-Control': 'no-store' } });
  if (context.request.method === 'GET') return new Response(form, { headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' } });
  if (context.request.method !== 'POST') return new Response('Method not allowed', { status: 405 });
  let submitted;
  try {
    const fields = await context.request.formData();
    submitted = String(fields.get('password') || '');
  } catch {
    return new Response('Invalid request', { status: 400 });
  }
  if (!matchesPassword(submitted, context.env.AUTH_PASSWORD)) return new Response('Wrong password', { status: 401, headers: { 'Cache-Control': 'no-store' } });
  const headers = new Headers({ 'Location': '/', 'Cache-Control': 'no-store' });
  headers.append('Set-Cookie', await issueCookie(context.env));
  return new Response(null, { status: 303, headers });
}
