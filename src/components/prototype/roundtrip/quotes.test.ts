import { expect, test } from 'vitest'

import { describeBuild, expected, expiryBadge, type QuoteSet } from './quotes.ts'

const quote = (expiry: string, strike: number, bid: number, ask: number) => ({ occ: '', expiry, strike, kind: 'C' as const, bid, ask, mark: (bid + ask) / 2, delta: 0.5, iv: 90, rate: 4, spot: 27.1, quoteTime: '2026-10-27T16:45:44Z' })
const QS: QuoteSet = {
  symbol: 'IREN',
  takenAt: '2026-10-27T16:45:46Z',
  spot: 27.1,
  contracts: [quote('2029-01-19', 25, 14.0, 14.6), quote('2029-01-19', 75, 6.2, 6.8), quote('2029-01-19', 40, 11.6, 12.0), quote('2028-01-21', 40, 4.0, 4.4)],
}
const leg = (expiry: string, strike: number, side: 1 | -1 = 1) => ({ expiry, strike, kind: 'C' as const, side })

test('a sleeve costs the ask of its long legs less the bid of its short ones, and shares take the rest', () => {
  const view = describeBuild(
    { id: 'b', name: 'B', description: null, budget: 10_000, defaultPathId: null, sleeves: [{ id: 'x', contracts: 2, legs: [leg('2029-01-19', 25), leg('2029-01-19', 75, -1)] }, { id: 'y', contracts: 1, legs: [leg('2029-01-19', 40)] }] },
    QS,
  )
  // 25/75: $14.60 - $6.20 = $8.40 a share, $840 a contract; $40 call $1,200
  expect(view.sleeves.map((s) => [s.label, s.unitCost])).toEqual([
    ['Jan 2029 25/75 call spread', 840],
    ['Jan 2029 $40 call', 1200],
  ])
  expect(view.cost).toBe(2880)
  expect(view.shares).toBeCloseTo(7120 / 27.1, 6)
  // bid/ask: ($0.60 + $0.60) / $8.40 on the spread
  expect(view.sleeves[0]?.spreadPct).toBeCloseTo(1.2 / 8.4, 6)
})

test('a sleeve whose contract is not in the Quote Set has no cost', () => {
  const view = describeBuild({ id: 'b', name: 'B', description: null, budget: 10_000, defaultPathId: null, sleeves: [{ id: 'x', contracts: 1, legs: [leg('2029-01-19', 33)] }] }, QS)
  expect(view.sleeves[0]?.unitCost).toBeNull()
})

test('the expiry badge names one expiry month, or says Mixed', () => {
  expect(expiryBadge([[leg('2029-01-19', 40)], [leg('2029-01-19', 25), leg('2029-01-19', 75, -1)]])).toBe('Jan 2029')
  expect(expiryBadge([[leg('2029-01-19', 40)], [leg('2028-01-21', 40)]])).toBe('Mixed')
  expect(expiryBadge([])).toBe('Shares')
})

test('Expected is the weighted average return over paths with weight, scaled to 100%', () => {
  // 45 on +100%, 20 on +300%, 35 on -50%: (45 x 2 + 20 x 4 + 35 x 0.5) / 100 = 1.875, so +87.5%
  const totals = new Map([
    ['base', 20_000],
    ['bull', 40_000],
    ['bear', 5_000],
    ['unweighted', 1_000_000],
  ])
  const paths = [
    { id: 'base', weight: 45 },
    { id: 'bull', weight: 20 },
    { id: 'bear', weight: 35 },
    { id: 'unweighted', weight: 0 },
  ]
  expect(expected(paths, (id) => totals.get(id), 10_000)).toBeCloseTo(0.875, 9)
  expect(expected([{ id: 'base', weight: 0 }], () => 20_000, 10_000)).toBeNull()
})
