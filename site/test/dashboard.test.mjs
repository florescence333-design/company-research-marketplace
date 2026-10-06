import test from 'node:test';
import assert from 'node:assert/strict';
import { buildFinancialDashboard, normalizeMarketSnapshot } from '../src/lib/dashboard.mjs';

const metric = (metric_id, value) => ({ metric_id, value, status: 'ok', unit: 'USD' });

test('six financial cards use SEC metrics and do not turn two losses into a positive quality ratio', () => {
  const metrics = [
    metric('revenue_growth_fy2025', 37.96), metric('revenue_cagr_3y', 41.82),
    metric('operating_margin_fy2025', -38.03),
    metric('operating_cash_flow_fy2024', -48890000), metric('operating_cash_flow_fy2025', -165521000),
    metric('free_cash_flow_fy2025', -321806000), metric('liabilities_to_equity', 19.91),
    metric('net_income_fy2025', -198209000),
  ];
  const result = buildFinancialDashboard(metrics);
  assert.equal(result.cards.length, 6);
  assert.match(result.cards[2].value, /현금유출 확대/);
  assert.doesNotMatch(result.cards[2].value, /%/);
  assert.match(result.cards[5].value, /비율 의미 없음/);
  assert.ok(result.warnings.some(w => w.includes('잉여현금흐름')));
  assert.ok(result.warnings.some(w => w.includes('재고·매출채권')));
});

test('missing market data remains unknown and loss-making PER is not shown as a numeric multiple', () => {
  const missing = normalizeMarketSnapshot(null, [metric('eps_ttm', -0.26)]);
  assert.equal(missing.price, null);
  assert.equal(missing.market_cap, null);
  assert.equal(missing.range_52w, null);
  assert.equal(missing.pe_ttm, '적자 기업 · 비율 의미 없음');
  const provided = normalizeMarketSnapshot({ price: 42, market_cap: 1000000000, pe_ttm: 30,
    range_52w: { low: 20, high: 50 }, as_of: '2026-10-06', source: 'Twelve Data' }, [metric('eps_ttm', -0.26)]);
  assert.equal(provided.price, 42);
  assert.equal(provided.pe_ttm, '적자 기업 · 비율 의미 없음');
});
