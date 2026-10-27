// PROTOTYPE (throwaway). Variant C: the focused Build against one other on the loaded path; the shaded gap shows where it
// leads or trails. With different budgets it shows returns, since dollars would compare different amounts of money.

import { useState } from 'react'
import { ClientOnly } from '@tanstack/react-router'
import { defineChart, differenceY, lineY, ruleY } from '@tanstack/charts'
import { Chart } from '@tanstack/charts/react'
import { scaleLinear } from '@tanstack/charts/scales/linear'
import { tooltip } from '@tanstack/charts/tooltip'
import { scaleUtc } from 'd3-scale'

import { Button } from '#/components/ui/button.tsx'
import { axisFormat, COLOR, fmtDate, fmtPct, fmtUsd, isRecord, legLabel, pnlClass, valueFormat } from './model.ts'
import type { BuildView } from './quotes.ts'
import type { Run, YMode } from './types.ts'
import type { ViewProps } from './view.ts'

type Pair = { date: Date; build: number; vs: number }
type Point = { date: Date; value: number }

/** A run's total on each date, as dollars or as a return on its own budget; carried flat past its last date. */
function valueOn(run: Run, budget: number, d: string, y: YMode): number {
  let i = run.dates.length - 1
  while (i > 0 && (run.dates[i] ?? '') > d) i--
  const t = run.legs.total?.[i] ?? 0
  return y === 'usd' ? t : t / budget - 1
}

function contribRows(b: BuildView, run: Run | undefined) {
  return Object.keys(run?.contrib ?? {})
    .map((id) => ({ label: legLabel(b, id), value: run?.contrib[id] ?? 0 }))
    .filter((r) => r.value !== 0)
}

