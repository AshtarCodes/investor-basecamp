// PROTOTYPE (throwaway). The /prototype/roundtrip Builds and Price Paths (plan-v2). Throwing the prototype away means
// dropping the rt_ tables. No prices are stored: a Quote Set is taken live and kept in server memory.

import { sql } from 'drizzle-orm'
import { integer, primaryKey, real, sqliteTable, text } from 'drizzle-orm/sqlite-core'

const createdAt = () =>
  integer('created_at', { mode: 'timestamp_ms' })
    .default(sql`(cast(unixepoch('subsecond') * 1000 as integer))`)
    .notNull()
const updatedAt = () =>
  integer('updated_at', { mode: 'timestamp_ms' })
    .default(sql`(cast(unixepoch('subsecond') * 1000 as integer))`)
    .$onUpdate(() => new Date())
    .notNull()

export const rtBuild = sqliteTable('rt_build', {
  id: text('id').primaryKey(),
  name: text('name').notNull(),
  description: text('description'),
  budget: integer('budget').default(10000).notNull(),
  createdAt: createdAt(),
  updatedAt: updatedAt(),
})

export const rtSleeve = sqliteTable('rt_sleeve', {
  id: text('id').primaryKey(),
  buildId: text('build_id')
    .notNull()
    .references(() => rtBuild.id, { onDelete: 'cascade' }),
  position: integer('position').notNull(),
  contracts: integer('contracts').notNull(),
})

// keyed by expiry, strike and kind rather than an OCC symbol, so a Build carries over to any day's Quote Set
export const rtLeg = sqliteTable(
  'rt_leg',
  {
    sleeveId: text('sleeve_id')
      .notNull()
      .references(() => rtSleeve.id, { onDelete: 'cascade' }),
    expiry: text('expiry').notNull(), // YYYY-MM-DD
    strike: real('strike').notNull(),
    kind: text('kind', { enum: ['C', 'P'] }).notNull(),
    side: integer('side').notNull(), // +1 long, -1 short
  },
  (table) => [primaryKey({ columns: [table.sleeveId, table.expiry, table.strike, table.kind] })],
)

export const rtPath = sqliteTable('rt_path', {
  id: text('id').primaryKey(),
  name: text('name').notNull(),
  description: text('description'),
  weight: real('weight').default(0).notNull(),
  createdAt: createdAt(),
  updatedAt: updatedAt(),
})

export const rtPathPoint = sqliteTable(
  'rt_path_point',
  {
    pathId: text('path_id')
      .notNull()
      .references(() => rtPath.id, { onDelete: 'cascade' }),
    date: text('date').notNull(), // YYYY-MM-DD
    price: real('price').notNull(),
    action: text('action', { enum: ['hold', 'sell_cash', 'sell_shares'] }).notNull(),
    sellPct: integer('sell_pct'), // null for hold
  },
  (table) => [primaryKey({ columns: [table.pathId, table.date] })],
)

// many to many, but the app keeps one row per Build for now: the path loaded when that Build is selected
export const rtBuildPath = sqliteTable(
  'rt_build_path',
  {
    buildId: text('build_id')
      .notNull()
      .references(() => rtBuild.id, { onDelete: 'cascade' }),
    pathId: text('path_id')
      .notNull()
      .references(() => rtPath.id, { onDelete: 'cascade' }),
  },
  (table) => [primaryKey({ columns: [table.buildId, table.pathId] })],
)
