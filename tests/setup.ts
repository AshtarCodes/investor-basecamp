import { afterAll, afterEach } from 'vitest'

import { server } from './msw.ts'

// Listen before test modules load: clients that capture `fetch` at import keep the unpatched one otherwise.
server.listen({ onUnhandledFrame: 'error' })
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
