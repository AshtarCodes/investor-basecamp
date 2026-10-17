# Tests

Vitest runs the unit, component, service, and external layers. A full browser journey is Playwright: `e2e/AGENTS.md`.

Pick the layer by what can fail:

| Layer | What it exercises | How |
| --- | --- | --- |
| Unit | Pure logic | Vitest, co-located `*.test.ts` |
| Component | UI behavior | Vitest, Testing Library, user-event, co-located `*.test.tsx` |
| Service | Database reads and writes | Vitest plus a new in-memory SQLite database |
| External | Outbound HTTP | Vitest plus MSW |

A change ships with the layer that can fail it.

## Harness

Shared setup lives in this directory: a render helper that mounts the same Query client the app uses, an MSW server, and a database factory. The factory opens `better-sqlite3` on `:memory:`, applies the Drizzle migrations, and returns a Drizzle client. Each service test gets its own database. MSW handlers for a test live next to that test; the server lifecycle is shared.

Component tests render the component with its props. A test of a route is the one that mounts the router.

## Docs

- Vitest: https://vitest.dev/llms.txt
- React Testing Library: https://testing-library.com/docs/react-testing-library/intro
- MSW: https://mswjs.io/docs/
