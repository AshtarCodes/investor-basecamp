# App

TanStack Start, file routes, React. The Query client is the one mounted by `src/integrations/tanstack-query/`.

## Routes

Route files live in `src/routes`. A route file is thin: `createFileRoute`, search validation, the loader, and a render that hands props to a component from `src/components`. The router plugin rewrites `routeTree.gen.ts` and the path passed to `createFileRoute` when files move.

A loader loads what the route needs before paint. A server function is the server-only boundary (database, session, other secrets). Query owns the client cache: mutations, refetch, and the dehydrated state from `@tanstack/react-router-ssr-query`. One fetcher serves both the loader and the query for a resource.

## Session gate

A page or server function that requires a session follows `src/lib/AGENTS.md`.

## Docs

- TanStack: https://tanstack.com/llms.txt
- TanStack Start: https://tanstack.com/start/latest/llms.txt
- TanStack Query: https://tanstack.com/query/latest/llms.txt
