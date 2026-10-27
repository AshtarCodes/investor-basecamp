// PROTOTYPE (throwaway). Left column: every Build, sorted by Expected, with "+ New build" and edit and delete on each card.
// A Build that can't be priced today stays in the list, greyed, with the reason.

import { useEffect, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'

import { Button } from '#/components/ui/button.tsx'
import { fmtPct, fmtUsd, pnlClass } from './model.ts'
import type { BuildView } from './quotes.ts'

export type RailItem = { build: BuildView; expected: number | null; onPath: number | null; reason: string | null }

function legSummary(build: BuildView): string {
  const parts = build.sleeves.map((s) => `${s.contracts}×${s.label.replace(/^\w{3} \d{4} /, '').replace(' call spread', ' spr').replace(' call', '')}`)
  if (build.shares > 0.5) parts.push(`${Math.round(build.shares)} sh`)
  return parts.join(' · ')
}

export function BuildsRail({ items, selected, pathName, onSelect, onNew, onEdit, onDelete }: { items: RailItem[]; selected: string; pathName: string; onSelect: (id: string) => void; onNew: () => void; onEdit: (id: string) => void; onDelete: (id: string) => void }) {
  const [confirming, setConfirming] = useState<string | null>(null)
  const order = items.filter((i) => !i.reason).map((i) => i.build.id)

  useEffect(() => {
    document.querySelector(`[data-build="${CSS.escape(selected)}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [selected])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target
      if (target instanceof HTMLElement && (target.tagName === 'INPUT' || target.tagName === 'SELECT' || target.tagName === 'TEXTAREA')) return
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
      event.preventDefault()
      const i = Math.max(0, order.indexOf(selected))
      const next = order[(i + (event.key === 'ArrowDown' ? 1 : -1) + order.length) % order.length]
      if (next) onSelect(next)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  return (
    <div className="flex flex-col gap-2 p-3 text-xs">
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={onNew}>
          <Plus className="size-3.5" aria-hidden /> New build
        </Button>
        <span className="text-muted-foreground">sorted by Expected; ↑/↓ steps through</span>
      </div>
      {items.map(({ build, expected, onPath, reason }) => {
        const isSelected = build.id === selected
        return (
          <div key={build.id} data-build={build.id} className={`rounded-md border bg-background ${isSelected ? 'border-zinc-900 ring-1 ring-zinc-900' : ''} ${reason ? 'opacity-60' : ''}`}>
            <button type="button" disabled={reason !== null} onClick={() => onSelect(build.id)} className="w-full p-2 text-left transition hover:bg-muted/50 disabled:cursor-not-allowed disabled:hover:bg-transparent">
              <div className="flex items-start gap-1">
                <span className="min-w-0 flex-1 font-mono font-semibold">{build.name}</span>
                <span className={`shrink-0 rounded px-1 text-[10px] ${build.badge === 'Mixed' ? 'bg-violet-100 text-violet-800' : build.badge === 'Shares' ? 'bg-zinc-100 text-zinc-700' : 'bg-sky-100 text-sky-800'}`}>{build.badge}</span>
              </div>
              {build.description && <div className="mt-0.5 line-clamp-2 text-muted-foreground">{build.description}</div>}
              <div className="mt-0.5 text-muted-foreground">{legSummary(build)}</div>
              {reason ? (
                <div className="mt-1 font-medium text-red-700">Not priced: {reason}</div>
              ) : (
                <dl className="mt-1.5 grid grid-cols-3 gap-x-1 tabular-nums">
                  <div>
                    <dt className="text-[10px] text-muted-foreground">Expected</dt>
                    <dd className={expected === null ? '' : pnlClass(expected)}>{expected === null ? '–' : fmtPct(expected)}</dd>
                  </div>
                  <div className="col-span-1">
                    <dt className="truncate text-[10px] text-muted-foreground" title={`On ${pathName}`}>
                      On loaded path
                    </dt>
                    <dd className={onPath === null ? '' : pnlClass(onPath)}>{onPath === null ? '–' : fmtPct(onPath)}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] text-muted-foreground">Budget</dt>
                    <dd>{fmtUsd(build.budget)}</dd>
                  </div>
                </dl>
              )}
            </button>
            <div className="flex items-center justify-end gap-1 border-t px-1 py-0.5">
              {confirming === build.id ? (
                <>
                  <span className="mr-auto pl-1 text-red-700">Delete this build?</span>
                  <Button size="xs" variant="destructive" onClick={() => (setConfirming(null), onDelete(build.id))}>
                    Delete
                  </Button>
                  <Button size="xs" variant="ghost" onClick={() => setConfirming(null)}>
                    Keep
                  </Button>
                </>
              ) : (
                <>
                  <Button size="xs" variant="ghost" aria-label={`Edit ${build.name}`} onClick={() => onEdit(build.id)}>
                    <Pencil className="size-3" aria-hidden />
                  </Button>
                  <Button size="xs" variant="ghost" aria-label={`Delete ${build.name}`} onClick={() => setConfirming(build.id)}>
                    <Trash2 className="size-3" aria-hidden />
                  </Button>
                </>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
