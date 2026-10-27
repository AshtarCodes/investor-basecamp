// PROTOTYPE (throwaway). Shell for /prototype/roundtrip: the yellow strip, the Builds on the left, the three views, the
// selection area (Price Paths), the edit area (the loaded path's points) and the builder. Plan:
// .scratch/iren-roundtrip-chart/plan-v2-one-timeline-and-my-builds.md.

import { useMemo, useState } from 'react'
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'

import { Button } from '#/components/ui/button.tsx'
import { PrototypeSwitcher } from '#/components/prototype/switcher.tsx'
import { deleteBuildFn, deletePathFn, getPage, requoteNow, runUnsaved, savePathFn, saveBuildFn, type PageData } from './api.ts'
import { BuilderPanel } from './builder-panel.tsx'
import { BuildsRail, type RailItem } from './builds-rail.tsx'
import { BASELINE_ID, DEBTS, fmtShare, runKey, scaleRun, type PathLike } from './model.ts'
import { PathsPanel, type Draft } from './paths-panel.tsx'
import { PointsEditor } from './points-editor.tsx'
import { describeBuild, expected } from './quotes.ts'
import type { BuildInput, Point } from './store.ts'
import type { PageState, YMode } from './types.ts'
import { VariantA } from './variant-a-path.tsx'
import { VariantB } from './variant-b-outcome.tsx'
import { VariantC } from './variant-c-compare.tsx'
import type { ViewProps } from './view.ts'

const VARIANTS = [
  { key: 'A', name: 'Legs over time' },
  { key: 'B', name: 'Outcome by path' },
  { key: 'C', name: 'Compare builds' },
] as const

const PAGE_KEY = ['roundtrip-page']
const message = (error: unknown) => (error instanceof Error ? error.message : String(error))

export function RoundtripPrototype({ state, update }: { state: PageState; update: (patch: Partial<PageState>) => void }) {
  const queryClient = useQueryClient()
  const page = useQuery({ queryKey: PAGE_KEY, queryFn: () => getPage(), staleTime: Number.POSITIVE_INFINITY, retry: false, refetchOnWindowFocus: false })
  const [draft, setDraft] = useState<Draft | null>(null)
  const [builder, setBuilder] = useState<{ id: string | null } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const unsaved = useQuery({
    queryKey: ['roundtrip-unsaved', draft?.points, page.data?.quoteSet.takenAt, page.data?.builds],
    queryFn: () => runUnsaved({ data: { path: { name: draft?.name ?? 'Unsaved', description: null, weight: 0, points: draft?.points ?? [] } } }),
    enabled: draft !== null && page.data !== undefined,
    placeholderData: keepPreviousData,
    retry: false,
    refetchOnWindowFocus: false,
  })

  async function act(job: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await job()
      await queryClient.invalidateQueries({ queryKey: PAGE_KEY })
      return true
    } catch (e) {
      setError(message(e))
      return false
    } finally {
      setBusy(false)
    }
  }

  if (page.isPending) return <Status text="Taking a live Quote Set from Schwab and running every Build on every path (a few seconds)…" />
  if (page.isError) return <Status text={`Could not load: ${message(page.error)}`} retry={() => void page.refetch()} />
  return (
    <Loaded
      data={page.data}
      state={state}
      update={update}
      draft={draft}
      setDraft={setDraft}
      unsavedRuns={draft ? unsaved.data : undefined}
      unsavedStatus={draft ? (unsaved.isFetching ? 'Running every Build on the unsaved path…' : unsaved.isError ? `Could not run the unsaved path: ${message(unsaved.error)}` : null) : null}
      builder={builder}
      setBuilder={setBuilder}
      busy={busy}
      error={error}
      setError={setError}
      act={act}
      requote={() =>
        void act(async () => {
          queryClient.setQueryData(PAGE_KEY, await requoteNow())
        })
      }
    />
  )
}

function Status({ text, retry }: { text: string; retry?: () => void }) {
  return (
    <div className="flex h-dvh flex-col">
      <div className="border-b-2 border-zinc-900 bg-yellow-300 px-3 py-2 font-mono text-xs font-bold text-zinc-900">PROTOTYPE CONTROLS</div>
      <div className="flex items-center gap-3 p-6 text-sm">
        <span>{text}</span>
        {retry && (
          <Button size="sm" variant="outline" onClick={retry}>
            Try again
          </Button>
        )}
      </div>
    </div>
  )
}

