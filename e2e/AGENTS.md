# Browser flows

Playwright covers a journey a user can take: navigation, forms, and a session that survives a reload. `playwright.config.ts` at the repo root points its `testDir` here and its `baseURL` at the app dev server.

A signed-in spec starts from storage state produced by the sign-in UI against the app's test database. The setup project signs in once and writes that state; later specs reuse the file.

One behavior, one spec. Assert what the user sees after the action. Vitest layers for the pieces of the flow stay in `tests/AGENTS.md`.
