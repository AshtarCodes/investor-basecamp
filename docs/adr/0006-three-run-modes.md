# Three run modes

`pnpm dev` is `http://localhost:3000` on loopback, with email and password for one seeded user, and Schwab fixtures unless `SCHWAB_MODE=live`. `pnpm dev:auth` is that same origin with passkeys only, relying party id `localhost`, and Schwab fixtures forced. `pnpm start`, after `pnpm build`, is the instance at `https://basecamp.ojos-alhena.ts.net`: passkeys only, relying party id `basecamp.ojos-alhena.ts.net`, live Schwab, and its own database. No mode is an auth bypass. Email and password are enabled only behind an explicit dev flag, and startup refuses that flag when `NODE_ENV=production` or the bind address is not loopback.

Each mode has its own database, auth secret, and Better Auth `advanced.cookiePrefix`. The seeded dev user exists only in the dev database. `BETTER_AUTH_URL`, `trustedOrigins`, and the passkey `rpID` and `origin` come from the environment. `trustedOrigins` lists the origins that mode is actually browsed from.

The app talks to Schwab through one client interface. `SCHWAB_MODE` picks `live` or `fixture` at startup. The default is `fixture`. The fixture implementation never reads or writes the Keychain item. Fixtures are recorded from real responses, including error and expired-token cases.

The CLI is the only process that runs the Schwab browser login. Schwab OAuth tokens live in one Keychain item. A refresh writes the returned tokens back before the next request. The app reads that item or asks the CLI. It never logs in itself. The Schwab dev CLI lives in `tools/schwab/`, runs with `uv`, and loads the app key and secret through the Bitwarden Secrets Manager Python SDK ([README](https://github.com/bitwarden/sdk-sm/blob/main/languages/python/README.md)), using the Bitwarden machine-account access token from Keychain `bws-access-token` and organization id from `bws-org-id`, not from `.env.local`. The served app will use the same SDK pattern at startup when it needs those secrets. The CLI callback is `https://127.0.0.1:8182/api/schwab/callback`. The app callback is `https://basecamp.ojos-alhena.ts.net/api/schwab/callback`. Both are registered with no trailing slash.

The login listener binds to loopback only, checks the OAuth `state` value, accepts one callback, and then shuts down. It never logs the authorization code or the tokens. The mkcert root CA private key stays in mkcert's CAROOT, outside this repository and outside any synced folder. It is not copied into the repo.

`tailscale serve` points only at the `pnpm start` port. Dev binds to loopback. Tailscale Funnel is not used. A passkey enrolled on `localhost` and a passkey enrolled on `basecamp.ojos-alhena.ts.net` are separate credentials. That Tailscale name stays permanent.

## Assumptions

These are not stated as fact. The behavior beside them is kept because it is safe either way.

- Schwab refuses `localhost` as a callback host. The CLI uses the registered `127.0.0.1` callback regardless.
- An aborted OAuth flow invalidates the current token. The CLI stays the only login, and a second login is not used as a test.
