const knownExchanges = new Map([
  ['nasdaq', { label: 'NASDAQ', prefix: 'NASDAQ' }],
  ['nyse', { label: 'NYSE', prefix: 'NYSE' }],
  ['nyse american', { label: 'NYSE American', prefix: 'AMEX' }],
]);

export function normalizeExchange(value) {
  if (typeof value !== 'string') return null;
  return knownExchanges.get(value.trim().replace(/\s+/g, ' ').toLowerCase()) || null;
}
