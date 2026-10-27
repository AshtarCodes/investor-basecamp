// PROTOTYPE (throwaway). The builder: a Build's name, description, budget, default path and Sleeves, priced live from the
// Quote Set as you go. Shares fill whatever the Sleeves leave, and Save is blocked above the budget.

import { useMemo, useState } from 'react'
import { Plus, X } from 'lucide-react'

import { Button } from '#/components/ui/button.tsx'
import { fmtShare, fmtUsd, type PathLike } from './model.ts'
import { fmtExpiry, legsCost, sleeveLabel, type QuoteSet } from './quotes.ts'
import type { BuildInput, Leg, StoredBuild } from './store.ts'

type Row = { type: 'call' | 'spread'; expiry: string; strike: number; upper: number; contracts: number }

const SPREAD_WARN = 0.1

function legsOf(row: Row): Leg[] {
  const long: Leg = { expiry: row.expiry, strike: row.strike, kind: 'C', side: 1 }
  return row.type === 'call' ? [long] : [long, { expiry: row.expiry, strike: row.upper, kind: 'C', side: -1 }]
}

function rowOf(sleeve: StoredBuild['sleeves'][number]): Row {
  const [long, short] = sleeve.legs
  return { type: short ? 'spread' : 'call', expiry: long?.expiry ?? '', strike: long?.strike ?? 0, upper: short?.strike ?? 0, contracts: sleeve.contracts }
}

