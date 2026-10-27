// PROTOTYPE (throwaway). Server memory for /prototype/roundtrip: the Quote Set and every engine run made on it.
// The Quote Set is one live `pnpm schwab option chain` (never offline); a run is scenarios/iren/analysis/roundtrip_run.py,
// which prices through the pricing engine's batch worker. Both spawn processes, so this works only in `vite dev`.

import { spawn } from 'node:child_process'

import type { QuoteSet } from './quotes.ts'
import type { Leg, Point, StoredBuild } from './store.ts'
import type { Run } from './types.ts'

const DEBTS = [0, 0.1, 0.25, 0.5]
const FIRST_EXPIRY = '2027-06-01' // the builder offers expiries from Jun 2027 on
/** The all-shares baseline every view compares with: $10,000 in shares, scaled to a Build's budget by the page. */
export const BASELINE = { id: '__shares', budget: 10_000, sleeves: [] as { contracts: number; legs: Leg[] }[] }

type EngineBuild = { budget: number; sleeves: { contracts: number; legs: Leg[] }[] }
type EnginePath = { points: Point[] }

let quoteSet: Promise<QuoteSet> | null = null
let runs = new Map<string, Run>() // `${build content}|${path content}|${debt}`, for the current Quote Set
const unpriceable = new Map<string, string>() // build content -> reason
let queue: Promise<unknown> = Promise.resolve() // one engine run at a time

function exec(command: string, args: string[], input?: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: process.cwd() })
    let out = ''
    let err = ''
    child.stdout.on('data', (chunk: Buffer) => (out += chunk.toString()))
    child.stderr.on('data', (chunk: Buffer) => (err = (err + chunk.toString()).slice(-800)))
    child.on('error', reject)
    child.on('close', (code) => (code === 0 ? resolve(out) : reject(new Error(err.trim() || `${command} exited with code ${code}`))))
    if (input !== undefined) child.stdin.end(input)
  })
}

export function currentQuoteSet(): Promise<QuoteSet> {
  quoteSet ??= exec('pnpm', ['-s', 'schwab', 'option', 'chain', '--symbol', 'IREN', '--from', FIRST_EXPIRY])
    .then((out): QuoteSet => JSON.parse(out.slice(out.indexOf('{'))))
    .catch((error: unknown) => {
      quoteSet = null // the next load tries again
      throw new Error(`Could not take a Quote Set from Schwab (is the CLI signed in? pnpm schwab login): ${error instanceof Error ? error.message : String(error)}`)
    })
  return quoteSet
}

/** "Re-quote now": a new Quote Set, and every run made again on it. */
export function requote(): Promise<QuoteSet> {
  quoteSet = null
  runs = new Map()
  unpriceable.clear()
  return currentQuoteSet()
}

const buildContent = (b: EngineBuild) => JSON.stringify([b.budget, b.sleeves.map((s) => [s.contracts, s.legs])])
const pathContent = (p: EnginePath) => JSON.stringify(p.points)

export type Runs = { runs: Record<string, Run>; unpriceable: Record<string, string> }

/** Every Build on every path at every debt share, keyed `${build id}|${path id}|${debt}`; only new ones are run. */
export async function runAll(builds: (StoredBuild | typeof BASELINE)[], paths: ({ id: string } & EnginePath)[]): Promise<Runs> {
  const qs = await currentQuoteSet()
  const today = new Date(qs.takenAt).toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
  paths = paths.filter((p) => p.points.some((pt) => pt.date > today)) // the engine skips points on or before today
  const todoBuilds = new Map<string, EngineBuild>()
  const todoPaths = new Map<string, EnginePath>()
  for (const b of builds) {
    const bk = buildContent(b)
    if (unpriceable.has(bk)) continue
    for (const p of paths) {
      if (!runs.has(`${bk}|${pathContent(p)}|0.00`)) {
        todoBuilds.set(bk, b)
        todoPaths.set(pathContent(p), p)
      }
    }
  }
  if (todoBuilds.size > 0) {
    const job = queue.then(async () => {
      const bKeys = [...todoBuilds.keys()]
      const pKeys = [...todoPaths.keys()]
      const request = {
        quoteSet: qs,
        builds: bKeys.map((k, i) => ({ id: `b${i}`, budget: todoBuilds.get(k)!.budget, sleeves: todoBuilds.get(k)!.sleeves.map((s, j) => ({ id: `s${j}`, contracts: s.contracts, legs: s.legs })) })),
        paths: pKeys.map((k, j) => ({ id: `p${j}`, weight: 0, points: todoPaths.get(k)!.points })),
        debts: DEBTS,
      }
      const out: Runs = JSON.parse(await exec('python3', ['scenarios/iren/analysis/roundtrip_run.py'], JSON.stringify(request)))
      for (const [id, why] of Object.entries(out.unpriceable)) unpriceable.set(bKeys[Number(id.slice(1))] ?? '', why)
      for (const [key, run] of Object.entries(out.runs)) {
        const [b = '', p = '', f = ''] = key.split('|')
        runs.set(`${bKeys[Number(b.slice(1))]}|${pKeys[Number(p.slice(1))]}|${f}`, run)
      }
    })
    queue = job.catch(() => undefined)
    await job
  }
  const result: Runs = { runs: {}, unpriceable: {} }
  for (const b of builds) {
    const bk = buildContent(b)
    const why = unpriceable.get(bk)
    if (why) {
      result.unpriceable[b.id] = why
      continue
    }
    for (const p of paths) {
      for (const f of DEBTS) {
        const run = runs.get(`${bk}|${pathContent(p)}|${f.toFixed(2)}`)
        if (run) result.runs[`${b.id}|${p.id}|${f.toFixed(2)}`] = run
      }
    }
  }
  return result
}
