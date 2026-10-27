// PROTOTYPE (throwaway). Variant A: the focused Build's legs over time on the loaded path, one line per leg, with events.

import { useMemo, useState } from 'react'
import { ClientOnly } from '@tanstack/react-router'
import { defineChart, dot, lineY, ruleY, text, type ChartMark } from '@tanstack/charts'
import { decorative } from '@tanstack/charts/mark/decorative'
import { Chart } from '@tanstack/charts/react'
import { scaleLinear } from '@tanstack/charts/scales/linear'
import { tooltip } from '@tanstack/charts/tooltip'
import { scaleUtc } from 'd3-scale'

import { Button } from '#/components/ui/button.tsx'
import { LegLegend, type LegendItem } from './leg-legend.tsx'
import { axisFormat, COLOR, dateRole, fixedDomain, fmtDate, fmtPct, fmtSignedUsd, fmtUsd, isRecord, legColor, legLabel, legRows, pnlClass, toggleableLegs, totalRows, valueFormat, type Row } from './model.ts'
import type { EngineEvent } from './types.ts'
import type { ViewProps } from './view.ts'

const EVENT_COLOR: Record<EngineEvent['type'], string> = { action: '#16a34a', debt: '#2563eb', expiry: '#d97706' }
const EVENT_TYPES: EngineEvent['type'][] = ['action', 'debt', 'expiry']
const RING = '#3f3f46'

type EventRow = { date: Date; value: number; label: string; dy: number; type: EngineEvent['type'] }

function eventShort(e: EngineEvent): string {
  if (e.type === 'action') return `sell ${e.pct}%: ${e.contracts} ct`
  if (e.type === 'debt') return 'debt'
  return `expiry: ${e.contracts} ct`
}

function eventLabel(e: EngineEvent, sleeveLabel: (key: string) => string): string {
  if (e.type === 'action') return `Sell ${e.pct}% of each option sleeve → ${e.action === 'sell_cash' ? 'cash' : 'shares'}: ${e.contracts} contracts`
  if (e.type === 'debt') return `Pay debt (${fmtPct(e.pct ?? 0)} of the gain)`
  return `${sleeveLabel(e.sleeve ?? '')} sold before expiry (${e.contracts} contracts) → shares`
}

