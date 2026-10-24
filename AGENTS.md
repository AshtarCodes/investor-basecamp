## Agent skills

### Issue tracker

Issues live as markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Stack

TypeScript 7 on TanStack Start (React, Vite), with TanStack Query, shadcn/ui, Drizzle on SQLite, and self-hosted Better Auth. Package manager is pnpm.

Scaffold when `package.json` is missing: `docs/agents/setup.md`.

### Read next

- Routes, loaders, server functions, Query: `src/AGENTS.md`
- Components and shadcn/ui: `src/components/AGENTS.md`
- Schema, client, migrations: `src/db/AGENTS.md`
- Session and the auth handler: `src/lib/AGENTS.md`
- Vitest layers: `tests/AGENTS.md`
- Playwright flows: `e2e/AGENTS.md`
- Pricing engine (Python, `uv`): `packages/pricing-engine/AGENTS.md`

### Checks

Oxlint lints. Type-aware rules come from `oxlint-tsgolint` built for the same TypeScript 7 that `tsc` typechecks with. Knip v6 reports unused files, exports, and dependencies; clear a report by removing that code or dependency. Lefthook runs Oxlint on staged files at commit, and runs `tsc`, Vitest, and Knip at push. The Python engine (`packages/pricing-engine/AGENTS.md`) adds Ruff on its staged files at commit, and ty and pytest at push.

A tool that imports the TypeScript programmatic API is satisfied with `@typescript/typescript6` beside the TypeScript 7 compiler, using the alias from the TypeScript 7 announcement, so `tsc` stays on 7.

## Docs

Prefer a library's `llms.txt` when looking it up. The link for an area library is in that directory's `AGENTS.md`.

Knip: https://www.everydev.ai/tools/knip/llms.txt

TypeScript 7, Oxlint, and Lefthook have no `llms.txt`:

- TypeScript: https://www.typescriptlang.org/docs/
- Oxlint: https://oxc.rs/docs/guide/usage/linter.html
- Lefthook: https://lefthook.dev/

React Testing Library, MSW, and Playwright have no `llms.txt`. Their links are in `tests/AGENTS.md` and `e2e/AGENTS.md`.
