# Pull real Schwab payloads for your accounts

Type: task
Status: ready-for-human
Blocked by: 04

## Question

Run a throwaway script that completes the OAuth flow and saves the raw responses from `/trader/v1/accounts/accountNumbers`, `/trader/v1/accounts?fields=positions`, one `/marketdata/v1/quotes` call for an option you hold, and one `/marketdata/v1/pricehistory` call. Redact account numbers and keep the dumps out of git.

The facts the answer must record, because the sync mapping waits on them:

- How a short option Position reports `averagePrice` and quantity (sign, per share or per contract), so Total Cost comes out signed correctly.
- The balance fields actually present for each of your account types (cash, margin, IRA), and which one is Net Liquidation Value.
- The exact option symbol format, and whether index options (SPX, XSP) come back with a different root or settlement flag.
- Any asset types in your accounts that v1 can't price.
- How Schwab's IV and greeks on the quote compare with what thinkorswim shows for the same contract.
- The units of the quote's dividend fields (`divAmount`, `divPayAmount`, `divYield`, `nextDivExDate`) and of the option chain's `volatility` and `interestRate`, for a dividend-paying stock you hold. "Which pricing models and inputs should the engine use?" couldn't confirm them.
- Any hint of Schwab's rate source and day count. For example: does the chain's `interestRate` vary by expiry, and do days-to-expiry values include the time of day?

The script is throwaway: keep it on a branch, not on master, and link it from the answer.

## Comments

**2026-10-22, plan:** The throwaway branch script is replaced by a dev CLI we keep. Not resolved. Run modes, auth, and which process owns the Schwab login are decided in [Three run modes](../../../docs/adr/0006-three-run-modes.md). In short: the CLI calls `https://127.0.0.1:8182/api/schwab/callback` and is the only Schwab browser login. The app calls `https://basecamp.ojos-alhena.ts.net/api/schwab/callback`. `pnpm dev` and `pnpm dev:auth` are `http://localhost:3000` on loopback. `pnpm dev` is email and password, with Schwab fixtures unless `SCHWAB_MODE=live`. `pnpm dev:auth` is passkeys only and fixtures only. `pnpm start` is the Tailscale instance, passkeys only, live Schwab, and a separate database. The app's Schwab client is a live-or-fixture interface. The fixture side never touches the Keychain. The app reads the CLI's Keychain item or asks the CLI.

The CLI is Python under `tools/schwab/`. Invoked via `pnpm schwab`, which runs the tool with **`uv`** (`uv run` from `tools/schwab/`). Dependencies and the virtualenv are managed by `uv`, not hand-rolled `pip`/`venv`. It owns the login and the Schwab OAuth Keychain item. The TanStack app does not share this code. Bitwarden: [Python SDK README](https://github.com/bitwarden/sdk-sm/blob/main/languages/python/README.md).

Commands:

- `login` listens at the registered loopback callback `https://127.0.0.1:8182/api/schwab/callback` with a mkcert certificate, opens the browser, and stores the access token and the refresh token in the macOS Keychain under `investor-basecamp` / `schwab`. There is no token file. The listener binds to `127.0.0.1` only, checks the OAuth `state` value, accepts one callback, and then shuts down. It never logs the authorization code or the tokens. The mkcert root CA private key stays in mkcert's CAROOT, outside this repository and outside any synced folder.
- `get <path>` performs one GET against `api.schwabapi.com`. The path includes the query string. This is the ad-hoc command, so an equity-only or option-only question never needs `--option`.
- `capture --option <occ> --equity <ticker>` is the fixed pull for this ticket. Both flags are required. It requests account numbers, accounts with positions, the option quote, the equity quote, one year of daily price history for the equity, and the option chain.

Every method other than GET is refused, and any path containing `orders` is refused.

**Secrets:** The Schwab app key and secret are not in `.env.local`. The CLI loads them with the Bitwarden Secrets Manager **Python SDK**, from the `investor-basecamp` project, using the secret names `SCHWAB_CLIENT_ID` and `SCHWAB_CLIENT_SECRET` (see [Register the Schwab developer app](04-register-the-schwab-developer-app.md)). The SDK authenticates with the read-only machine account. The CLI reads the access token from the macOS Keychain item **`bws-access-token`** and the organization id from **`bws-org-id`**, and passes both to the SDK in memory only. No `bws` subprocess and no env fallback for Schwab app credentials or Bitwarden (`bws-access-token`, `bws-org-id`). The CLI does not store or log those values. Schwab OAuth tokens (access and refresh) are a separate Keychain item (`investor-basecamp` / `schwab`), written only by `login` and refresh.

**Grilling 2026-10-23 (settled, implemented in CLI):** Auto-refresh expired Schwab access tokens on `get` and `capture`, writing the new pair to Keychain before the API call. A lock under `.local/schwab/` during refresh (and during `login` token exchange) so two terminals cannot rotate the same refresh token. Fail with a clear message if Keychain or Bitwarden fetch fails; never read Schwab app credentials from the environment.

A **Capture** is one saved response, written under `.local/schwab/captures/`, which is gitignored. The command prints the HTTP status and the path. The body stays in the file. A failed request is saved too. Before writing, a digit account number is replaced with a shape marker such as `REDACTED:8-digits`. Hashes, positions, and balances are kept. The first Capture is checked for an account number that landed in some other field.

An **Observation** is a fact read off one or more Captures. Observations are checked in at `docs/schwab/observations.md`: field paths, types, units, symbol roots, and the Capture filename and date. Quantities, prices, cash, and account hashes are placeholders. The CLI does not write that file. Capture, Observation, and account hash stay out of `GLOSSARY.md`. A Capture is not a Snapshot.

**2026-10-23, implemented:** Python CLI at `tools/schwab/` (`pnpm schwab`). Commands `login`, `get`, `capture`. Bitwarden via `bitwarden-sdk` and Keychain `bws-access-token` / `bws-org-id`. Schwab tokens in Keychain `investor-basecamp` / `schwab`. Captures under `.local/schwab/captures/`.

**2026-10-23, capture run:** Live `capture` for `IREN` / `IREN  261023P00022000` (20261023T140603Z–140605Z). Observations in [docs/schwab/observations.md](../../../docs/schwab/observations.md). **Human follow-up:** TOS IV/greek spot-check; second capture on a dividend-paying `--equity`; confirm cash/IRA balance fields if those account types exist; index option symbol if you hold SPX/XSP.
