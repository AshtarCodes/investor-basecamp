// PROTOTYPE (throwaway). Variant B: the focused Build's end result on every path, against shares, and what each leg added.

import { useMemo } from 'react'
import { ClientOnly } from '@tanstack/react-router'
import { barX, barY, defineChart, ruleX, ruleY } from '@tanstack/charts'
import { group } from '@tanstack/charts/group'
import { Chart } from '@tanstack/charts/react'
import { scaleBand } from '@tanstack/charts/scales/band'
import { scaleLinear } from '@tanstack/charts/scales/linear'
import { tooltip } from '@tanstack/charts/tooltip'

import { LegLegend, type LegendItem } from './leg-legend.tsx'
import { axisFormat, COLOR, fixedDomain, fmtPct, fmtShare, fmtUsd, isRecord, legColor, legLabel, pnlClass, valueFormat } from './model.ts'
import type { ViewProps } from './view.ts'

type OutcomeRow = { path: string; series: string; value: number; fill: string }
type ContribRow = { label: string; value: number; fill: string }

export function VariantB({ state, update, build, paths, path, run: runOf, baseline, side, below }: ViewProps) {
  const budget = build.budget
  const isShares = build.sleeves.length === 0
  const totalWeight = paths.reduce((sum, p) => sum + (p.id === 'unsaved' ? 0 : p.weight), 0)
  // bars are labelled by name; two paths with one name would share a bar, so a repeat gets a suffix
  const labels = useMemo(() => {
    const seen = new Map<string, number>()
    return new Map(
      paths.map((p) => {
        const n = (seen.get(p.name) ?? 0) + 1
        seen.set(p.name, n)
        return [p.id, n > 1 ? `${p.name} (${n})` : p.name]
      }),
    )
  }, [paths])

  const outcome = useMemo(() => {
    const conv = (total: number) => (state.y === 'usd' ? total : total / budget - 1)
    const fmt = valueFormat(state.y)
    const rows: OutcomeRow[] = []
    const all: number[] = []
    for (const p of paths) {
      const mine = runOf(build.id, p.id)
      const base = baseline(budget, p.id)
      const label = labels.get(p.id) ?? p.name
      if (mine) rows.push({ path: label, series: build.name, value: conv(mine.total), fill: COLOR.total })
      if (base && !isShares) rows.push({ path: label, series: 'All shares', value: conv(base.total), fill: '#cbd5e1' })
      if (mine) all.push(conv(mine.total))
      if (base) all.push(conv(base.total))
    }
    const [lo, hi] = fixedDomain(all, true)
    return defineChart({
      marks: [barY(rows, { id: 'outcome', x: 'path', y: 'value', z: 'series', fill: (r: OutcomeRow) => r.fill, layout: group({ padding: 0.08 }) }), ruleY([state.y === 'usd' ? budget : 0], { stroke: '#a1a1aa', strokeDasharray: '4 3' })],
      scales: {
        x: { scale: () => scaleBand().padding(0.2) },
        y: { scale: scaleLinear().domain([lo, hi]), grid: true, axis: { label: state.y === 'usd' ? 'Final wealth + debt paid ($)' : 'Total return incl. debt', ticks: { format: axisFormat(state.y) } } },
      },
      tooltip: {
        use: tooltip,
        format(point: { datum: unknown }) {
          const d = isRecord(point.datum) ? point.datum : {}
          return `${String(d.path)}\n${String(d.series)}: ${fmt(Number(d.value))}`
        },
      },
    })
  }, [paths, runOf, baseline, build, budget, state.y, isShares, labels])

  const run = runOf(build.id)
  const contribIds = run ? Object.keys(run.contrib) : []
  const items: LegendItem[] = contribIds.map((id) => ({ id, label: legLabel(build, id), color: legColor(build, id), detail: run ? fmtUsd(run.contrib[id] ?? 0) : '' }))
  const hidden = state.hidden

  const contribChart = useMemo(() => {
    if (!run) return undefined
    const fmt = valueFormat(state.y)
    const conv = (v: number) => (state.y === 'usd' ? v : v / budget)
    const rows: ContribRow[] = Object.keys(run.contrib)
      .filter((id) => !hidden.includes(id))
      .map((id) => ({ label: legLabel(build, id), value: conv(run.contrib[id] ?? 0), fill: legColor(build, id) }))
    const [lo, hi] = fixedDomain(
      paths.flatMap((p) => Object.values(runOf(build.id, p.id)?.contrib ?? {}).map(conv)),
      true,
    )
    return defineChart({
      marks: [barX(rows, { id: 'contrib', x: 'value', y: 'label', fill: (r: ContribRow) => r.fill }), ruleX([0], { stroke: '#a1a1aa' })],
      scales: {
        y: { scale: () => scaleBand().padding(0.25) },
        x: { scale: scaleLinear().domain([lo, hi]), grid: true, axis: { label: state.y === 'usd' ? 'Added to the end result ($)' : 'Added, as % of the budget', ticks: { format: axisFormat(state.y) } } },
      },
      tooltip: {
        use: tooltip,
        format(point: { datum: unknown }) {
          const d = isRecord(point.datum) ? point.datum : {}
          return `${String(d.label)}: ${fmt(Number(d.value))}`
        },
      },
    })
  }, [run, hidden, build, state.y, budget, paths, runOf])

  const toggle = (id: string) => update({ hidden: hidden.includes(id) ? hidden.filter((h) => h !== id) : [...hidden, id] })
  const allIds = items.map((i) => i.id)

  return (
    <div className="flex flex-col gap-4 p-3 text-xs">
      <div className="flex flex-col gap-4 2xl:flex-row">
        <section className="min-w-0 flex-1">
          <h2 className="mb-1 text-sm font-semibold">
            {build.name} against shares, on each path <span className="font-normal text-muted-foreground">(debt {fmtShare(Number(state.debt))} of the gain)</span>
          </h2>
          <div className="rounded-md border bg-background p-2">
            <ClientOnly fallback={<div style={{ height: 360 }} />}>
              <Chart
                definition={outcome}
                height={360}
                ariaLabel={`${build.name} against shares on each path`}
                onSelect={(point) => {
                  const label = isRecord(point?.datum) ? point.datum.path : undefined
                  const hit = paths.find((p) => labels.get(p.id) === label)
                  if (hit) update({ path: hit.id })
                }}
              />
            </ClientOnly>
          </div>
          <p className="mt-1 text-muted-foreground">Click a bar group to load that path.</p>
          <table className="mt-3 w-full max-w-5xl tabular-nums">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-1 font-normal">Path</th>
                <th className="font-normal">Weight</th>
                <th className="text-right font-normal">{build.name}</th>
                <th className="text-right font-normal">Debt paid</th>
                <th className="text-right font-normal">All shares</th>
                <th className="text-right font-normal">Difference</th>
              </tr>
            </thead>
            <tbody>
              {paths.map((p) => {
                const mine = runOf(build.id, p.id)
                const base = baseline(budget, p.id)
                if (!mine || !base) return null
                return (
                  <tr key={p.id} className={`cursor-pointer border-b hover:bg-muted/50 ${p.id === path.id ? 'bg-yellow-50' : ''}`} onClick={() => update({ path: p.id })}>
                    <td className="py-1">{labels.get(p.id)}</td>
                    <td>{p.id === 'unsaved' ? 'unsaved' : totalWeight > 0 ? fmtShare(p.weight / totalWeight) : '0%'}</td>
                    <td className={`text-right ${pnlClass(mine.total - budget)}`}>
                      {fmtUsd(mine.total)} ({fmtPct(mine.total / budget - 1)})
                    </td>
                    <td className="text-right">{fmtUsd(mine.debt)}</td>
                    <td className="text-right">
                      {fmtUsd(base.total)} ({fmtPct(base.total / budget - 1)})
                    </td>
                    <td className={`text-right ${pnlClass(mine.total - base.total)}`}>
                      {mine.total - base.total >= 0 ? '+' : ''}
                      {fmtUsd(mine.total - base.total)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {below}
        </section>
        <section className="flex w-full flex-col gap-3 2xl:w-[26rem]">
          <div>
            <h2 className="mb-1 text-sm font-semibold">What each leg added on: {path.name}</h2>
            <div className="rounded-md border bg-background p-2">
              {contribChart && (
                <ClientOnly fallback={<div style={{ height: 260 }} />}>
                  <Chart definition={contribChart} height={260} ariaLabel={`What each leg of ${build.name} added on ${path.name}`} />
                </ClientOnly>
              )}
            </div>
            <div className="mt-2">
              <LegLegend items={items} hidden={hidden} onToggle={toggle} onSolo={(id) => update({ hidden: allIds.filter((x) => x !== id) })} onAll={() => update({ hidden: [] })} onNone={() => update({ hidden: allIds })} />
            </div>
            <p className="mt-1 text-muted-foreground">Proceeds from what was sold, plus what is still held at the end, less what it cost. The legs add up to the total less the budget.</p>
          </div>
          {side}
        </section>
      </div>
    </div>
  )
}
