// PROTOTYPE (throwaway). The edit area under the chart: the loaded path's points, one row each with date, price, Action
// and percent. Changing a saved path's point makes the unsaved copy; the shell decides that, this only reports the points.

import { useState } from 'react'
import { X } from 'lucide-react'

import { Button } from '#/components/ui/button.tsx'
import type { Action, Point } from './store.ts'

const PCTS = [10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 100]
const ACTIONS: { value: Action; label: string }[] = [
  { value: 'hold', label: 'Hold' },
  { value: 'sell_cash', label: 'Sell → cash' },
  { value: 'sell_shares', label: 'Sell → shares' },
]
const ISO = /^\d{4}-\d{2}-\d{2}$/
const validPrice = (n: number) => Number.isFinite(n) && n > 0 && n <= 100_000

function withAction(point: Point, action: Action): Point {
  return action === 'hold' ? { ...point, action, sellPct: null } : { ...point, action, sellPct: point.sellPct ?? 50 }
}

function PointRow({ point, today, taken, onChange, onRemove }: { point: Point; today: string; taken: Set<string>; onChange: (next: Point) => void; onRemove: () => void }) {
  const [price, setPrice] = useState<string | null>(null) // what is typed while the box has focus
  const past = point.date <= today
  return (
    <tr className={past ? 'text-muted-foreground' : ''}>
      <td className="py-0.5 pr-1">
        <input
          type="date"
          aria-label="Date"
          value={point.date}
          onChange={(e) => {
            const d = e.target.value
            if (ISO.test(d) && !taken.has(d)) onChange({ ...point, date: d })
          }}
          className="rounded border border-zinc-300 bg-background px-1 py-0.5"
        />
      </td>
      <td className="pr-1">
        $
        <input
          type="number"
          aria-label={`IREN price on ${point.date}`}
          min={1}
          step="1"
          value={price ?? String(point.price)}
          onBlur={() => setPrice(null)}
          onChange={(e) => {
            setPrice(e.target.value)
            const n = Number(e.target.value)
            if (validPrice(n)) onChange({ ...point, price: Math.round(n * 100) / 100 })
          }}
          className="ml-0.5 w-20 rounded border border-zinc-300 bg-background px-1 py-0.5"
        />
      </td>
      <td className="pr-1">
        <select aria-label={`Action on ${point.date}`} value={point.action} onChange={(e) => onChange(withAction(point, ACTIONS.find((a) => a.value === e.target.value)?.value ?? 'hold'))} className="rounded border border-zinc-300 bg-background px-1 py-0.5">
          {ACTIONS.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </select>
      </td>
      <td className="pr-1">
        {point.action !== 'hold' && (
          <select aria-label={`Percent sold on ${point.date}`} value={point.sellPct ?? 50} onChange={(e) => onChange({ ...point, sellPct: Number(e.target.value) })} className="rounded border border-zinc-300 bg-background px-1 py-0.5">
            {PCTS.map((p) => (
              <option key={p} value={p}>
                {p}%
              </option>
            ))}
          </select>
        )}
      </td>
      <td className="pr-1">{past && <span title="Points on or before the Quote Set's day are kept but skipped">skipped (past)</span>}</td>
      <td>
        <button type="button" aria-label={`Remove the point on ${point.date}`} onClick={onRemove} className="rounded-full p-0.5 hover:bg-zinc-200">
          <X className="size-3" />
        </button>
      </td>
    </tr>
  )
}

export function PointsEditor({
  title,
  points,
  today,
  spot,
  draftFields,
  status,
  onChange,
  onFields,
}: {
  title: string
  points: Point[]
  today: string
  spot: number
  draftFields: { name: string; description: string | null; weight: number; editingName: boolean } | null // shown for the unsaved copy
  status: string | null // the unsaved copy's run, or an error
  onChange: (points: Point[]) => void
  onFields: (fields: { name?: string; description?: string | null; weight?: number }) => void
}) {
  const [date, setDate] = useState('2027-06-30')
  const [price, setPrice] = useState('60')
  const n = Number(price)
  const taken = new Set(points.map((p) => p.date))
  const canAdd = ISO.test(date) && !taken.has(date) && validPrice(n)
  const set = (next: Point[]) => onChange(next.toSorted((a, b) => a.date.localeCompare(b.date)))
  const add = () => canAdd && set([...points, { date, price: Math.round(n * 100) / 100, action: 'hold', sellPct: null }])

  return (
    <section className="mt-3 rounded-md border bg-background p-3 text-xs" aria-label="Path points">
      <h2 className="mb-1 text-sm font-semibold">{title}</h2>
      <p className="mb-2 text-muted-foreground">
        IREN starts at today's ${spot.toFixed(2)} and moves in a straight line (in percentage terms) between the points, then stays at the last price. Sell X% sells that share of what is left in every option sleeve, rounded half up to whole contracts; shares are never sold. Changing a point of a saved path makes an unsaved copy; its pencil edits it in place.
      </p>
      {draftFields && (
        <div className="mb-2 flex flex-wrap items-end gap-2">
          {draftFields.editingName && (
            <label className="flex flex-col gap-0.5">
              <span className="text-muted-foreground">Name</span>
              <input value={draftFields.name} onChange={(e) => onFields({ name: e.target.value })} className="w-56 rounded border border-zinc-300 bg-background px-1 py-0.5" />
            </label>
          )}
          <label className="flex min-w-64 flex-1 flex-col gap-0.5">
            <span className="text-muted-foreground">Description</span>
            <input value={draftFields.description ?? ''} onChange={(e) => onFields({ description: e.target.value || null })} className="rounded border border-zinc-300 bg-background px-1 py-0.5" />
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="text-muted-foreground">Weight</span>
            <input type="number" min={0} step="1" value={draftFields.weight} onChange={(e) => Number(e.target.value) >= 0 && onFields({ weight: Number(e.target.value) })} className="w-20 rounded border border-zinc-300 bg-background px-1 py-0.5" />
          </label>
        </div>
      )}
      <table className="tabular-nums">
        <thead>
          <tr className="text-left text-muted-foreground">
            <th className="font-normal">Date</th>
            <th className="font-normal">IREN price</th>
            <th className="font-normal">Action</th>
            <th className="font-normal">Sell</th>
            <th className="font-normal">
              <span className="sr-only">Note</span>
            </th>
            <th className="font-normal">
              <span className="sr-only">Remove</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {points.map((p) => (
            <PointRow
              key={p.date}
              point={p}
              today={today}
              taken={taken}
              onChange={(next) => set(points.map((q) => (q.date === p.date ? next : q)))}
              onRemove={() => points.length > 1 && set(points.filter((q) => q.date !== p.date))}
            />
          ))}
        </tbody>
      </table>
      <div className="mt-2 flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">Add a point: date</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="rounded border border-zinc-400 bg-background px-1 py-0.5" />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">IREN price ($)</span>
          <input type="number" min={1} step="1" value={price} onChange={(e) => setPrice(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && add()} className="w-24 rounded border border-zinc-400 bg-background px-1 py-0.5" />
        </label>
        <Button size="sm" variant="outline" disabled={!canAdd} onClick={add}>
          Add point
        </Button>
      </div>
      {status && <p className="mt-2 text-muted-foreground">{status}</p>}
    </section>
  )
}
