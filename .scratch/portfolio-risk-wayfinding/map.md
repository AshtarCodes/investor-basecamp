# Portfolio risk app v1

Label: wayfinder:map

## Destination

A v1 spec at `.scratch/portfolio-risk/spec.md` plus numbered implementation issues in `.scratch/portfolio-risk/issues/`, ready for agents, with every decision a builder would otherwise have to guess already made.

## Notes

- Domain: a personal options-and-equities risk tool for Schwab accounts. Use the vocabulary in `GLOSSARY.md`; flag any new term instead of drifting to a synonym. Read `docs/adr/` before deciding anything that touches pricing, holdings sources, hosting, Schwab access, or agent control of a Portfolio.
- Crossing the Portfolio Loss Threshold opens a Simulated Portfolio and the Compare view in v1. The guided loop that adjusts that book is v2. Each control is one function, exposed as a WebMCP tool and through one MCP endpoint at the Tailscale address. Tools return rich data, such as the Shock list, and the agent draws conclusions. Tool names are not chosen yet ([ADR 0005](../../docs/adr/0005-scenario-controls-are-webmcp-tools.md)).
- Grilling tickets: call the "grilling" and "domain-modeling" skills. Prototype tickets: the "prototype" skill. Research tickets: the "research" skill, findings on a throwaway `research/<name>` branch (this repo has no remote yet, so branches stay local).
- Stack and checks are in the root `AGENTS.md`. The app isn't scaffolded yet; prototypes may need the scaffold in `docs/agents/setup.md` first.
- This map plans; it doesn't build. The destination spec lives in its own directory so decision tickets and implementation issues never share a frontier.
- The Schwab developer app is ready. "Pull real Schwab payloads for your accounts" is the next Schwab task; the loopback callback is enough for that script.

## Decisions so far

- [Core domain model and v1 scope](issues/01-core-domain-model-and-v1-scope.md): Accounts sync from Schwab, screenshots only create Simulated Portfolios, Scenarios belong to a Portfolio, Loss Thresholds are optional risk budgets per Portfolio and per Underlying.
- [Can the Schwab Trader API supply our positions and market data?](issues/02-can-schwab-supply-positions-and-market-data.md): yes, free, with 1 to 3 day approval, an HTTPS callback fixed at registration, and a mandatory weekly re-login.
- [Which pricing models and inputs should the engine use?](issues/06-pricing-inputs-and-models.md): Leisen-Reimer with discrete dividends for American options, Black-Scholes-Merton for European index options. The engine runs server-side as a Python worker ([ADR 0007](../../docs/adr/0007-pricing-engine-is-a-python-worker.md)), which prefers a cash-drop finite-difference solver over the tree. Treasury.gov curve for the rate, calendar minutes to the settlement instant. Schwab's values differ by design, so the cross-check uses a tolerance.
- [Where does the app run, and how do you reach it?](issues/03-where-does-the-app-run.md): your laptop, reached over Tailscale at `basecamp.<tailnet>.ts.net`, an address that can move to a VPS. How the laptop serves that address was reopened as its own ticket. Secrets in Bitwarden Secrets Manager, no order-placing code, passkeys plus password and TOTP, daily local backups with push-to-R2 and restore commands.
- [How should Shocks behave?](issues/07-how-should-shocks-behave.md): each contract starts from its live mark. IV Shifts are absolute points by default (proportional as a setting), independent of the SPY move. Beta is a 1-year daily regression against SPY, overridable per Scenario. Days forward is one calendar-day value per Scenario. Shock P/L is measured from current market value. Settings cascade from global to Portfolio to Underlying. Default grid is 66 Shocks with a "Market shock" starter Scenario. The default IV range is open to revision by historical-data research.
- [Scaffold the app so prototypes run on the real stack](issues/13-scaffold-the-app.md): TanStack Start app is on `master` at `a9958f3`, TypeScript 7.0.2, Better Auth on SQLite, Oxlint/Vitest/Knip/Playwright wired. shadcn `cn` comes from the `cn` package.
- [What should the Portfolio view look like?](issues/08-portfolio-view-prototype.md): Inspector. Holdings on the left with Cash, Margin Cushion, and the Legend; the worst Shock in the header against the account's percent-of-NLV Loss Threshold; the selected Underlying in the middle, with a Shock toggle beside Greeks that puts that Shock's P/L on every Position. Choosing among Shocks is the Scenario view.
- [Register the Schwab developer app](issues/04-register-the-schwab-developer-app.md): ready on 2026-10-22. Tailnet `ojos-alhena.ts.net`. Callbacks are the basecamp address and `https://127.0.0.1:8182/api/schwab/callback`. Secrets are `SCHWAB_CLIENT_ID` and `SCHWAB_CLIENT_SECRET` in the investor-basecamp Bitwarden project.
- [Pricing engine package](issues/16-pricing-engine-package.md): landed in `4c024dc` as `packages/pricing-engine/` (ty as the type checker). 85 tests pass and the 50 by 100 grid takes 0.12 s in a process pool. Rate and dividend inputs are [17](issues/17-engine-rate-and-dividend-inputs.md) and the worker is [18](issues/18-engine-worker.md).
- [Engine rate and dividend inputs](issues/17-engine-rate-and-dividend-inputs.md): `treasury.py` (Treasury.gov par curve as a continuous rate, Schwab-chain fallback flagged) and `dividends.py` (quarterly projection, `needs-continuous-yield` for SATA). Stale ex-dates roll forward, and Treasury.gov needs a custom User-Agent. The worker is [18](issues/18-engine-worker.md).
- [Engine worker](issues/18-engine-worker.md): `pricing-worker` in `packages/pricing-engine/`, JSON lines over stdin and stdout, one request at a time. A `batch` request owns the Shock semantics (Mark-implied IV solved once per contract, IV Shift sticky-strike with a 1 vol point floor, days forward in calendar days, residual carried when there is no IV) and returns per-share prices. A pool of 4 warm processes (`PRICING_WORKERS` or `--workers` to change it) prices a 50 by 100 grid in 0.21 s; a dead pool is rebuilt and the caller retries once. `uv run` forwards SIGTERM. The server code that spawns it is not written yet.

## Not yet specified

- **Sync mapping:** exactly how Schwab positions and balances become Snapshots and Positions (signs, multipliers, index option roots, unsupported asset types). Waits on the real payloads.
- **Market data budget:** refresh cadence for quotes, chains, and price history, cache lifetimes, and staying under about 120 requests per minute with many Underlyings. Waits on the real payloads.
- **Settings inventory:** which settings exist beyond beta lookback, IV shift mode, and the P/L baseline (for example the 15-minute sync age), and which scopes each allows. Comes into view as the prototypes surface what you want to change.
- **Slicing v1:** the build order and issue boundaries for the spec (pure engines first, then persistence, Schwab, screenshots, views). Comes into view once the prototypes and Shock semantics settle.

## Out of scope

- The v2 agentic flow that proposes hold, add, and trim rules from historical data, tuned by a prompt. A separate effort once v1 ships.
- Strategy detection, Monte Carlo and VaR, correlated shocks and volatility skew, a combined view across Accounts, and futures, futures options, and mutual funds. Roadmap items beyond v1.
