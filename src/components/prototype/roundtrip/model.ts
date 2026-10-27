// PROTOTYPE (throwaway). Helpers shared by the roundtrip views: formats, colours, lines and the baseline.

import type { BuildView } from './quotes.ts'
import type { Point } from './store.ts'
import type { Run, YMode } from './types.ts'

export const DEBTS = ['0.00', '0.10', '0.25', '0.50']
export const BASELINE_ID = '__shares'
const BASELINE_BUDGET = 10_000

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** A Price Path as the views see it: a saved one, or the unsaved copy (id 'unsaved'). */
export type PathLike = { id: string; name: string; description: string | null; weight: number; points: Point[] }

const PALETTE = ['#7c3aed', '#2563eb', '#d97706', '#dc2626', '#0891b2', '#16a34a', '#db2777']
export const COLOR = {
  stock: '#64748b',
  cash: '#a3a3a3',
  debt: '#f59e0b',
  total: '#111827',
  baseline: '#6b7280',
}

/** Colour for a leg, stable for a build: Sleeves take palette colours in the build's own order. */
export function legColor(build: BuildView, id: string): string {
  if (id === 'stock' || id === 'cash' || id === 'debt' || id === 'total') return COLOR[id]
  const index = build.sleeves.findIndex((s) => s.key === id)
  return PALETTE[Math.max(0, index) % PALETTE.length] ?? COLOR.stock
}

export function fmtUsd(n: number): string {
  const abs = Math.abs(n).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
  return n < 0 ? `−${abs}` : abs
}

export function fmtSignedUsd(n: number): string {
  return n > 0 ? `+${fmtUsd(n)}` : fmtUsd(n)
}

export function fmtPct(n: number, digits = 0): string {
  const text = `${Math.abs(n * 100).toLocaleString('en-US', { maximumFractionDigits: digits })}%`
  return n < 0 ? `−${text}` : n > 0 ? `+${text}` : text
}

export function fmtShare(n: number): string {
  return `${Math.round(n * 100)}%`
}

export function fmtDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
}

export function pnlClass(n: number): string {
  return n > 0 ? 'text-emerald-700' : n < 0 ? 'text-red-700' : 'text-muted-foreground'
}

export function runKey(buildId: string, pathId: string, debt: string): string {
  return `${buildId}|${pathId}|${debt}`
}

/** The all-shares baseline at another budget: every dollar figure scales with it (the debt rule is linear too). */
export function scaleRun(run: Run, budget: number): Run {
  const k = budget / BASELINE_BUDGET
  const legs = Object.fromEntries(Object.entries(run.legs).map(([id, xs]) => [id, xs.map((x) => x * k)]))
  const contrib = Object.fromEntries(Object.entries(run.contrib).map(([id, x]) => [id, x * k]))
  return { ...run, total: run.total * k, wealth: run.wealth * k, debt: run.debt * k, legs, contrib, events: run.events.map((e) => ({ ...e, amount: e.amount * k })) }
}

export function legLabel(build: BuildView, id: string): string {
  if (id === 'stock') return `Shares (${Math.round(build.shares)} at entry)`
  if (id === 'cash') return 'Cash from sales'
  if (id === 'debt') return 'Debt paid (cumulative)'
  if (id === 'total') return 'Total incl. debt paid'
  const sleeve = build.sleeves.find((s) => s.key === id)
  return sleeve ? `${sleeve.contracts} × ${sleeve.label}` : id
}

/** Legs that can be shown for a build, in legend order. */
export function toggleableLegs(build: BuildView, y: YMode): string[] {
  const ids = ['stock', ...build.sleeves.map((s) => s.key)]
  if (y === 'usd') ids.push('cash', 'debt')
  return ids
}

export type Row = { date: Date; value: number; series: string }

/** One line's rows for the chart: dollars of holdings, or the return on one share or contract. A sold Sleeve's line stops. */
export function legRows(run: Run, id: string, label: string, y: YMode): Row[] {
  const rows: Row[] = []
  const values = y === 'usd' ? run.legs[id] : run.unit[id]
  if (!values) return rows
  const isSleeve = id.startsWith('s')
  let ended = false
  values.forEach((raw, i) => {
    if (raw === null || raw === undefined || ended) return
    rows.push({ date: new Date(`${run.dates[i]}T00:00:00Z`), value: raw, series: label })
    if (isSleeve && y === 'usd' && raw === 0 && i > 0) ended = true // sold out: keep the first zero, then stop the line
  })
  return rows
}

export function totalRows(run: Run, y: YMode, label: string, budget: number): Row[] {
  return run.dates.map((d, i) => ({
    date: new Date(`${d}T00:00:00Z`),
    value: y === 'usd' ? (run.legs.total?.[i] ?? 0) : (run.legs.total?.[i] ?? 0) / budget - 1,
    series: label,
  }))
}

export function axisFormat(y: YMode): (value: number) => string {
  return y === 'usd'
    ? (v) => (Math.abs(v) >= 1000 ? `${v < 0 ? '−' : ''}$${(Math.abs(v) / 1000).toLocaleString('en-US', { maximumFractionDigits: 1 })}k` : fmtUsd(v))
    : (v) => fmtPct(v)
}

export function valueFormat(y: YMode): (value: number) => string {
  return y === 'usd' ? fmtUsd : (v) => fmtPct(v, 1)
}

export function parseHidden(raw: unknown): string[] {
  if (typeof raw !== 'string' || raw === '') return []
  return raw.split(',').filter(Boolean)
}

/** A fixed axis, so changing the path or debt share moves the lines and bars, not the scale. */
const step = (v: number) => 10 ** Math.floor(Math.log10(Math.max(Math.abs(v), 1))) / 2

export function fixedDomain(values: number[], includeZero: boolean): [number, number] {
  let lo = Math.min(...values, includeZero ? 0 : Infinity)
  let hi = Math.max(...values, includeZero ? 0 : -Infinity)
  hi = hi > 0 ? Math.ceil((hi * 1.04) / step(hi)) * step(hi) : 0
  lo = lo < 0 ? Math.floor((lo * 1.04) / step(lo)) * step(lo) : 0
  return [lo, hi]
}
