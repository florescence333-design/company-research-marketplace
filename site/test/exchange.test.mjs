import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeExchange } from '../src/lib/exchange.mjs';

test('S0 exchanges produce the correct TradingView prefix regardless of case', () => {
  for (const [ticker, input, label, prefix] of [
    ['AAPL', 'Nasdaq', 'NASDAQ', 'NASDAQ'],
    ['MSFT', 'nAsDaQ', 'NASDAQ', 'NASDAQ'],
    ['VRT', 'NYSE', 'NYSE', 'NYSE'],
    ['UAMY', 'nyse american', 'NYSE American', 'AMEX'],
  ]) {
    assert.deepEqual(normalizeExchange(input), { label, prefix }, ticker);
  }
});

test('unknown or malformed exchanges cannot create a market symbol', () => {
  for (const input of ['OTC', 'NASDAQ:FAKE', '', null, 123]) {
    assert.equal(normalizeExchange(input), null);
  }
});
