import { eq } from 'drizzle-orm'
import { expect, test } from 'vitest'

import { createTestDb } from '../../../tests/db.ts'
import { session, user } from './auth.ts'

test('deleting a user deletes their sessions', () => {
  const db = createTestDb()
  db.insert(user)
    .values({ id: 'u1', name: 'Me', email: 'me@example.com' })
    .run()
  db.insert(session)
    .values({
      id: 's1',
      token: 'token-1',
      userId: 'u1',
      expiresAt: new Date(Date.now() + 60_000),
      updatedAt: new Date(),
    })
    .run()

  db.delete(user).where(eq(user.id, 'u1')).run()

  expect(db.select().from(session).all()).toEqual([])
})
