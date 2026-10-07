import test from 'node:test';
import assert from 'node:assert/strict';
import { buildFinancialDashboard, normalizeMarketSnapshot } from '../src/lib/dashboard.mjs';

const metric = (metric_id, value) => ({ metric_id, value, status: 'ok', unit: 'USD' });

test('six financial cards use SEC metrics and do not turn two losses into a positive quality ratio', () => {
  const metrics = [
    metric('revenue_fy2025', 601799000),
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

test('MSFT cards select FY2026 values instead of FY2025 values', () => {
  const result = buildFinancialDashboard([
    metric('revenue_fy2025', 281724000000), metric('revenue_fy2026', 331999000000),
    metric('revenue_growth_fy2025', 14.9), metric('revenue_growth_fy2026', 17.8),
    metric('operating_margin_fy2025', 45.6), metric('operating_margin_fy2026', 46.8),
    metric('operating_cash_flow_fy2025', 136162000000), metric('operating_cash_flow_fy2026', 182935000000),
    metric('free_cash_flow_fy2025', 71611000000), metric('free_cash_flow_fy2026', 66987000000),
    metric('net_income_fy2025', 101832000000), metric('net_income_fy2026', 133749000000),
  ]);
  assert.equal(result.cards[0].value, '17.8%');
  assert.equal(result.cards[1].value, '46.8%');
  assert.equal(result.cards[1].detail, '2026년');
  assert.equal(result.cards[3].value, '66,987.0M USD');
  assert.match(result.cards[3].detail, /^2026년/);
  assert.match(result.cards[5].detail, /133,749.0M USD/);
});

test('AAPL, VRT, and RKLB cards remain on FY2025', () => {
  for (const [ticker, fcf] of [['AAPL', 98767000000], ['VRT', 1893800000], ['RKLB', -321806000]]) {
    const result = buildFinancialDashboard([
      metric('revenue_fy2024', 100000000), metric('revenue_fy2025', 120000000),
      metric('operating_margin_fy2025', 12), metric('free_cash_flow_fy2025', fcf),
    ]);
    assert.equal(result.cards[1].detail, '2025년', ticker);
    assert.match(result.cards[3].detail, /^2025년/, ticker);
  }
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
