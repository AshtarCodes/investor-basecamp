# Where does the app run, and how do you reach it?

Type: grilling
Status: resolved

## Question

Does the app run only on your laptop at `https://127.0.0.1:<port>`, or on an always-on machine (home server or VPS) behind a real HTTPS domain that you can also reach from your phone?

This has to be decided before registering the Schwab app, because the OAuth callback URL is fixed at registration and changing it triggers re-approval. It also decides:

- how the weekly Schwab reconnect happens (which browser, which device)
- how hard the deployment has to be locked down (Better Auth hardening, encrypting Schwab tokens at rest, backups of the SQLite file)
- whether the 15-minute auto-sync can run while your laptop is closed

## Answer

Settled in a grilling session on 2026-10-18. Key fact: reading positions requires Schwab's "Accounts and Trading Production" product, so the token that syncs positions can also place orders.

**Where it runs**

- On your laptop, which is sometimes closed. Nothing syncs while it's closed, which is fine because sync happens on open. A VPS may come later.
- Reached from the laptop and your phone over Tailscale. Nothing is publicly exposed.

**The app's one address**

- The app's only address is a Tailscale Service, `https://basecamp.<tailnet>.ts.net`, used on the laptop too. The app listens on `127.0.0.1` over plain HTTP, and `tailscale serve --service=svc:basecamp` handles HTTPS with a certificate Tailscale issues.
- Passkeys and the Schwab callback are both tied to that address. Moving to a VPS means advertising the same Service from the VPS: no Schwab re-approval and no passkey re-enrollment.
- No domain for now. If you ever leave Tailscale, we accept one Schwab re-approval and re-enroll passkeys.
- Tailnet setup order: switch the tailnet DNS name to the randomized two-word name (for example `yak-bebop.ts.net`), enable HTTPS, then create and approve the `basecamp` Service. The name becomes part of the app's address, appears in public certificate logs, and is permanent in practice.
- Callbacks to register with Schwab: `https://basecamp.<tailnet>.ts.net/api/schwab/callback` for the app, and `https://127.0.0.1:<port>/api/schwab/callback` for throwaway scripts only.

**Protecting a token that can trade**

- The app contains no code that calls a Schwab order endpoint.
- Schwab tokens are encrypted at rest in SQLite. Reconnect and disconnect are explicit in the app.
- Secrets live in Bitwarden Secrets Manager (free plan), in one project, "investor-basecamp": the Schwab app key and secret, the OpenAI key, the Better Auth secret, the token-encryption key, the `age` backup key, and the R2 credentials. The app reads them at startup through one read-only machine account and keeps them in memory only. That machine account's access token sits in macOS Keychain on the laptop, and would become a system service credential on a VPS. `.env.local` holds non-secret settings only.

**Sign-in**

- Passkeys are the main sign-in: Face ID on the phone and Touch ID on the laptop, synced through iCloud Keychain, using Better Auth's passkey plugin. A passkey counts as both factors.
- Fallback: email and password plus an authenticator-app code (TOTP), remembered on trusted devices for 30 days.

**Backups**

- A full copy of the database (minus Schwab tokens), taken once a day while the app runs and caught up at the next start if a day was missed. Kept in `~/Library/Application Support/investor-basecamp/backups/`: 30 daily copies plus one per month indefinitely.
- `pnpm backup:push` encrypts any backups not yet uploaded with `age` and sends them to Cloudflare R2. `pnpm backup:restore` restores from a local or R2 backup.
- The Portfolio page shows "last backup" and "last uploaded" as quiet status, with no warning banner.
- There's no Time Machine. Until `backup:push` runs, backups don't survive losing the laptop.

## Comments

**2026-10-18, correction found while working "Register the Schwab developer app":** a Tailscale Service can only be hosted by a device with a tag-based identity, and the laptop is a user device. The address `https://basecamp.<tailnet>.ts.net` and everything tied to it (the Schwab callback, passkeys) stands, because a dedicated node named `basecamp` produces the same address. The `tailscale serve --service` mechanism above is reopened as "How does the laptop serve the basecamp address?".
