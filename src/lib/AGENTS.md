# Auth

Self-hosted Better Auth. Server instance: `src/lib/auth.ts`. Browser client: `src/lib/auth-client.ts`. HTTP handler: `src/routes/api/auth/$.ts`, which forwards the request to `auth.handler`.

`auth.ts` uses `drizzleAdapter` on the client from `src/db/`, with `provider: "sqlite"`. `tanstackStartCookies()` is the last entry in `plugins`. Browser sign-in and sign-up go through `authClient`. The server reads the session with `auth.api.getSession` and the incoming request headers.

`getSession` is the shared server function. A protected route calls it from `beforeLoad` and redirects when the session is absent. A protected server function calls it and returns unauthorized when the session is absent.

`BETTER_AUTH_SECRET` and `BETTER_AUTH_URL` come from the environment. The secret stays out of git. Schema generation for these tables is in `src/db/AGENTS.md`.

`src/lib/utils.ts` is the shadcn `cn` helper; its rules are in `src/components/AGENTS.md`.
