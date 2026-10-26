# Daily Mark-implied IV snapshot service

Type: task
Status: needs-triage

Blocked by: none. Builds on [14](14-schwab-option-price-cli.md) (the Schwab inputs and the engine call, merged), and feeds [`scenarios/iren/iv-rules.md`](../../../scenarios/iren/iv-rules.md). Overlaps the research question in [12](12-can-historical-data-calibrate-shocks.md): Schwab has no historical option IV, so this builds our own history from today forward.

## Goal

A small, lightweight script that starts with the laptop, takes a daily snapshot of the Mark-implied IV for a configured set of tickers, and records it in a local Postgres database. If it cannot reach Schwab, it pings the user's phone over Tailscale at 7:00 am ET.

## Why

Schwab's API returns no historical option IV, so how a stock's IV moves with its price, with the VIX and through time cannot be measured after the fact. [`scenarios/iren/iv-rules.md`](../../../scenarios/iren/iv-rules.md) Rule 2 (IV moves against the stock, +15 points at -40%, -15 at +100%) is an assumption for exactly that reason. A daily record of Mark-implied IV beside spot is the data that confirms, resizes or drops it. History cannot be backfilled, so every day not recorded is lost.

## Scope

- **A snapshot command.** `pnpm schwab iv snapshot`, a new subcommand of the existing CLI in `tools/schwab/`, reusing its token handling (Keychain), the Schwab GETs in `schwab_inputs.py` and the engine's Mark-implied IV. It reads the ticker list from a committed config file (TOML; no secrets in it). Start with IREN; the config takes more (ticket 12 names CIFR and ASST; `$SPX` is the obvious index).
- **What it records**, per ticker and day, for a fixed set of contracts:
  - the contract (OCC symbol, expiry, strike, right), spot, bid, ask, Mark and the quote time;
  - our Mark-implied IV, or its `reason` when there is none (`at_or_below_intrinsic`, `no_bracket`), with the model, the rate and its source, and the engine flags;
  - Schwab's own `volatility`, as a separate column, so the gap between the two (2 to 8 vol points on IREN's LEAPS on 2026-10-26) is itself recorded;
  - the underlying's close and the VIX level for the day, so IV can be read against spot and the VIX.
