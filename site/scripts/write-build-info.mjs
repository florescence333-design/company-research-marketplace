import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const siteRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = existsSync(join(siteRoot, '.git')) ? siteRoot : resolve(siteRoot, '..');
const sha = process.env.CF_PAGES_COMMIT_SHA ||
  (existsSync(join(repoRoot, '.git'))
    ? execFileSync('git', ['-c', `safe.directory=${repoRoot}`, 'rev-parse', 'HEAD'], { cwd: repoRoot, encoding: 'utf8' }).trim()
    : null);
if (sha !== null && !/^[a-f0-9]{40}$/.test(sha)) throw new Error('Expected a full Git commit SHA');
const info = { commit_sha: sha, built_at: new Date().toISOString() };
mkdirSync(join(siteRoot, 'public'), { recursive: true });
writeFileSync(join(siteRoot, 'public', 'build-info.json'), JSON.stringify(info) + '\n');