export function VariantC({ state, update, build, builds, path, run: runOf, baseline, expectedOf, side, below }: ViewProps) {
  const others = builds.filter((b) => b.id !== build.id)
  const vsBuild: BuildView | undefined = others.find((b) => b.id === state.vs) ?? others.find((b) => b.sleeves.length === 0) ?? others[0]
  const [dollarsAnyway, setDollarsAnyway] = useState(false)
  const mine = runOf(build.id)
  const other = vsBuild ? runOf(vsBuild.id) : undefined
  const differ = vsBuild !== undefined && vsBuild.budget !== build.budget
  const y: YMode = differ && !dollarsAnyway ? 'pct' : state.y
  const fmt = valueFormat(y)

  const sharesRun = baseline(build.budget)
  const definition = (() => {
    if (!mine || !other || !vsBuild) return undefined
    const dates = [...new Set([...mine.dates, ...other.dates])].toSorted()
    const rows: Pair[] = dates.map((d) => ({ date: new Date(`${d}T00:00:00Z`), build: valueOn(mine, build.budget, d, y), vs: valueOn(other, vsBuild.budget, d, y) }))
    return defineChart({
      marks: [
        ruleY([y === 'usd' ? build.budget : 0], { stroke: '#a1a1aa', strokeDasharray: '4 3' }),
        differenceY(rows, { id: 'gap', x: 'date', y1: 'vs', y2: 'build', positiveFill: '#16a34a', negativeFill: '#dc2626', comparisonStroke: COLOR.baseline }),
        // all shares with the focused Build's budget, unless that is what it is compared with
        ...(sharesRun && vsBuild.sleeves.length > 0
          ? [lineY(dates.map((d): Point => ({ date: new Date(`${d}T00:00:00Z`), value: valueOn(sharesRun, build.budget, d, y) })), { id: 'shares', x: 'date', y: 'value', stroke: COLOR.baseline, strokeWidth: 1.5, strokeDasharray: '6 4' })]
          : []),
      ],
      scales: {
        x: { scale: scaleUtc, nice: false, grid: true },
        y: { scale: scaleLinear, nice: true, grid: true, axis: { label: y === 'usd' ? 'Total incl. debt paid ($)' : 'Total return incl. debt', ticks: { format: axisFormat(y) } } },
      },
      focus: 'group-x',
      maxFocusDistance: Number.POSITIVE_INFINITY,
      tooltip: {
        use: tooltip,
        formatGroup(points: readonly { xValue: unknown; datum: unknown }[]) {
          const p = points[0]
          const d = isRecord(p?.datum) ? p.datum : {}
          const x = p?.xValue
          const heading = x instanceof Date ? fmtDate(x.toISOString().slice(0, 10)) : ''
          if (typeof d.build !== 'number' || typeof d.vs !== 'number') return heading
          return [heading, `${build.name}: ${fmt(d.build)}`, `${vsBuild.name}: ${fmt(d.vs)}`, `Gap: ${fmt(d.build - d.vs)}`].join('\n')
        },
      },
    })
  })()

  return (
    <div className="flex flex-col gap-3 p-3 text-xs xl:flex-row xl:items-start">
      <div className="min-w-0 flex-1">
        <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
          <b>{build.name}</b>
          <span className="text-muted-foreground">against</span>
          <select aria-label="Compare against" className="max-w-80 rounded border border-zinc-400 bg-background px-1 py-0.5 text-xs" value={vsBuild?.id ?? ''} onChange={(e) => update({ vs: e.target.value })}>
            {others.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} ({b.badge}, {fmtUsd(b.budget)})
              </option>
            ))}
          </select>
          <span className="text-muted-foreground">on {path.name}</span>
        </div>
        {differ && (
          <div className="mb-2 flex items-center gap-2 rounded border border-amber-300 bg-amber-50 px-2 py-1 text-amber-900">
            Budgets differ ({fmtUsd(build.budget)} against {fmtUsd(vsBuild?.budget ?? 0)}), so the chart shows each Build's return on its own budget.
            <Button size="xs" variant="outline" onClick={() => setDollarsAnyway(!dollarsAnyway)}>
              {dollarsAnyway ? 'Show returns' : 'Show dollars anyway'}
            </Button>
          </div>
        )}
        <div className="rounded-md border bg-background p-2">
          <ClientOnly fallback={<div style={{ height: 420 }} />}>
            {definition ? <Chart definition={definition} height={420} ariaLabel={`${build.name} against ${vsBuild?.name ?? ''} over time`} /> : <p className="p-4 text-muted-foreground">Pick a second priced Build to compare.</p>}
          </ClientOnly>
        </div>
        <p className="mt-1 text-muted-foreground">
          Green: {build.name} is ahead. Red: it trails. Grey line: {vsBuild?.name}. Dashed: {fmtUsd(build.budget)} in shares only. Valuation dates only; a Build whose options expire earlier is all shares after its expiry sale.
        </p>
        {below}
      </div>
      <aside className="flex w-full shrink-0 flex-col gap-3 xl:w-96">
        <div className="rounded-md border bg-background p-3">
          <h2 className="mb-1 text-sm font-semibold">Results (debt {fmtPct(Number(state.debt))} of the gain)</h2>
          <table className="w-full tabular-nums">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="font-normal">
                  <span className="sr-only">Measure</span>
                </th>
                <th className="text-right font-normal">{build.name}</th>
                <th className="text-right font-normal">{vsBuild?.name}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="py-0.5">Expected</td>
                {[build, vsBuild].map((b, i) => {
                  const e = b ? expectedOf(b.id) : null
                  return (
                    <td key={i} className={`text-right ${e === null ? '' : pnlClass(e)}`}>
                      {e === null ? '–' : fmtPct(e)}
                    </td>
                  )
                })}
              </tr>
              <tr>
                <td className="py-0.5">On {path.name}</td>
                {[
                  { b: build, r: mine },
                  { b: vsBuild, r: other },
                ].map(({ b, r }, i) => (
                  <td key={i} className={`text-right ${r && b ? pnlClass(r.total - b.budget) : ''}`}>
                    {r && b ? `${fmtUsd(r.total)} (${fmtPct(r.total / b.budget - 1)})` : '–'}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="py-0.5">Debt paid</td>
                <td className="text-right">{mine ? fmtUsd(mine.debt) : '–'}</td>
                <td className="text-right">{other ? fmtUsd(other.debt) : '–'}</td>
              </tr>
              <tr>
                <td className="py-0.5">Budget</td>
                <td className="text-right">{fmtUsd(build.budget)}</td>
                <td className="text-right">{vsBuild ? fmtUsd(vsBuild.budget) : '–'}</td>
              </tr>
            </tbody>
          </table>
          {sharesRun && <p className="mt-1 text-muted-foreground">All shares with {fmtUsd(build.budget)}: {fmtUsd(sharesRun.total)} ({fmtPct(sharesRun.total / build.budget - 1)}).</p>}
        </div>
        <div className="rounded-md border bg-background p-3">
          <h2 className="mb-1 text-sm font-semibold">What each leg added on this path</h2>
          {[
            { b: build, run: mine },
            { b: vsBuild, run: other },
          ].map(({ b, run }) =>
            b ? (
              <div key={b.id} className="mb-2">
                <div className="font-medium">{b.name}</div>
                <table className="w-full tabular-nums">
                  <tbody>
                    {contribRows(b, run).map((r) => (
                      <tr key={r.label}>
                        <td className="py-0.5">{r.label}</td>
                        <td className={`text-right ${pnlClass(r.value)}`}>{fmtUsd(r.value)}</td>
                      </tr>
                    ))}
                    <tr className="border-t font-semibold">
                      <td className="py-0.5">Total vs {fmtUsd(b.budget)}</td>
                      <td className={`text-right ${pnlClass((run?.total ?? b.budget) - b.budget)}`}>{fmtUsd((run?.total ?? b.budget) - b.budget)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : null,
          )}
        </div>
        {side}
      </aside>
    </div>
  )
}