- **A launch agent.** A macOS LaunchAgent (not a LaunchDaemon: the Schwab tokens are in the user's login Keychain) that runs at login and on a daily calendar schedule. A laptop that was asleep or off at the scheduled time must run the missed snapshot when it next wakes, and must not run twice for the same day.
- **A failure ping.** At 7:00 am ET a health check confirms Schwab is reachable and the token works (one cheap GET). If not, it notifies the phone over the tailnet. See "Open decisions" for how.
- **A runnable spec** in `tools/schwab/README.md`: how to run a snapshot by hand, where the config is, how to install and remove the LaunchAgent.

## Design notes

- **Few calls.** `option price` makes about five GETs per contract. A snapshot should instead make one `/chains` call per ticker per expiry (it already returns Mark, bid, ask, quote time and the underlying price for every strike) and solve the IV in-process, so a snapshot of dozens of contracts stays at a handful of calls. All calls are read-only GETs (ADR 0004).
- **The rate.** Use the engine's `TreasuryCurves` with its disk cache under `.local/schwab/`, as the CLI does. One rate lookup per expiry; the fetch is cached for a day.
- **Idempotent.** One row per (snapshot date, OCC symbol). A rerun the same day updates nothing it already has and fills what is missing.
- **A failed ticker does not fail the run.** Record the error against that ticker and carry on; the run's status says how many succeeded.
- **Postgres is down, or the token is dead.** Keep the snapshot and replay it rather than lose the day. A spool file under `.local/` that the next run drains is enough. This matters because Postgres.app on this laptop runs only while the app is open, and the Schwab refresh token expires every 7 days (below).
- **Market days only.** Skip weekends and exchange holidays (Schwab's market hours endpoint can say); a Mark after the close is the last quote, so take it after 4:00 pm ET and record the quote time with it.
- **The schema** is the implementer's to propose, in a migration file. A starting shape: `snapshot_runs` (run id, started, finished, status, error), `iv_snapshots` (the per-contract columns above, unique on date and OCC symbol) and `underlying_snapshots` (ticker, date, close, quote time; the VIX is a ticker).
- **Postgres here, SQLite in the app.** The app's database is SQLite (Drizzle). This service uses a separate local Postgres on purpose, as research data the app does not read yet. If the app later wants it, that is a decision for its own ticket.

## Two facts to plan around

- **The Schwab refresh token lasts 7 days from login, not 12 hours.** ([Trader API documentation](../../../docs/schwab/api-specs/trader-api-documentation.md): "A Trader API refresh token is valid for 7 days after creation.") The access token lasts 30 minutes and the CLI refreshes it on its own, but the refresh token is not extended by use. An unattended daily job therefore needs `pnpm schwab login` about once a week, and an expired token is the most likely reason it cannot reach Schwab. The 7:00 am ping is what tells the user to log in. Make the message say that ("Schwab login expired, run `pnpm schwab login`") and tell it apart from "no network" and "Schwab returned an error".
- **Tailscale is stopped on this laptop today** (`tailscale status` says so). A ping that depends on the tailnet must still leave a trace when the tailnet is down: log it, and raise a local macOS notification as the fallback.

## Open decisions

1. **How a "ping over Tailscale" reaches the phone.** Tailscale itself carries traffic; it has no push channel. Candidates for the implementer to spike:
   - **Taildrop**: `tailscale file cp` a small status file to the phone, whose Tailscale app shows an incoming-file notification. No extra service. Needs checking on the user's phone OS.
   - **A self-hosted notification server on the tailnet** (for example ntfy), published over Tailscale and subscribed to from the phone. More moving parts; confirm what the phone OS needs for a background notification.
   - **`tailscale ping`** alone shows only that the phone answers; it does not notify and is not enough.
   
   Pick the lightest one that produces a visible notification on the phone, and keep it behind a small function so it can be swapped. The user's phone OS is not recorded anywhere; ask before choosing.
2. **What 7:00 am means.** Read here as: a health check at 7:00 am ET on every day, and a ping if it fails (so a dead token is caught before the market opens). Alternative: the snapshot runs at about 4:05 pm ET, and a failure there is held and sent at 7:00 am the next morning. The first reads the request more naturally and catches a dead token early; confirm.
3. **Which contracts per ticker.** Proposal: per ticker, the nearest expiry at least 30 days out, and about 90 days, 180 days and 1 year out, plus the two furthest January LEAPS; at each, the at-the-money call and the strikes nearest 25% out of the money on each side. Alternative: only contracts the user holds, which needs the account positions read. Decide before the schema.
4. **Snapshot time.** About 4:05 pm ET (the close's final Marks) is the proposal. A second snapshot near the open would show overnight IV moves but doubles the calls.

## Acceptance

- `pnpm schwab iv snapshot` with a fixture-backed `get` and the engine's saved Treasury month records the expected rows and the underlying and VIX rows, with the Mark-implied IV reproducing each Mark (the engine is the real one; only `get` and `TreasuryCurves(fetch=…)` are faked, as in [14](14-schwab-option-price-cli.md)).
- A rerun on the same date adds no duplicate rows. A missed day is run on the next wake, once.
- With Postgres unreachable, the snapshot is spooled and the next run writes it. With the token expired, nothing is lost and the notifier is called with the "login expired" message; with the network down, with the "no network" message.
- The notifier is behind one function; the tests use a fake and never touch Tailscale or the network.
- The LaunchAgent plist is in the repo with install and remove steps in the README. It runs the real command on this laptop, shown once in the ticket's Answer: one snapshot written, one simulated failure pinging the phone.
- Database tests use a throwaway database, not the user's data. No test needs the network.

## Out of scope

- Reading the snapshots in the app, or charting them.
- Backfilling history (Schwab has none; ticket 12 covers paid sources).
- Order endpoints of any kind (ADR 0004).
- Moving the job to a VPS. It will need its own Schwab login and a rethink of the Keychain; separate ticket when the VPS exists.
