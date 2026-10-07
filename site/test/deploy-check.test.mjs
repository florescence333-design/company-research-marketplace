import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { checkDeployment } from '../scripts/check-deploy.mjs';

const sha = 'a'.repeat(40);

async function serve(openCompany = false, ticker = 'RKLB') {
  const server = createServer((request, response) => {
    if (request.url === '/build-info.json') {
      response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      response.end(JSON.stringify({ commit_sha: sha, built_at: '2026-10-07T00:00:00Z' }));
    } else if (request.url === '/login') {
      response.writeHead(200, { 'Content-Type': 'text/html' });
      response.end('login');
    } else if (request.url === `/company/${ticker}/` && openCompany) {
      response.writeHead(200);
      response.end('public report');
    } else {
      response.writeHead(302, { Location: '/login' });
      response.end();
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { server, base: `http://127.0.0.1:${server.address().port}` };
}

test('deployment checker accepts matching public build hash and protected report', async () => {
  const { server, base } = await serve();
  try {
    assert.deepEqual(await checkDeployment(base, sha, ['RKLB']), { commit_sha: sha, protected: true });
  } finally {
    server.close();
  }
});

test('deployment checker accepts an installation with only AAPL', async () => {
  const { server, base } = await serve(false, 'AAPL');
  try {
    assert.deepEqual(await checkDeployment(base, sha, ['AAPL']), { commit_sha: sha, protected: true });
  } finally {
    server.close();
  }
});

test('deployment checker rejects a publicly readable company report', async () => {
  const { server, base } = await serve(true);
  try {
    await assert.rejects(checkDeployment(base, sha, ['RKLB']), /보호/);
  } finally {
    server.close();
  }
});

test('deployment checker rejects a stale build hash', async () => {
  const { server, base } = await serve();
  try {
    await assert.rejects(checkDeployment(base, 'b'.repeat(40), ['RKLB']), /커밋 해시/);
  } finally {
    server.close();
  }
});
