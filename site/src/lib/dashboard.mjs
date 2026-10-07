const valid = value => Number.isFinite(value);
const million = value => `${(value / 1_000_000).toLocaleString('ko-KR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })}M USD`;
const percent = value => `${value.toLocaleString('ko-KR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`;

export function buildFinancialDashboard(metrics = []) {
  const facts = new Map(metrics.filter(m => m?.status === 'ok' && valid(m.value)).map(m => [m.metric_id, m.value]));
  const get = id => facts.get(id);
  const fiscalYear = Math.max(0, ...[...facts.keys()].filter(id => /^revenue_fy\d{4}$/.test(id)).map(id => Number(id.slice(-4))));
  const fy = (name, year = fiscalYear) => year ? get(`${name}_fy${year}`) : undefined;
  const yearLabel = fiscalYear ? `${fiscalYear}년` : '회계연도 확인 불가';
  const growth = fy('revenue_growth');
  const cagr = get('revenue_cagr_3y');
  const margin = fy('operating_margin');
  const ocf = fy('operating_cash_flow');
  const priorOcf = fy('operating_cash_flow', fiscalYear - 1);
  const fcf = fy('free_cash_flow');
  const debtRatio = get('liabilities_to_equity');
  const netIncome = fy('net_income');
  const ocfComparable = valid(ocf) && valid(priorOcf) && priorOcf > 0;
  const ocfGrowth = ocfComparable ? (ocf / priorOcf - 1) * 100 : null;
  const ocfState = !valid(ocf) || !valid(priorOcf) ? '확인 불가'
    : !ocfComparable ? (ocf < priorOcf ? '현금유출 확대' : '현금흐름 개선') : percent(ocfGrowth);
  const incomeQuality = !valid(ocf) || !valid(netIncome) ? '확인 불가'
    : netIncome <= 0 ? '적자 · 비율 의미 없음' : `${(ocf / netIncome).toFixed(2)}배`;
  const cards = [
    { id: 'revenue_growth', label: '매출 성장률', value: valid(growth) ? percent(growth) : '확인 불가', detail: valid(cagr) ? `3년 CAGR ${percent(cagr)}` : '3년 CAGR 확인 불가' },
    { id: 'operating_margin', label: '영업이익률', value: valid(margin) ? percent(margin) : '확인 불가', detail: valid(margin) && margin < 0 ? '영업손실 상태' : yearLabel },
    { id: 'ocf_growth', label: 'OCF 성장률', value: ocfState, detail: valid(ocf) && valid(priorOcf) ? `${million(priorOcf)} → ${million(ocf)}` : '연도 비교 자료 부족' },
    { id: 'free_cash_flow', label: '잉여현금흐름', value: valid(fcf) ? million(fcf) : '확인 불가', detail: `${yearLabel} · 영업현금흐름 − 설비투자` },
    { id: 'liabilities_ratio', label: '부채비율', value: valid(debtRatio) ? percent(debtRatio) : '확인 불가', detail: '총부채 ÷ 자기자본 · 최근 분기말' },
    { id: 'income_quality', label: '순이익의 질', value: incomeQuality, detail: valid(ocf) && valid(netIncome) ? `영업현금흐름 ${million(ocf)} · 순손익 ${million(netIncome)}` : '현금흐름 또는 순손익 없음' },
  ];
  const warnings = [];
  if (valid(fcf) && fcf < 0) warnings.push(`${yearLabel} 잉여현금흐름 적자`);
  if (valid(ocf) && valid(priorOcf) && ocf < priorOcf) warnings.push('영업현금흐름 악화');
  const inventoryCurrent = fy('inventory'), inventoryPrior = fy('inventory', fiscalYear - 1);
  const receivablesCurrent = fy('accounts_receivable'), receivablesPrior = fy('accounts_receivable', fiscalYear - 1);
  if (valid(growth) && valid(inventoryCurrent) && valid(inventoryPrior) && inventoryPrior > 0 && (inventoryCurrent / inventoryPrior - 1) * 100 > growth)
    warnings.push('재고 증가율이 매출 성장률 초과');
  if (valid(growth) && valid(receivablesCurrent) && valid(receivablesPrior) && receivablesPrior > 0 && (receivablesCurrent / receivablesPrior - 1) * 100 > growth)
    warnings.push('매출채권 증가율이 매출 성장률 초과');
  if (!valid(inventoryCurrent) || !valid(inventoryPrior) || !valid(receivablesCurrent) || !valid(receivablesPrior))
    warnings.push('재고·매출채권 경고 미평가 · 데이터 없음');
  return { cards, warnings };
}

export function normalizeMarketSnapshot(snapshot, metrics = []) {
  const eps = metrics.find(m => m.metric_id === 'eps_ttm' && m.status === 'ok')?.value;
  const range = snapshot?.range_52w;
  return {
    price: valid(snapshot?.price) && snapshot.price > 0 ? snapshot.price : null,
    market_cap: valid(snapshot?.market_cap) && snapshot.market_cap > 0 ? snapshot.market_cap : null,
    pe_ttm: valid(eps) && eps <= 0 ? '적자 기업 · 비율 의미 없음'
      : valid(snapshot?.pe_ttm) && snapshot.pe_ttm > 0 ? snapshot.pe_ttm : null,
    range_52w: valid(range?.low) && valid(range?.high) && range.low > 0 && range.high >= range.low ? { low: range.low, high: range.high } : null,
    as_of: typeof snapshot?.as_of === 'string' ? snapshot.as_of : null,
    source: snapshot?.source === 'Twelve Data' ? snapshot.source : null,
  };
}