function Loaded({
  data,
  state,
  update,
  draft,
  setDraft,
  unsavedRuns,
  unsavedStatus,
  builder,
  setBuilder,
  busy,
  error,
  setError,
  act,
  requote,
}: {
  data: PageData
  state: PageState
  update: (patch: Partial<PageState>) => void
  draft: Draft | null
  setDraft: (draft: Draft | null) => void
  unsavedRuns: { runs: PageData['runs']; unpriceable: PageData['unpriceable'] } | undefined
  unsavedStatus: string | null
  builder: { id: string | null } | null
  setBuilder: (builder: { id: string | null } | null) => void
  busy: boolean
  error: string | null
  setError: (error: string | null) => void
  act: (job: () => Promise<unknown>) => Promise<boolean>
  requote: () => void
}) {
  const qs = data.quoteSet
  const today = new Date(qs.takenAt).toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
  const runs = useMemo(() => ({ ...data.runs, ...unsavedRuns?.runs }), [data.runs, unsavedRuns])
  const saved: PathLike[] = data.paths
  const source = draft?.sourceId ? saved.find((p) => p.id === draft.sourceId) : undefined
  const draftPath: PathLike | null = draft
    ? { id: 'unsaved', name: draft.mode === 'edit' ? `Editing · ${source?.name ?? draft.name}` : source ? `Unsaved · from ${source.name}` : `Unsaved · ${draft.name}`, description: draft.description, weight: 0, points: draft.points }
    : null
  const paths = draftPath ? [draftPath, ...saved] : saved
  const path: PathLike | undefined = (state.path === 'unsaved' ? draftPath : saved.find((p) => p.id === state.path)) ?? saved[0] ?? draftPath ?? undefined

  const views = useMemo(() => data.builds.map((b) => describeBuild(b, qs)), [data.builds, qs])
  const expectedOf = (id: string) => {
    const b = views.find((v) => v.id === id)
    return b ? expected(saved, (pid) => runs[runKey(id, pid, state.debt)]?.total, b.budget) : null
  }
  const items: RailItem[] = views
    .map((b) => {
      const onPath = path ? runs[runKey(b.id, path.id, state.debt)] : undefined
      return { build: b, expected: expectedOf(b.id), onPath: onPath ? onPath.total / b.budget - 1 : null, reason: data.unpriceable[b.id] ?? null }
    })
    .toSorted((a, b) => Number(a.reason !== null) - Number(b.reason !== null) || (b.expected ?? -Infinity) - (a.expected ?? -Infinity))
  const priced = items.filter((i) => !i.reason).map((i) => i.build)
  const build = priced.find((b) => b.id === state.build) ?? priced[0]

  const selectBuild = (id: string) => {
    const b = views.find((v) => v.id === id)
    update({ build: id, ...(b?.defaultPathId && saved.some((p) => p.id === b.defaultPathId) ? { path: b.defaultPathId } : {}) })
  }
  const editPoints = (points: Point[]) => {
    if (!path) return
    if (path.id === 'unsaved' && draft) setDraft({ ...draft, points })
    else {
      setDraft({ mode: 'copy', sourceId: path.id, name: path.name, description: path.description, weight: 0, points })
      update({ path: 'unsaved' })
    }
  }
  const savePath = (name: string) => {
    if (!draft) return
    let id = draft.mode === 'edit' ? draft.sourceId : null
    void act(async () => {
      id = (await savePathFn({ data: { id: id ?? undefined, path: { name, description: draft.description, weight: draft.weight, points: draft.points } } })).id
    }).then((ok) => {
      if (!ok || !id) return
      setDraft(null)
      update({ path: id })
    })
  }
  const deletePath = (id: string) =>
    void act(() => deletePathFn({ data: { id } })).then((ok) => {
      if (!ok) return
      if (draft?.sourceId === id) setDraft({ ...draft, mode: 'copy', sourceId: null })
      if (state.path === id) update({ path: saved.find((p) => p.id !== id)?.id ?? 'unsaved' })
    })
  const saveBuild = (input: BuildInput) => {
    let id = builder?.id ?? null
    void act(async () => {
      id = (await saveBuildFn({ data: { id: id ?? undefined, build: input } })).id
    }).then((ok) => {
      if (!ok || !id) return
      setBuilder(null)
      update({ build: id, ...(input.defaultPathId ? { path: input.defaultPathId } : {}) })
    })
  }

  const strip = (
    <div className="flex shrink-0 flex-wrap items-center gap-2 border-b-2 border-zinc-900 bg-yellow-300 px-3 py-2 text-xs text-zinc-900">
      <span className="font-mono font-bold">PROTOTYPE CONTROLS</span>
      <span className="font-mono">
        Priced {new Date(qs.takenAt).toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })} · IREN ${qs.spot.toFixed(2)}
      </span>
      <Button size="xs" variant="outline" disabled={busy} onClick={requote}>
        {busy ? 'Working…' : 'Re-quote now'}
      </Button>
      <span className="ml-2">Debt on 2027-11-30</span>
      {DEBTS.map((d) => (
        <Button key={d} size="xs" variant={state.debt === d ? 'default' : 'outline'} onClick={() => update({ debt: d })}>
          {d === '0.00' ? 'none' : fmtShare(Number(d))}
        </Button>
      ))}
      <span className="ml-2">Show</span>
      {(['usd', 'pct'] as YMode[]).map((y) => (
        <Button key={y} size="xs" variant={state.y === y ? 'default' : 'outline'} onClick={() => update({ y })}>
          {y === 'usd' ? 'Dollars' : 'Return %'}
        </Button>
      ))}
      <span className="font-mono">live Schwab chain, ask/bid entry, values from the batch pricing engine at Rule 2 IV</span>
      {error && (
        <span className="basis-full font-medium text-red-800" role="alert">
          {error}{' '}
          <button type="button" className="underline" onClick={() => setError(null)}>
            dismiss
          </button>
        </span>
      )}
    </div>
  )

  const side = (
    <PathsPanel
      paths={saved}
      draft={draft}
      loaded={path?.id ?? ''}
      busy={busy}
      onLoad={(id) => update({ path: id })}
      onEdit={(id) => {
        const p = saved.find((x) => x.id === id)
        if (!p) return
        setDraft({ mode: 'edit', sourceId: id, name: p.name, description: p.description, weight: p.weight, points: p.points })
        update({ path: 'unsaved' })
      }}
      onDelete={deletePath}
      onNew={() => {
        setDraft({ mode: 'copy', sourceId: null, name: 'New path', description: null, weight: 0, points: [{ date: '2027-12-31', price: Math.round(qs.spot), action: 'hold', sellPct: null }] })
        update({ path: 'unsaved' })
      }}
      onSave={savePath}
      onDiscard={() => {
        update({ path: draft?.sourceId && saved.some((p) => p.id === draft.sourceId) ? draft.sourceId : (saved[0]?.id ?? '') })
        setDraft(null)
      }}
    />
  )
  const below = path ? (
    <PointsEditor
      title={path.id === 'unsaved' ? `Points of ${path.name}` : `Points of ${path.name}`}
      points={path.points}
      today={today}
      spot={qs.spot}
      draftFields={path.id === 'unsaved' && draft ? { name: draft.name, description: draft.description, weight: draft.weight, editingName: draft.mode === 'edit' } : null}
      status={path.id === 'unsaved' ? unsavedStatus : null}
      onChange={editPoints}
      onFields={(fields) => draft && setDraft({ ...draft, ...fields })}
    />
  ) : null

  const props: ViewProps | null =
    build && path
      ? {
          state: { ...state, build: build.id, path: path.id },
          update,
          build,
          builds: priced,
          paths,
          path,
          run: (buildId, pathId = path.id) => runs[runKey(buildId, pathId, state.debt)],
          baseline: (budget, pathId = path.id) => {
            const r = runs[runKey(BASELINE_ID, pathId, state.debt)]
            return r ? scaleRun(r, budget) : undefined
          },
          expectedOf,
          side,
          below,
        }
      : null

  return (
    <div className="flex h-dvh flex-col">
      {strip}
      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-80 shrink-0 overflow-auto border-r bg-zinc-50 lg:block">
          <BuildsRail
            items={items}
            selected={build?.id ?? ''}
            pathName={path?.name ?? ''}
            onSelect={selectBuild}
            onNew={() => setBuilder({ id: null })}
            onEdit={(id) => setBuilder({ id })}
            onDelete={(id) => void act(() => deleteBuildFn({ data: { id } }))}
          />
        </aside>
        <main className="min-w-0 flex-1 overflow-auto bg-zinc-50 pb-20">
          {!props && (
            <div className="p-4 text-sm text-muted-foreground">
              {!path ? 'No price paths: add one.' : 'No Build could be priced. Add one with “New build”.'}
              <div className="max-w-md">{side}</div>
            </div>
          )}
          {props && state.variant === 'A' ? <VariantA {...props} /> : null}
          {props && state.variant === 'B' ? <VariantB {...props} /> : null}
          {props && state.variant === 'C' ? <VariantC {...props} /> : null}
        </main>
      </div>
      {builder && (
        <BuilderPanel
          quoteSet={qs}
          paths={saved}
          initial={builder.id ? (data.builds.find((b) => b.id === builder.id) ?? null) : null}
          busy={busy}
          error={error}
          onSave={saveBuild}
          onClose={() => (setBuilder(null), setError(null))}
        />
      )}
      <PrototypeSwitcher variants={VARIANTS} current={state.variant} onChange={(key) => update({ variant: VARIANTS.find((v) => v.key === key)?.key ?? 'A' })} />
    </div>
  )
}
