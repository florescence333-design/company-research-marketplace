import test from 'node:test';
import assert from 'node:assert/strict';
import { compareReports } from '../src/lib/comparison.mjs';

test('comparison distinguishes missing custom sections and sourced sections', () => {
  const rows = compareReports({
    claude: { reportItems: [{ section_id: 'S04', title: '사업', status: 'partial', body: 'one', source_ids: [] }] },
    gpt: { reportItems: [{ section_id: 'S04', title: '사업', status: 'partial', body: 'two', source_ids: ['web-a'], subsections: [{ section_id: 'S04-A', title: '신설', status: 'partial', body: 'three', source_ids: ['web-a'] }] }] },
  });
  assert.equal(rows.length, 2);
  assert.equal(rows[0].difference, '웹 근거 수 차이');
  assert.equal(rows[1].claude.status, '없음');
  assert.equal(rows[1].difference, '작성 상태 차이');
});

test('comparison shows validated complete sections', () => {
  const rows = compareReports({ gpt: { reportItems: [{ section_id: 'S01', title: '기본 정보', status: 'complete', body: 'text', source_ids: ['web-a'] }] } });
  assert.equal(rows[0].gpt.status, '작성 완료');
});
