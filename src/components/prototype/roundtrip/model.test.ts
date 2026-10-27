import { expect, test } from 'vitest'

import { dateRole } from './model.ts'
import type { Point } from './store.ts'

const base = {
  name: 'Base',
  points: [
    { date: '2027-12-31', price: 103, action: 'hold', sellPct: null },
    { date: '2028-06-30', price: 129.97, action: 'sell_cash', sellPct: 50 },
    { date: '2028-12-29', price: 164, action: 'hold', sellPct: null },
  ] satisfies Point[],
}
const dates = ['2026-10-27', '2027-11-30', '2027-12-31', '2028-01-20', '2028-06-30', '2028-12-29', '2029-01-18']

test('each valuation date says whether it is one of the path’s points, and if not, why it is on the chart', () => {
  expect(dateRole('2026-10-27', base, dates)).toBe("Entry, at today's price")
  expect(dateRole('2027-12-31', base, dates)).toBe('Point of Base: Hold')
  expect(dateRole('2028-06-30', base, dates)).toBe('Point of Base: Sell 50% → cash')
  expect(dateRole('2027-11-30', base, dates)).toBe('Debt date, not a point of Base: the price is the path’s, between today and the Dec 31, 2027 point')
  expect(dateRole('2028-01-20', base, dates)).toBe('Expiry sale, not a point of Base: the price is the path’s, between the Dec 31, 2027 and Jun 30, 2028 points')
  expect(dateRole('2029-01-18', base, dates)).toBe('Expiry sale, not a point of Base: the price stays at the last point’s')
})
