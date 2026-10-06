// Verify a Pages deployment without site credentials.

import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export async function checkDeployment(base, expectedSha) {
  const origin = new URL(base);
  if (origin.pathname !== '/' || !(['https:'].includes(origin.protocol) ||
      (origin.protocol === 'http:' && ['127.0.0.1', 'localhost'].includes(origin.hostname)))) {
    throw new Error('배포 주소는 HTTPS 사이트 루트여야 합니다');
  }
  if (!/^[a-f0-9]{40}$/.test(expectedSha)) throw new Error('기대 커밋 해시 형식 오류');

  const infoResponse = await fetch(new URL('/build-info.json', origin), {
    redirect: 'manual', signal: AbortSignal.timeout(10000)
  });
  if (infoResponse.status !== 200) throw new Error('공개 빌드 정보 조회 실패');
  if (!infoResponse.headers.get('cache-control')?.includes('no-store')) throw new Error('빌드 정보 캐시 설정 확인 실패');
  const info = await infoResponse.json();
  if (Object.keys(info).sort().join(',') !== 'built_at,commit_sha' || info.commit_sha !== expectedSha ||
      !Number.isFinite(Date.parse(info.built_at))) throw new Error('빌드 정보의 필드·커밋 해시 불일치');

  for (const path of ['/', '/company/RKLB/', '/data/companies/RKLB/gpt/current.json']) {
    const response = await fetch(new URL(path, origin), {
      redirect: 'manual', signal: AbortSignal.timeout(10000)
    });
    const location = response.headers.get('location');
    const login = location && new URL(location, origin);
    if (response.status !== 302 || !login || login.origin !== origin.origin || login.pathname !== '/login') {
      throw new Error(`인증 없는 ${path} 보호 확인 실패`);
    }
  }
  const login = await fetch(new URL('/login', origin), {
    redirect: 'manual', signal: AbortSignal.timeout(10000)
  });
  if (login.status !== 200) throw new Error('로그인 페이지 확인 실패');
  return { commit_sha: info.commit_sha, protected: true };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [, , base, expectedSha] = process.argv;
  if (!base || !expectedSha) {
    console.error('사용법: node scripts/check-deploy.mjs <사이트 루트 URL> <기대 사이트 커밋 SHA>');
    process.exitCode = 2;
  } else {
    try {
      const result = await checkDeployment(base, expectedSha);
      console.log(`배포 해시·비인증 경로 보호 확인: ${result.commit_sha}`);
    } catch (error) {
      console.error(`배포 확인 실패: ${error.message}`);
      process.exitCode = 1;
    }
  }
}
