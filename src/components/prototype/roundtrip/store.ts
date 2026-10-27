// PROTOTYPE (throwaway). Builds and Price Paths in the rt_ tables: read, save, delete, check, and the first-use seed.
// Server only. The seed is scenarios/iren/data/roundtrip-v2-seed.json, written by scenarios/iren/analysis/export_seed.py.

import { asc, eq } from 'drizzle-orm'
import type { BetterSQLite3Database } from 'drizzle-orm/better-sqlite3'

import type * as schema from '#/db/schema/index.ts'
import { rtBuild, rtBuildPath, rtLeg, rtPath, rtPathPoint, rtSleeve } from '#/db/schema/roundtrip.ts'
import { isRecord } from './model.ts'

type Db = BetterSQLite3Database<typeof schema>

export type Leg = { expiry: string; strike: number; kind: 'C' | 'P'; side: 1 | -1 }
type SleeveInput = { contracts: number; legs: Leg[] }
export type BuildInput = { name: string; description: string | null; budget: number; defaultPathId: string | null; sleeves: SleeveInput[] }
export type StoredBuild = Omit<BuildInput, 'sleeves'> & { id: string; sleeves: (SleeveInput & { id: string })[] }

export type Action = 'hold' | 'sell_cash' | 'sell_shares'
export type Point = { date: string; price: number; action: Action; sellPct: number | null }
export type PathInput = { name: string; description: string | null; weight: number; points: Point[] }
export type StoredPath = PathInput & { id: string }

/** scenarios/iren/data/roundtrip-v2-seed.json; every entry is checked by parseBuild or parsePath on the way in. */
export type Seed = { builds: ({ key: string } & Record<string, unknown>)[]; paths: ({ key: string } & Record<string, unknown>)[] }

