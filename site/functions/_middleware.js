import { configured, hasValidSession } from './auth.js';

export async function onRequest(context) {
  const path = new URL(context.request.url).pathname;
  if (path === '/build-info.json') {
    const response = await context.next();
    const headers = new Headers(response.headers);
    headers.set('Cache-Control', 'no-store');
    return new Response(response.body, { status: response.status, headers });
  }
  if (path === '/login') return context.next();
  if (!configured(context.env)) return new Response('Authentication unavailable', { status: 503, headers: { 'Cache-Control': 'no-store' } });
  if (!await hasValidSession(context.request, context.env)) return Response.redirect(new URL('/login', context.request.url), 302);
  const response = await context.next();
  const headers = new Headers(response.headers);
  headers.set('Cache-Control', 'private, no-store');
  return new Response(response.body, { status: response.status, headers });
}
