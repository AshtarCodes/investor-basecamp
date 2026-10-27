// PROTOTYPE (throwaway). Server functions for /prototype/roundtrip: the page's data, "Re-quote now", a run of the unsaved
// path, and saving or deleting Builds and Price Paths. Dev server only (they spawn the Schwab CLI and the engine).

import { createServerFn } from '@tanstack/react-start'

import { isRecord } from './model.ts'
import type { QuoteSet } from './quotes.ts'
import type { StoredBuild, StoredPath } from './store.ts'
import type { Run } from './types.ts'

export type PageData = {
  quoteSet: QuoteSet
  builds: StoredBuild[]
  paths: StoredPath[]
  runs: Record<string, Run> // `${build id}|${path id}|${debt}`; the all-shares baseline is build '__shares'
  unpriceable: Record<string, string>
}

/** `{id?, <field>}` from a request body; the field itself is checked by parseBuild or parsePath. */
function withId(raw: unknown, field: string): { id: string | undefined; value: unknown } {
  const input = isRecord(raw) ? raw : {}
  return { id: typeof input.id === 'string' && input.id ? input.id : undefined, value: input[field] }
}

function devOnly() {
  if (!import.meta.env.DEV) throw new Error('The roundtrip prototype spawns the Schwab CLI and the engine, so it runs only in the dev server.')
}

async function load(fresh: boolean): Promise<PageData> {
  devOnly()
  const { db } = await import('#/db/index.ts')
  const store = await import('./store.ts')
  const server = await import('./server.ts')
  const seed = (await import('../../../../scenarios/iren/data/roundtrip-v2-seed.json')).default
  store.seedIfEmpty(db, seed)
  const quoteSet = fresh ? await server.requote() : await server.currentQuoteSet()
  const builds = store.listBuilds(db)
  const paths = store.listPaths(db)
  const { runs, unpriceable } = await server.runAll([...builds, server.BASELINE], paths)
  return { quoteSet, builds, paths, runs, unpriceable }
}

export const getPage = createServerFn({ method: 'GET' }).handler(() => load(false))

export const requoteNow = createServerFn({ method: 'POST' }).handler(() => load(true))

/** Every Build and the baseline on the unsaved path, keyed `${build id}|unsaved|${debt}`. */
export const runUnsaved = createServerFn({ method: 'POST' })
  .validator((raw: unknown) => ({ path: withId(raw, 'path').value }))
  .handler(async ({ data }) => {
    devOnly()
    const { db } = await import('#/db/index.ts')
    const store = await import('./store.ts')
    const server = await import('./server.ts')
    const path = store.parsePath({ name: 'Unsaved', ...(isRecord(data.path) ? data.path : {}) })
    return server.runAll([...store.listBuilds(db), server.BASELINE], [{ id: 'unsaved', ...path }])
  })

export const saveBuildFn = createServerFn({ method: 'POST' })
  .validator((raw: unknown) => withId(raw, 'build'))
  .handler(async ({ data }) => {
    devOnly()
    const { db } = await import('#/db/index.ts')
    const store = await import('./store.ts')
    return { id: store.saveBuild(db, store.parseBuild(data.value), data.id) }
  })

export const deleteBuildFn = createServerFn({ method: 'POST' })
  .validator((raw: unknown) => ({ id: withId(raw, 'id').id ?? '' }))
  .handler(async ({ data }) => {
    devOnly()
    const { db } = await import('#/db/index.ts')
    const store = await import('./store.ts')
    store.deleteBuild(db, data.id)
    return { ok: true }
  })

export const savePathFn = createServerFn({ method: 'POST' })
  .validator((raw: unknown) => withId(raw, 'path'))
  .handler(async ({ data }) => {
    devOnly()
    const { db } = await import('#/db/index.ts')
    const store = await import('./store.ts')
    return { id: store.savePath(db, store.parsePath(data.value), data.id) }
  })

export const deletePathFn = createServerFn({ method: 'POST' })
  .validator((raw: unknown) => ({ id: withId(raw, 'id').id ?? '' }))
  .handler(async ({ data }) => {
    devOnly()
    const { db } = await import('#/db/index.ts')
    const store = await import('./store.ts')
    store.deletePath(db, data.id)
    return { ok: true }
  })