export function VariantA({ state, update, build, paths, path, run: runOf, baseline, side, below }: ViewProps) {
  const run = runOf(build.id)
  const base = build.sleeves.length > 0 ? baseline(build.budget) : undefined
  const [selected, setSelected] = useState<number | null>(null)
  const [sameScale, setSameScale] = useState(true)
  const dates = useMemo(() => run?.dates ?? [], [run])
  const lastIndex = dates.length - 1
  const at = Math.min(selected ?? lastIndex, lastIndex)
  const legIds = useMemo(() => toggleableLegs(build, state.y), [build, state.y])
  const items: LegendItem[] = [
    { id: 'total', label: legLabel(build, 'total'), color: COLOR.total },
    ...legIds.map((id) => ({ id, label: legLabel(build, id), color: legColor(build, id) })),
    ...(base ? [{ id: 'baseline', label: `All shares (${fmtUsd(build.budget)})`, color: COLOR.baseline }] : []),
  ]
  const hidden = state.hidden

  // one axis across every path, so switching paths moves the lines and not the scale; the path that peaks highest is left
  // out of it, so it can run off the top instead of flattening the others
  const domain = useMemo(() => {
    const byPath = paths.map((p) => {
      const r = runOf(build.id, p.id)
      const values: number[] = []
      if (r) for (const line of Object.values(state.y === 'usd' ? r.legs : r.unit)) for (const v of line) if (v !== null && v !== undefined) values.push(v)
      if (r && state.y === 'pct') for (const t of r.legs.total ?? []) values.push(t / build.budget - 1)
      return values
    })
    const peaks = byPath.map((v) => Math.max(...v, 0))
    const top = peaks.indexOf(Math.max(...peaks))
    return fixedDomain(byPath.filter((_, i) => i !== top || byPath.length === 1).flat(), true)
  }, [paths, runOf, build, state.y])
  const cap = sameScale ? domain[1] : Number.POSITIVE_INFINITY

  const definition = useMemo(() => {
    if (!run) return undefined
    const clip = (rows: Row[]) => rows.map((row) => ({ ...row, shown: Math.min(row.value, cap) }))
    // dynamic mark list: the library infers types from literal tuples, so this prototype types the list loosely
    // oxlint-disable-next-line typescript/no-explicit-any
    const marks: ChartMark<any, any, any>[] = [ruleY([state.y === 'usd' ? build.budget : 0], { stroke: '#a1a1aa', strokeDasharray: '4 3', strokeOpacity: 0.9 })]
    for (const id of legIds) {
      if (hidden.includes(id)) continue
      const rows = clip(legRows(run, id, legLabel(build, id), state.y))
      if (rows.length === 0) continue
      marks.push(lineY(rows, { id: `leg-${id}`, x: 'date', y: 'shown', z: 'series', stroke: legColor(build, id), strokeWidth: 1.75, points: true }))
    }
    if (base && !hidden.includes('baseline')) {
      marks.push(lineY(clip(totalRows(base, state.y, 'All shares (baseline)', build.budget)), { id: 'baseline', x: 'date', y: 'shown', z: 'series', stroke: COLOR.baseline, strokeWidth: 2, strokeDasharray: '6 4' }))
    }
    const totals = clip(totalRows(run, state.y, 'Total incl. debt paid', build.budget))
    if (!hidden.includes('total')) marks.push(lineY(totals, { id: 'total', x: 'date', y: 'shown', z: 'series', stroke: COLOR.total, strokeWidth: 3.5, points: true }))
    const byDate = new Map<string, number>()
    const events: EventRow[] = run.events.map((e) => {
      const i = dates.indexOf(e.date)
      const k = byDate.get(e.date) ?? 0
      byDate.set(e.date, k + 1)
      return { date: new Date(`${e.date}T00:00:00Z`), value: totals[i]?.shown ?? 0, label: eventShort(e), dy: -14 - k * 13, type: e.type }
    })
    for (const type of hidden.includes('total') ? [] : EVENT_TYPES) {
      const rows = events.filter((e) => e.type === type)
      if (rows.length === 0) continue
      marks.push(decorative(dot(rows, { id: `ev-dot-${type}`, x: 'date', y: 'value', r: 5.5, fill: EVENT_COLOR[type], stroke: '#111827', strokeWidth: 1 })))
      marks.push(decorative(text(rows, { id: `ev-text-${type}`, x: 'date', y: 'value', text: 'label', dy: (row: EventRow) => row.dy, fontSize: 11, fill: EVENT_COLOR[type], fontWeight: 600 })))
    }
    // rings on the dates whose prices set the path
    const rings: EventRow[] = hidden.includes('total')
      ? []
      : path.points.flatMap((p) => {
          const i = dates.indexOf(p.date)
          return i < 0 ? [] : [{ date: new Date(`${p.date}T00:00:00Z`), value: totals[i]?.shown ?? 0, label: `IREN $${p.price.toFixed(0)}`, dy: 18, type: 'action' as const }]
        })
    if (rings.length > 0) {
      marks.push(decorative(dot(rings, { id: 'ring-dot', x: 'date', y: 'value', r: 6, fill: '#ffffff', stroke: RING, strokeWidth: 2.5 })))
      marks.push(decorative(text(rings, { id: 'ring-text', x: 'date', y: 'value', text: 'label', dy: (row: EventRow) => row.dy, fontSize: 11, fill: RING, fontWeight: 700 })))
    }
    const fmt = valueFormat(state.y)
    return defineChart({
      marks,
      scales: {
        x: { scale: scaleUtc, nice: false, grid: true },
        y: { scale: sameScale ? scaleLinear().domain(domain) : scaleLinear, nice: !sameScale, grid: true, axis: { label: state.y === 'usd' ? 'Value in the account ($)' : 'Return vs entry', ticks: { format: axisFormat(state.y) } } },
      },
      focus: 'group-x',
      maxFocusDistance: Number.POSITIVE_INFINITY,
      tooltip: {
        use: tooltip,
        formatGroup(points: readonly { xValue: unknown; datum: unknown }[]) {
          const first = points[0]?.xValue
          const iso = first instanceof Date ? first.toISOString().slice(0, 10) : ''
          const i = dates.indexOf(iso)
          const heading = iso ? `${fmtDate(iso)} · IREN $${(run.spot[i] ?? 0).toFixed(2)}\n${dateRole(iso, path, dates)}` : ''
          return [heading, ...points.map((p) => (isRecord(p.datum) ? `${String(p.datum.series)}: ${fmt(Number(p.datum.value))}` : ''))].join('\n')
        },
      },
    })
  }, [run, base, build, legIds, hidden, state.y, dates, path, domain, sameScale, cap])

  const toggle = (id: string) => update({ hidden: hidden.includes(id) ? hidden.filter((h) => h !== id) : [...hidden, id] })
  const allIds = items.map((i) => i.id)

  const legend = <LegLegend items={items} hidden={hidden} onToggle={toggle} onSolo={(id) => update({ hidden: allIds.filter((x) => x !== id) })} onAll={() => update({ hidden: [] })} onNone={() => update({ hidden: allIds })} />

  if (!run || !definition) {
    return (
      <div className="flex flex-col gap-3 p-3 text-xs xl:flex-row xl:items-start">
        <div className="min-w-0 flex-1">
          <p className="p-4 text-sm text-muted-foreground">No run for this Build on this path yet.</p>
          {below}
        </div>
        <aside className="flex w-full shrink-0 flex-col gap-3 xl:w-80">{side}</aside>
      </div>
    )
  }

  const dateIso = dates[at] ?? ''
  const eventsHere = run.events.filter((e) => e.date === dateIso)
  const total = run.legs.total?.[at] ?? 0
  const peak = Math.max(...(run.legs.total ?? []).map((t) => (state.y === 'usd' ? t : t / build.budget - 1)))
  const clipped = sameScale && peak > domain[1]
  const sleeveLabel = (key: string) => build.sleeves.find((s) => s.key === key)?.label ?? key

  return (
    <div className="flex flex-col gap-3 p-3 text-xs xl:flex-row xl:items-start">
      <div className="min-w-0 flex-1">
        <div className="mb-2 text-sm">
          <b>{build.name}</b> <span className="text-muted-foreground">on</span> <b>{path.name}</b>
          <span className="ml-2 text-muted-foreground">
            final {fmtUsd(run.total)} ({fmtPct(run.total / build.budget - 1)} on {fmtUsd(build.budget)}) incl. {fmtUsd(run.debt)} debt paid, on {fmtDate(run.end)}
          </span>
        </div>
        <div className="mb-1 flex items-center gap-2">
          <Button size="xs" variant={sameScale ? 'default' : 'outline'} onClick={() => setSameScale(!sameScale)}>
            Same scale on every path: {sameScale ? 'on' : 'off'}
          </Button>
          <span className="text-muted-foreground">
            {sameScale ? 'One axis for every path but the one that peaks highest, which can run off the top.' : 'The axis fits what is drawn now.'}
            {clipped ? ` This path peaks at ${valueFormat(state.y)(peak)}, above the axis, so its lines stop at the top (hover for the real values).` : ''}
          </span>
        </div>
        <div className="rounded-md border bg-background p-2">
          <ClientOnly fallback={<div style={{ height: 440 }} />}>
            <Chart
              definition={definition}
              height={440}
              ariaLabel={`${build.name} legs over time on ${path.name}`}
              onSelect={(point) => {
                const x = point?.xValue
                if (x instanceof Date) {
                  const i = dates.indexOf(x.toISOString().slice(0, 10))
                  if (i >= 0) setSelected(i)
                }
              }}
            />
          </ClientOnly>
        </div>
        <p className="mt-1 text-muted-foreground">
          Dots on the lines are the dates the engine values: entry, each of the path's points (grey rings, with their prices), and two kinds of date it adds itself, the debt date (2027-11-30) and each expiry sale, priced where the path is on that day. Straight segments are not prices in between. Click a date to read it on the right. Dashed grey:
          the same budget in shares only.
        </p>
        {below}
      </div>
      <aside className="flex w-full shrink-0 flex-col gap-3 xl:w-80">
        {legend}
        <div className="rounded-md border bg-background p-3">
          <h2 className="mb-1 text-sm font-semibold">
            {fmtDate(dateIso)} <span className="font-normal text-muted-foreground">IREN ${(run.spot[at] ?? 0).toFixed(2)}</span>
          </h2>
          <p className={`mb-1 ${path.points.some((p) => p.date === dateIso) ? 'text-muted-foreground' : 'font-medium text-amber-800'}`}>{dateRole(dateIso, path, dates)}</p>
          <table className="w-full tabular-nums">
            <tbody>
              {legIds.map((id) => {
                const v = run.legs[id]?.[at] ?? 0
                const u = run.unit[id]?.[at]
                return (
                  <tr key={id} className={hidden.includes(id) ? 'opacity-40' : ''}>
                    <td className="py-0.5">
                      <span className="mr-1 inline-block h-2 w-2 rounded-sm" style={{ background: legColor(build, id) }} />
                      {legLabel(build, id)}
                    </td>
                    <td className="text-right">{fmtUsd(v)}</td>
                    <td className={`w-14 text-right ${u === null || u === undefined ? '' : pnlClass(u)}`}>{u === null || u === undefined ? '' : fmtPct(u)}</td>
                  </tr>
                )
              })}
              <tr className="border-t font-semibold">
                <td className="py-0.5">Total incl. debt paid</td>
                <td className="text-right">{fmtUsd(total)}</td>
                <td className={`w-14 text-right ${pnlClass(total - build.budget)}`}>{fmtPct(total / build.budget - 1)}</td>
              </tr>
            </tbody>
          </table>
          <p className="mt-1 text-[11px] text-muted-foreground">Right column: return on one share or contract against its entry cost, as if held.</p>
          {eventsHere.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1 border-t pt-2">
              {eventsHere.map((e, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="mt-1 inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: EVENT_COLOR[e.type] }} />
                  <span>
                    {eventLabel(e, sleeveLabel)}
                    <b className="ml-1">{fmtSignedUsd(e.amount)}</b>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
        {side}
      </aside>
    </div>
  )
}

