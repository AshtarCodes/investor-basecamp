# Scaffold

Run this while `package.json` is missing. Each step ends when its done line is true. The directory `AGENTS.md` files are the lasting rules; this file is the sequence that gets the tree there.

Generate into an empty directory, then copy the app into this repo. This repo already has a git history and these docs.

```bash
pnpm create @tanstack/start@latest investor-basecamp-scaffold \
  --package-manager pnpm \
  --framework React \
  --no-git \
  --no-examples \
  -y \
  --add-ons tanstack-query,shadcn,better-auth,drizzle \
  --add-on-config '{"drizzle":{"database":"sqlite"}}'
```

The checks step installs Oxlint, so this command selects add-ons only.

Copy the generated app in. Keep this repo's `AGENTS.md`, `docs/agents/`, and the nested `AGENTS.md` files when a generated file shares a path. The shadcn add-on may write `.cursorrules`; component rules live in `src/components/AGENTS.md`, so remove that generated file.

Done when this repo has `package.json`, `src/routes/__root.tsx`, `components.json`, `src/lib/auth.ts`, and `src/db/`, the plan's `AGENTS.md` files are unchanged, and `drizzle.config.ts` has `dialect: "sqlite"`.

## TypeScript 7

`pnpm exec tsc --version` prints 7. Bump the `typescript` dependency until it does. Set `engines.node` to `>=22`.

## Auth on the app database

The Better Auth add-on mounts the handler and may document a `pg` Pool. Wire the server instance as `src/lib/AGENTS.md` describes, and the schema as `src/db/AGENTS.md` describes. Generate the migration and apply it.

Done when a local sign-up inserts a user row in the SQLite file, and regenerating the auth schema leaves application tables in place.

## Checks and the test harness

Install `oxlint`, `oxlint-tsgolint` (the release line that matches TypeScript 7), `knip` 6, `lefthook`, `vitest`, `@testing-library/react`, `@testing-library/user-event`, `msw`, `@playwright/test`, and `better-sqlite3`. When this step ends, Oxlint is the only linter config in the repo.

`lefthook.yml` matches the Checks section of the root `AGENTS.md`. The `prepare` script runs `lefthook install`.

Add the shared harness under `tests/` and the Playwright project under `e2e/`, as `tests/AGENTS.md` and `e2e/AGENTS.md` describe. Prove each layer with one test: a pure function, a component interaction, a Drizzle write against in-memory SQLite, an outbound call handled by MSW, and one Playwright flow.

`.env.example` names `DATABASE_URL`, `BETTER_AUTH_SECRET`, and `BETTER_AUTH_URL`. `.env.local` and the SQLite file stay untracked.

Done when `pnpm exec tsc --noEmit`, `pnpm exec vitest run`, `pnpm exec knip`, and `pnpm exec playwright test` all pass, and a commit invokes the Lefthook pre-commit command.
