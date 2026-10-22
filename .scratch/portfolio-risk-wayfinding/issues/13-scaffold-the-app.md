# Scaffold the app so prototypes run on the real stack

Type: task
Status: resolved

## Question

The UI prototypes need a running TanStack Start app with shadcn/ui, so that a variation chosen in a prototype carries into the build as is. Run the whole sequence in `docs/agents/setup.md`, up to every step's done line: generate and copy the app, TypeScript 7, Better Auth on the SQLite database, and the checks and test harness.

This ticket does, rather than decides. It earns its place by unblocking [What should the Portfolio view look like?](08-portfolio-view-prototype.md) and [What should the Scenario and Compare views look like?](09-scenario-and-compare-views-prototype.md). Record anything a later ticket depends on: package versions that differ from the docs, commands that changed, and deviations from `setup.md`.

## Answer

Done 2026-10-19. Commit `a9958f3` on `master`: "Scaffold the TanStack Start app with auth on SQLite, checks, and a test in each layer." `package.json`, `src/routes/__root.tsx`, `components.json`, `src/lib/auth.ts`, `src/db/`, and `drizzle.config.ts` (`dialect: "sqlite"`) are in place. TypeScript is 7.0.2. A local sign-up writes a user row; regenerating the auth schema leaves application tables as sibling modules. Each Vitest layer has one test, plus one Playwright session flow. Oxlint is the only linter.

**Deviations later tickets should know:**

- shadcn/ui's `cn` helper is the `cn` npm package, re-exported from `src/lib/utils.ts`. Generated `src/components/ui/*` files import `cn` from `"cn"` directly, not from `#/lib/utils`.
- The generator's `.cursorrules` was not left in the repo.
- Lefthook `pre-commit` runs Oxlint on staged files; `pre-push` runs `tsc`, Vitest, and Knip. The scaffold commit itself is the Lefthook-invoking commit `setup.md` asked for.
