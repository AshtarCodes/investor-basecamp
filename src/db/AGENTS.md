# Database

SQLite through Drizzle and `better-sqlite3`. `src/db/index.ts` is the app client, a singleton aimed at the file in `DATABASE_URL`. That file stays untracked.

## Schema

`src/db/schema/index.ts` is the barrel `drizzle.config.ts` points at. Better Auth's CLI writes `src/db/schema/auth.ts`; regenerating that file replaces it. Application tables are sibling modules exported from the barrel, so a regeneration leaves them in place.

`drizzle/` holds migrations. Read the generated SQL, then apply it with Drizzle Kit.

## Tests

Service tests use the in-memory factory in `tests/AGENTS.md`. This singleton stays the app database.

## Docs

Drizzle ORM: https://orm.drizzle.team/llms.txt
