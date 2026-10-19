import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'

import { server } from '../../tests/msw.ts'
import { submitCredentials } from './credentials.ts'

test('a rejected sign-in returns the server message', async () => {
  server.use(
    http.post('http://localhost:3000/api/auth/sign-in/email', () =>
      HttpResponse.json(
        { code: 'INVALID_EMAIL_OR_PASSWORD', message: 'Invalid email or password' },
        { status: 401 },
      ),
    ),
  )

  await expect(
    submitCredentials('sign-in', { email: 'me@example.com', password: 'nope-nope' }),
  ).resolves.toBe('Invalid email or password')
})
