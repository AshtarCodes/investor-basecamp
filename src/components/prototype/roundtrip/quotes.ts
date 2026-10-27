// PROTOTYPE (throwaway). The Quote Set (what `pnpm schwab option chain` prints) and what a Build costs on it.
// Shared by the server and the page; entry is the ask for long Legs and the bid for short ones, as in the engine.

import type { Leg, StoredBuild } from './store.ts'

type Quote = {
  occ: string
  expiry: string
  strike: number
  kind: 'C' | 'P'
  bid: number | null
  ask: number | null
  mark: number | null
  delta: number | null
  iv: number | null // Schwab's, percent
  rate: number // percent
  spot: number
  quoteTime: string
}

export type QuoteSet = { symbol: string; takenAt: string; spot: number; contracts: Quote[] }

type SleeveView = StoredBuild['sleeves'][number] & {
  key: string // the engine's id for this Sleeve: its position, s0, s1, ...
  label: string
  unitCost: number | null // dollars per contract, null when a Leg has no quote
  spreadPct: number | null // the bid/ask spread as a share of the entry cost
}

export type BuildView = Omit<StoredBuild, 'sleeves'> & { sleeves: SleeveView[]; cost: number; shares: number; badge: string }

function findQuote(qs: QuoteSet, leg: Leg): Quote | undefined {
  return qs.contracts.find((q) => q.expiry === leg.expiry && q.strike === leg.strike && q.kind === leg.kind)
}

export function fmtExpiry(expiry: string): string {
  return new Date(`${expiry}T00:00:00Z`).toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' })
}

export function sleeveLabel(legs: Leg[]): string {
  const [first, second] = legs
  if (!first) return ''
  const kind = first.kind === 'C' ? 'call' : 'put'
  if (!second) return `${fmtExpiry(first.expiry)} $${first.strike} ${kind}`
  return `${fmtExpiry(first.expiry)} ${first.strike}/${second.strike} ${kind} spread`
}

/** Per share of one contract: the entry cost, and the bid/ask spread summed over its Legs. Null if a Leg has no quote. */
export function legsCost(qs: QuoteSet, legs: Leg[]): { cost: number; spread: number } | null {
  let cost = 0
  let spread = 0
  for (const leg of legs) {
    const q = findQuote(qs, leg)
    if (!q || q.bid === null || q.ask === null) return null
    cost += leg.side * (leg.side > 0 ? q.ask : q.bid)
    spread += q.ask - q.bid
  }
  return { cost, spread }
}

export function expiryBadge(sleeves: Leg[][]): string {
  const months = new Set(sleeves.flat().map((l) => fmtExpiry(l.expiry)))
  if (months.size === 0) return 'Shares'
  return months.size === 1 ? ([...months][0] ?? '') : 'Mixed'
}

export function describeBuild(build: StoredBuild, qs: QuoteSet): BuildView {
  const sleeves = build.sleeves.map((s, i): SleeveView => {
    const c = legsCost(qs, s.legs)
    return { ...s, key: `s${i}`, label: sleeveLabel(s.legs), unitCost: c ? Math.round(c.cost * 100 * 100) / 100 : null, spreadPct: c && c.cost > 0 ? c.spread / c.cost : null }
  })
  const cost = sleeves.reduce((sum, s) => sum + s.contracts * (s.unitCost ?? 0), 0)
  return { ...build, sleeves, cost, shares: Math.max(0, build.budget - cost) / qs.spot, badge: expiryBadge(build.sleeves.map((s) => s.legs)) }
}

/** The weighted average return over the paths with weight above 0, the weights scaled to 100%; null with no weight. */
export function expected(paths: { id: string; weight: number }[], total: (pathId: string) => number | undefined, budget: number): number | null {
  let weight = 0
  let sum = 0
  for (const p of paths) {
    const t = total(p.id)
    if (p.weight <= 0 || t === undefined) continue
    weight += p.weight
    sum += p.weight * (t / budget - 1)
  }
  return weight > 0 ? sum / weight : null
}