export function BuilderPanel({ quoteSet, paths, initial, busy, error, onSave, onClose }: { quoteSet: QuoteSet; paths: PathLike[]; initial: StoredBuild | null; busy: boolean; error: string | null; onSave: (build: BuildInput) => void; onClose: () => void }) {
  const chain = useMemo(() => {
    const byExpiry = new Map<string, number[]>()
    for (const q of quoteSet.contracts) if (q.kind === 'C' && q.bid !== null && q.ask !== null) byExpiry.set(q.expiry, [...(byExpiry.get(q.expiry) ?? []), q.strike])
    return new Map([...byExpiry].toSorted(([a], [b]) => a.localeCompare(b)).map(([e, ks]) => [e, [...new Set(ks)].toSorted((a, b) => a - b)]))
  }, [quoteSet])
  const expiries = [...chain.keys()]
  const firstRow = (): Row => {
    const expiry = expiries[expiries.length - 1] ?? ''
    const strikes = chain.get(expiry) ?? []
    const strike = strikes.find((k) => k >= quoteSet.spot) ?? strikes[0] ?? 0
    return { type: 'call', expiry, strike, upper: strikes.find((k) => k > strike * 2) ?? strikes[strikes.length - 1] ?? 0, contracts: 1 }
  }

  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [budget, setBudget] = useState(String(initial?.budget ?? 10_000))
  const [defaultPathId, setDefaultPathId] = useState(initial?.defaultPathId ?? '')
  const [rows, setRows] = useState<Row[]>(initial ? initial.sleeves.map(rowOf) : [firstRow()])

  const budgetN = Number(budget)
  const budgetOk = Number.isInteger(budgetN) && budgetN >= 1000
  const priced = rows.map((row) => {
    const c = legsCost(quoteSet, legsOf(row))
    return c ? { perContract: c.cost * 100, spreadPct: c.cost > 0 ? c.spread / c.cost : null } : null
  })
  const spent = priced.reduce((sum, p, i) => sum + (p ? p.perContract * (rows[i]?.contracts ?? 0) : 0), 0)
  const left = budgetN - spent
  const unpricedRow = priced.some((p) => p === null)
  const badSpread = rows.some((r) => r.type === 'spread' && r.upper <= r.strike)
  const canSave = !busy && name.trim() !== '' && budgetOk && left >= 0 && !unpricedRow && !badSpread && rows.every((r) => Number.isInteger(r.contracts) && r.contracts >= 1)

  const setRow = (i: number, patch: Partial<Row>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const save = () => onSave({ name: name.trim(), description: description.trim() || null, budget: budgetN, defaultPathId: defaultPathId || null, sleeves: rows.map((r) => ({ contracts: r.contracts, legs: legsOf(r) })) })

  return (
    <dialog open className="fixed inset-0 z-40 m-0 flex h-full max-h-none w-full max-w-none justify-end bg-black/30 p-0" aria-label={initial ? `Edit ${initial.name}` : 'New build'}>
      <div className="flex h-full w-full max-w-3xl flex-col gap-3 overflow-auto bg-background p-4 text-xs shadow-xl">
        <div className="flex items-center">
          <h2 className="text-base font-semibold">{initial ? `Edit ${initial.name}` : 'New build'}</h2>
          <Button size="icon-sm" variant="ghost" className="ml-auto" aria-label="Close" onClick={onClose}>
            <X aria-hidden />
          </Button>
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <label className="flex flex-col gap-0.5">
            <span className="text-muted-foreground">Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} className="rounded border border-zinc-300 px-1.5 py-1" />
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="text-muted-foreground">Budget ($, whole dollars, at least $1,000)</span>
            <input type="number" min={1000} step="1000" value={budget} onChange={(e) => setBudget(e.target.value)} aria-invalid={!budgetOk} className="rounded border border-zinc-300 px-1.5 py-1 aria-invalid:border-red-500" />
          </label>
          <label className="flex flex-col gap-0.5 sm:col-span-2">
            <span className="text-muted-foreground">Description</span>
            <input value={description} onChange={(e) => setDescription(e.target.value)} className="rounded border border-zinc-300 px-1.5 py-1" />
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="text-muted-foreground">Default path (loaded when you select this build)</span>
            <select value={defaultPathId} onChange={(e) => setDefaultPathId(e.target.value)} className="rounded border border-zinc-300 px-1 py-1">
              <option value="">None: keep the loaded path</option>
              {paths.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <table className="w-full tabular-nums">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="py-1 font-normal">Type</th>
              <th className="font-normal">Expiry</th>
              <th className="font-normal">Strike(s)</th>
              <th className="font-normal">Contracts</th>
              <th className="text-right font-normal">Per contract</th>
              <th className="text-right font-normal">Total</th>
              <th className="text-right font-normal">Of budget</th>
              <th className="text-right font-normal">Bid/ask</th>
              <th className="font-normal">
                <span className="sr-only">Remove</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const strikes = chain.get(row.expiry) ?? []
              const p = priced[i]
              const total = p ? p.perContract * row.contracts : null
              return (
                <tr key={i} className="border-b">
                  <td className="py-1 pr-1">
                    <select aria-label="Type" value={row.type} onChange={(e) => setRow(i, { type: e.target.value === 'spread' ? 'spread' : 'call' })} className="rounded border border-zinc-300 px-1 py-0.5">
                      <option value="call">Call</option>
                      <option value="spread">Call spread</option>
                    </select>
                  </td>
                  <td className="pr-1">
                    <select aria-label="Expiry" value={row.expiry} onChange={(e) => setRow(i, { expiry: e.target.value })} className="rounded border border-zinc-300 px-1 py-0.5">
                      {!chain.has(row.expiry) && <option value={row.expiry}>{row.expiry ? `${fmtExpiry(row.expiry)} (not listed)` : 'Pick one'}</option>}
                      {expiries.map((e) => (
                        <option key={e} value={e}>
                          {fmtExpiry(e)} ({e.slice(8)})
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="pr-1">
                    <select aria-label={row.type === 'spread' ? 'Long strike' : 'Strike'} value={row.strike} onChange={(e) => setRow(i, { strike: Number(e.target.value) })} className="rounded border border-zinc-300 px-1 py-0.5">
                      {!strikes.includes(row.strike) && <option value={row.strike}>${row.strike} (not listed)</option>}
                      {strikes.map((k) => (
                        <option key={k} value={k}>
                          ${k}
                        </option>
                      ))}
                    </select>
                    {row.type === 'spread' && (
                      <>
                        {' / '}
                        <select aria-label="Short strike" value={row.upper} onChange={(e) => setRow(i, { upper: Number(e.target.value) })} className="rounded border border-zinc-300 px-1 py-0.5">
                          {!strikes.includes(row.upper) && <option value={row.upper}>${row.upper} (not listed)</option>}
                          {strikes
                            .filter((k) => k > row.strike)
                            .map((k) => (
                              <option key={k} value={k}>
                                ${k}
                              </option>
                            ))}
                        </select>
                      </>
                    )}
                  </td>
                  <td className="pr-1">
                    <input type="number" aria-label="Contracts" min={1} step="1" value={row.contracts} onChange={(e) => setRow(i, { contracts: Math.max(0, Math.floor(Number(e.target.value))) })} className="w-16 rounded border border-zinc-300 px-1 py-0.5" />
                  </td>
                  <td className="text-right">{p ? fmtUsd(p.perContract) : <span className="text-red-700">no quote</span>}</td>
                  <td className="text-right">{total === null ? '–' : fmtUsd(total)}</td>
                  <td className="text-right">{total === null || !budgetOk ? '–' : fmtShare(total / budgetN)}</td>
                  <td className={`text-right ${p?.spreadPct !== null && p?.spreadPct !== undefined && p.spreadPct > SPREAD_WARN ? 'font-semibold text-amber-700' : ''}`} title="Bid/ask spread as a share of the entry cost">
                    {p?.spreadPct === null || p?.spreadPct === undefined ? '–' : `${(p.spreadPct * 100).toFixed(1)}%${p.spreadPct > SPREAD_WARN ? ' ⚠' : ''}`}
                  </td>
                  <td className="pl-1">
                    <Button size="icon-xs" variant="ghost" aria-label={`Remove ${sleeveLabel(legsOf(row))}`} onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                      <X aria-hidden />
                    </Button>
                  </td>
                </tr>
              )
            })}
            <tr>
              <td colSpan={5} className="py-1 text-muted-foreground">
                Shares with the rest, at IREN ${quoteSet.spot.toFixed(2)}
              </td>
              <td className={`text-right ${left < 0 ? 'font-semibold text-red-700' : ''}`}>{budgetOk ? fmtUsd(left) : '–'}</td>
              <td className="text-right">{budgetOk && left >= 0 ? fmtShare(left / budgetN) : '–'}</td>
              <td colSpan={2} className="text-right text-muted-foreground">
                {budgetOk && left >= 0 ? `${(left / quoteSet.spot).toFixed(1)} shares` : ''}
              </td>
            </tr>
          </tbody>
        </table>
        <div>
          <Button size="sm" variant="outline" onClick={() => setRows([...rows, firstRow()])}>
            <Plus aria-hidden /> Add sleeve
          </Button>
        </div>
        <p className="text-muted-foreground">
          Entry is the ask for long legs and the bid for short ones, from the Quote Set taken {new Date(quoteSet.takenAt).toLocaleString('en-US')}. A spread is long the first strike and short the second. Bid/ask above {SPREAD_WARN * 100}% of the cost is marked ⚠.
        </p>
        {left < 0 && budgetOk && <p className="font-medium text-red-700">Over budget by {fmtUsd(-left)}: remove contracts or raise the budget.</p>}
        {error && (
          <p className="font-medium text-red-700" role="alert">
            Could not save: {error}
          </p>
        )}
        <div className="flex gap-2">
          <Button disabled={!canSave} onClick={save}>
            {busy ? 'Saving…' : 'Save build'}
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </dialog>
  )
}
