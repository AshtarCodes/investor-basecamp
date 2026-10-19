import Database from 'better-sqlite3'
import { drizzle } from 'drizzle-orm/better-sqlite3'
import { migrate } from 'drizzle-orm/better-sqlite3/migrator'

import * as schema from '#/db/schema/index.ts'

export function createTestDb() {
  const db = drizzle(new Database(':memory:'), { schema })
  migrate(db, { migrationsFolder: 'drizzle' })
  return db
}
