// PROTOTYPE (throwaway). The selection area: every Price Path, with a pencil (edit in place) and a trash can, "+ New path",
// and the one unsaved copy at the top with Save and Discard.

import { useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'

import { Button } from '#/components/ui/button.tsx'
import type { PathLike } from './model.ts'
import type { Point } from './store.ts'

/** The unsaved copy: a copy of a path (or a new one), or a preset being edited in place through its pencil. */
export type Draft = { mode: 'copy' | 'edit'; sourceId: string | null; name: string; description: string | null; weight: number; points: Point[] }

export function PathsPanel({
  paths,
  draft,
  loaded,
  busy,
  onLoad,
  onEdit,
  onDelete,
  onNew,
  onSave,
  onDiscard,
}: {
  paths: PathLike[]
  draft: Draft | null
  loaded: string
  busy: boolean
  onLoad: (id: string) => void
  onEdit: (id: string) => void
  onDelete: (id: string) => void
  onNew: () => void
  onSave: (name: string) => void
  onDiscard: () => void
}) {
  const [confirming, setConfirming] = useState<string | null>(null)
  const [name, setName] = useState('')
  const total = paths.reduce((sum, p) => sum + p.weight, 0)
  const source = draft?.sourceId ? paths.find((p) => p.id === draft.sourceId) : undefined
  const draftTitle = draft ? (draft.mode === 'edit' ? `Editing · ${source?.name ?? draft.name}` : source ? `Unsaved · from ${source.name}` : `Unsaved · ${draft.name}`) : ''

  return (
    <section className="rounded-md border bg-background p-3 text-xs" aria-label="Price paths">
      <h2 className="mb-1 text-sm font-semibold">Price paths</h2>
      <p className="mb-2 text-muted-foreground">Load one onto the chart. Expected weighs every path with weight above 0 ({total} in all, scaled to 100%).</p>
      <ul className="flex flex-col gap-1">
        {draft && (
          <li className={`rounded border border-violet-300 bg-violet-50 p-1.5 ${loaded === 'unsaved' ? 'ring-1 ring-violet-500' : ''}`}>
            <button type="button" className="w-full text-left font-medium text-violet-900" onClick={() => onLoad('unsaved')}>
              {draftTitle}
            </button>
            <div className="mt-1 flex flex-wrap items-center gap-1">
              {draft.mode === 'copy' && (
                <input aria-label="Name for the new path" placeholder="Name it to save" value={name} onChange={(e) => setName(e.target.value)} className="min-w-0 flex-1 rounded border border-violet-300 bg-background px-1 py-0.5" />
              )}
              <Button size="xs" disabled={busy || (draft.mode === 'copy' && !name.trim())} onClick={() => (onSave(draft.mode === 'copy' ? name.trim() : draft.name), setName(''))}>
                {draft.mode === 'edit' ? 'Save over it' : 'Save'}
              </Button>
              <Button size="xs" variant="ghost" disabled={busy} onClick={() => (onDiscard(), setName(''))}>
                Discard
              </Button>
            </div>
          </li>
        )}
        {paths.map((p) => (
          <li key={p.id} className={`flex items-center gap-1 rounded border ${loaded === p.id ? 'border-zinc-900 bg-yellow-50' : ''}`}>
            {confirming === p.id ? (
              <>
                <span className="flex-1 px-1.5 py-1 text-red-700">Delete {p.name}?</span>
                <Button size="xs" variant="destructive" disabled={busy} onClick={() => (setConfirming(null), onDelete(p.id))}>
                  Delete
                </Button>
                <Button size="xs" variant="ghost" onClick={() => setConfirming(null)}>
                  Keep
                </Button>
              </>
            ) : (
              <>
                <button type="button" title={p.description ?? undefined} onClick={() => onLoad(p.id)} className="flex min-w-0 flex-1 items-center gap-1 px-1.5 py-1 text-left hover:bg-muted/60">
                  <span className="min-w-0 truncate">{p.name}</span>
                  <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">{p.weight > 0 ? `w ${p.weight}` : ''}</span>
                </button>
                <Button size="icon-xs" variant="ghost" aria-label={`Edit ${p.name}`} disabled={busy} onClick={() => onEdit(p.id)}>
                  <Pencil aria-hidden />
                </Button>
                <Button size="icon-xs" variant="ghost" aria-label={`Delete ${p.name}`} disabled={busy} onClick={() => setConfirming(p.id)}>
                  <Trash2 aria-hidden />
                </Button>
              </>
            )}
          </li>
        ))}
      </ul>
      <Button size="xs" variant="outline" className="mt-2" disabled={busy} onClick={onNew}>
        <Plus aria-hidden /> New path
      </Button>
    </section>
  )
}
