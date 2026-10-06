import { configured, hasValidSession } from './auth.js';

const CSP = "default-src 'self'; script-src 'self' https://s3.tradingview.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: https://*.tradingview.com; frame-src https://*.tradingview.com https://tradingview-widget.com https://*.tradingview-widget.com; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'";

function secure(response, cache) {
  const headers = new Headers(response.headers);
  headers.set('Cache-Control', cache);
  headers.set('Content-Security-Policy', CSP);
  return new Response(response.body, { status: response.status, headers });
}

export async function onRequest(context) {
  const path = new URL(context.request.url).pathname;
  if (path === '/build-info.json') {
    return secure(await context.next(), 'no-store');
  }
  if (path === '/login') return secure(await context.next(), 'no-store');
  if (!configured(context.env)) return secure(new Response('Authentication unavailable', { status: 503 }), 'no-store');
  if (!await hasValidSession(context.request, context.env)) return secure(Response.redirect(new URL('/login', context.request.url), 302), 'no-store');
  return secure(await context.next(), 'private, no-store');
}