function record(value: unknown, what: string): Record<string, unknown> {
  return isRecord(value) ? value : fail(`${what} must be an object`)
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

function fail(message: string): never {
  throw new Error(message)
}

function text(raw: unknown, what: string): string {
  return typeof raw === 'string' && raw.trim() ? raw.trim() : fail(`${what} is required`)
}

function optionalText(raw: unknown): string | null {
  return typeof raw === 'string' && raw.trim() ? raw.trim() : null
}

export function parseBuild(raw: unknown): BuildInput {
  const input = record(raw, 'a build')
  const budget = input.budget
  if (typeof budget !== 'number' || !Number.isInteger(budget) || budget < 1000) fail('budget must be whole dollars, at least $1,000')
  if (!Array.isArray(input.sleeves)) fail('sleeves must be a list')
  const sleeves = input.sleeves.map((s: unknown): SleeveInput => {
    const sleeve = record(s, 'a sleeve')
    const contracts = sleeve.contracts
    if (typeof contracts !== 'number' || !Number.isInteger(contracts) || contracts < 1) fail('contracts must be a whole number, at least 1')
    if (!Array.isArray(sleeve.legs) || sleeve.legs.length < 1 || sleeve.legs.length > 2) fail('a sleeve has one or two legs')
    const legs = sleeve.legs.map((l: unknown): Leg => {
      const leg = record(l, 'a leg')
      if (typeof leg.expiry !== 'string' || !ISO_DATE.test(leg.expiry)) fail('a leg needs an expiry date')
      if (typeof leg.strike !== 'number' || !(leg.strike > 0)) fail('a leg needs a strike above 0')
      if (leg.kind !== 'C' && leg.kind !== 'P') fail('a leg is a call or a put')
      if (leg.side !== 1 && leg.side !== -1) fail('a leg is long (+1) or short (-1)')
      return { expiry: leg.expiry, strike: leg.strike, kind: leg.kind, side: leg.side }
    })
    return { contracts, legs }
  })
  const defaultPathId = typeof input.defaultPathId === 'string' && input.defaultPathId ? input.defaultPathId : null
  return { name: text(input.name, 'name'), description: optionalText(input.description), budget, defaultPathId, sleeves }
}

export function parsePath(raw: unknown): PathInput {
  const input = record(raw, 'a path')
  const weight = input.weight
  if (typeof weight !== 'number' || !Number.isFinite(weight) || weight < 0) fail('weight must be 0 or more')
  if (!Array.isArray(input.points) || input.points.length === 0) fail('a path needs at least one point')
  const points = input.points.map((p: unknown): Point => {
    const point = record(p, 'a point')
    if (typeof point.date !== 'string' || !ISO_DATE.test(point.date)) fail('a point needs a date')
    if (typeof point.price !== 'number' || !(point.price > 0) || point.price > 100_000) fail('a point needs a price above 0')
    const action = point.action
    if (action !== 'hold' && action !== 'sell_cash' && action !== 'sell_shares') fail('an action is hold, sell_cash or sell_shares')
    const pct = point.sellPct
    if (action === 'hold') return { date: point.date, price: point.price, action, sellPct: null }
    if (typeof pct !== 'number' || !Number.isInteger(pct) || pct < 1 || pct > 100) fail('a sale needs a percent from 1 to 100')
    return { date: point.date, price: point.price, action, sellPct: pct }
  })
  if (new Set(points.map((p) => p.date)).size !== points.length) fail('two points share a date')
  return { name: text(input.name, 'name'), description: optionalText(input.description), weight, points: points.toSorted((a, b) => a.date.localeCompare(b.date)) }
}

export function listBuilds(db: Db): StoredBuild[] {
  const builds = db.select().from(rtBuild).orderBy(asc(rtBuild.createdAt), asc(rtBuild.id)).all()
  const sleeves = db.select().from(rtSleeve).orderBy(asc(rtSleeve.position)).all()
  const legs = db.select().from(rtLeg).all()
  const links = db.select().from(rtBuildPath).all()
  return builds.map((b) => ({
    id: b.id,
    name: b.name,
    description: b.description,
    budget: b.budget,
    defaultPathId: links.find((l) => l.buildId === b.id)?.pathId ?? null,
    sleeves: sleeves
      .filter((s) => s.buildId === b.id)
      .map((s) => ({
        id: s.id,
        contracts: s.contracts,
        legs: legs
          .filter((l) => l.sleeveId === s.id)
          .map((l): Leg => ({ expiry: l.expiry, strike: l.strike, kind: l.kind, side: l.side > 0 ? 1 : -1 }))
          .toSorted((x, y) => y.side - x.side || x.strike - y.strike),
      })),
  }))
}

/** Insert a Build, or replace an existing one's fields, Sleeves and default path. Returns its id. */
export function saveBuild(db: Db, input: BuildInput, id: string = crypto.randomUUID()): string {
  db.transaction((tx) => {
    tx.insert(rtBuild)
      .values({ id, name: input.name, description: input.description, budget: input.budget })
      .onConflictDoUpdate({ target: rtBuild.id, set: { name: input.name, description: input.description, budget: input.budget, updatedAt: new Date() } })
      .run()
    tx.delete(rtSleeve).where(eq(rtSleeve.buildId, id)).run()
    input.sleeves.forEach((s, position) => {
      const sleeveId = crypto.randomUUID()
      tx.insert(rtSleeve).values({ id: sleeveId, buildId: id, position, contracts: s.contracts }).run()
      for (const leg of s.legs) tx.insert(rtLeg).values({ sleeveId, ...leg }).run()
    })
    tx.delete(rtBuildPath).where(eq(rtBuildPath.buildId, id)).run()
    if (input.defaultPathId) tx.insert(rtBuildPath).values({ buildId: id, pathId: input.defaultPathId }).run()
  })
  return id
}

export function deleteBuild(db: Db, id: string): void {
  db.delete(rtBuild).where(eq(rtBuild.id, id)).run()
}

export function listPaths(db: Db): StoredPath[] {
  const paths = db.select().from(rtPath).orderBy(asc(rtPath.createdAt), asc(rtPath.id)).all()
  const points = db.select().from(rtPathPoint).orderBy(asc(rtPathPoint.date)).all()
  return paths.map((p) => ({
    id: p.id,
    name: p.name,
    description: p.description,
    weight: p.weight,
    points: points.filter((pt) => pt.pathId === p.id).map((pt) => ({ date: pt.date, price: pt.price, action: pt.action, sellPct: pt.sellPct })),
  }))
}

/** Insert a Price Path, or overwrite an existing one (the pencil's Save). Returns its id. */
export function savePath(db: Db, input: PathInput, id: string = crypto.randomUUID()): string {
  db.transaction((tx) => {
    tx.insert(rtPath)
      .values({ id, name: input.name, description: input.description, weight: input.weight })
      .onConflictDoUpdate({ target: rtPath.id, set: { name: input.name, description: input.description, weight: input.weight, updatedAt: new Date() } })
      .run()
    tx.delete(rtPathPoint).where(eq(rtPathPoint.pathId, id)).run()
    for (const p of input.points) tx.insert(rtPathPoint).values({ pathId: id, ...p }).run()
  })
  return id
}

export function deletePath(db: Db, id: string): void {
  db.delete(rtPath).where(eq(rtPath.id, id)).run()
}

/** First use: load v1's builds and the 11 paths when there are no Builds and no paths at all. */
export function seedIfEmpty(db: Db, seed: Seed): void {
  if (db.select({ id: rtBuild.id }).from(rtBuild).limit(1).all().length > 0) return
  if (db.select({ id: rtPath.id }).from(rtPath).limit(1).all().length > 0) return
  for (const p of seed.paths) savePath(db, parsePath(p), p.key)
  for (const b of seed.builds) saveBuild(db, parseBuild({ ...b, defaultPathId: null }), b.key)
}
