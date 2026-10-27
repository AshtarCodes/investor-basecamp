import { expect, test } from 'vitest'

import { createTestDb } from '../../../../tests/db.ts'
import seed from '../../../../scenarios/iren/data/roundtrip-v2-seed.json'
import { deleteBuild, deletePath, listBuilds, listPaths, parseBuild, parsePath, saveBuild, savePath, seedIfEmpty } from './store.ts'

const jan29 = (strike: number, side: 1 | -1 = 1) => ({ expiry: '2029-01-19', strike, kind: 'C' as const, side })
const hold = (date: string, price: number) => ({ date, price, action: 'hold' as const, sellPct: null })

test('the seed loads v1 builds and the 11 paths once', () => {
  const db = createTestDb()
  seedIfEmpty(db, seed)
  seedIfEmpty(db, seed)
  const builds = listBuilds(db)
  const paths = listPaths(db)
  expect(builds).toHaveLength(29)
  expect(paths).toHaveLength(11)
  const heavy = builds.find((b) => b.name === 'R60/B20/S20 R3 B2 · Jan 2029')
  expect(heavy?.sleeves.map((s) => [s.contracts, s.legs.map((l) => `${l.side > 0 ? '+' : '-'}${l.strike}`)])).toEqual([
    [2, ['+40']],
    [6, ['+90']],
    [1, ['+25', '-75']],
  ])
  expect(paths.reduce((sum, p) => sum + p.weight, 0)).toBe(100)
  expect(paths.find((p) => p.name === 'Base')?.points.map((p) => p.action)).toEqual(['hold', 'sell_cash', 'sell_cash', 'hold'])
})

test('a build saves with its sleeves and default path, and an edit replaces its sleeves', () => {
  const db = createTestDb()
  const pathId = savePath(db, { name: 'Mine', description: null, weight: 0, points: [hold('2027-12-31', 60)] })
  const id = saveBuild(db, { name: 'Two calls', description: 'test', budget: 5000, defaultPathId: pathId, sleeves: [{ contracts: 2, legs: [jan29(40)] }] })
  saveBuild(db, { name: 'A spread', description: null, budget: 5000, defaultPathId: null, sleeves: [{ contracts: 3, legs: [jan29(25), jan29(75, -1)] }] }, id)
  const [b] = listBuilds(db)
  expect(b).toMatchObject({ id, name: 'A spread', budget: 5000, defaultPathId: null })
  expect(b?.sleeves.map((s) => s.legs.length)).toEqual([2])
})

test('deleting a path clears it as a default; deleting a build removes it', () => {
  const db = createTestDb()
  const pathId = savePath(db, { name: 'Mine', description: null, weight: 5, points: [hold('2027-12-31', 60)] })
  const id = saveBuild(db, { name: 'B', description: null, budget: 10000, defaultPathId: pathId, sleeves: [{ contracts: 1, legs: [jan29(40)] }] })
  deletePath(db, pathId)
  expect(listBuilds(db)[0]?.defaultPathId).toBeNull()
  deleteBuild(db, id)
  expect(listBuilds(db)).toEqual([])
})

test('editing a path in place overwrites its points', () => {
  const db = createTestDb()
  const id = savePath(db, { name: 'Mine', description: null, weight: 0, points: [hold('2027-06-30', 40), hold('2027-12-31', 60)] })
  savePath(db, { name: 'Mine', description: 'edited', weight: 10, points: [{ date: '2027-12-31', price: 80, action: 'sell_shares', sellPct: 50 }] }, id)
  expect(listPaths(db)).toEqual([{ id, name: 'Mine', description: 'edited', weight: 10, points: [{ date: '2027-12-31', price: 80, action: 'sell_shares', sellPct: 50 }] }])
})

test('inputs are checked: budget, contracts, legs, points', () => {
  const ok = { name: 'B', description: null, budget: 10000, defaultPathId: null, sleeves: [{ contracts: 1, legs: [jan29(40)] }] }
  expect(parseBuild(ok)).toEqual(ok)
  expect(() => parseBuild({ ...ok, budget: 999 })).toThrow('budget')
  expect(() => parseBuild({ ...ok, sleeves: [{ contracts: 0, legs: [jan29(40)] }] })).toThrow('contracts')
  expect(() => parseBuild({ ...ok, sleeves: [{ contracts: 1, legs: [jan29(40), jan29(50), jan29(60)] }] })).toThrow('legs')
  const path = { name: 'P', description: null, weight: 0, points: [hold('2027-12-31', 60)] }
  expect(parsePath(path)).toEqual(path)
  expect(() => parsePath({ ...path, points: [{ date: '2027-12-31', price: 60, action: 'sell_cash', sellPct: null }] })).toThrow('percent')
  expect(() => parsePath({ ...path, points: [hold('2027-12-31', 60), hold('2027-12-31', 70)] })).toThrow('date')
  expect(() => parsePath({ ...path, points: [] })).toThrow('point')
})
