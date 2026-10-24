# Re-run the ANALYTICAL chain probe during a market-hours weekday

Type: task
Status: ready-for-agent
Blocked by: none

## Question

The first run of the Schwab `/chains` ANALYTICAL probe was a **Saturday snapshot (2026-10-24, market closed)**, so quotes were last-session values and Schwab's fields may have carried different timestamps. Two findings depend on that and are not safe to rely on until re-run:

- **Item 8:** Schwab's no-override `theoreticalOptionValue` could not be reproduced from its own displayed IV, rate, days-to-expiry and spot (about $0.95 low on a 27-day near-the-money SPY call: theo 11.068, Black-Scholes at the displayed inputs 12.020, mark 13.34).
- **Item 9:** Schwab's per-contract `volatility` did not reproduce Schwab's own mark: median -1.6 to -1.9 vol points over 42 contracts, with jumps between adjacent strikes (14.07 to 16.61).

Does either gap survive when quotes are live and fields are stamped together? If they vanish, the "Schwab's numbers are not one consistent set" argument in [ADR 0001](../../../docs/adr/0001-own-pricing-model.md) and the research note loses its strongest evidence, and the "known correct input" question reopens.

The probe and its first verdict are on the branch `prototype/schwab-analytical-chain` (commit 7e4964f): `tools/schwab/prototype_analytical_chain.py` and `tools/schwab/prototype/ANALYTICAL_CHAIN_VERDICT.md`. Findings already stable regardless of timing (request shape, flat vol, whole chain returned, American-style theoretical) should be re-confirmed by the same run, not assumed.

## How to run

- **When:** a US market weekday between about 10:00 and 15:30 ET. Avoid the first 15 minutes (stale or wide quotes) and the last 15 minutes. Record the run time in the answer.
- **Where:** check out the branch (`git switch prototype/schwab-analytical-chain`), run from the repo root: `uv run --project tools/schwab python tools/schwab/prototype_analytical_chain.py SPY`. It is read-only market data through the existing CLI client and needs a valid Keychain token (`pnpm schwab get /marketdata/v1/quotes?symbols=SPY` is a quick check; do not run `login` unless the user is present).
- **Dates:** the script hard-codes `FROM = "2026-11-20"` and `TO = "2027-01-22"`, and T4 uses the 2026-12-18 expiry. After 2026-11-20, update those constants to a current monthly expiry before running.
- **Also run it on an index.** Pass `SPX` and `XSP` (URL-encode a leading `$` as `%24` if the plain symbol is rejected). Index options are European, so T1b should show deep ITM puts **below** intrinsic. T4 picks a strike with `round(S * 1.05)` and may need a strike that exists on the index.

## What the answer must record

- Run time (ET), symbol, and whether quotes were live (`isDelayed` false, bid/ask spreads normal).
- Whether item 8 and item 9 persist, with the same statistics as the first run (median, min, max gap in vol points over all contracts; `theoreticalOptionValue` within 2 cents of the mark: count of total).
- Whether the no-override theoretical is reproducible from displayed IV, rate, DTE and spot, and the size of any remaining gap.
- Whether SPX/XSP theoretical values are European (below intrinsic on deep ITM puts at a flat vol) or American.
- Whether the continuous yield implied by a deep ITM call is stable across expiries (0.98% at 365 basis in the first run), to separate day basis from yield.
- Any change to the request-shape findings (overrides honoured only for one expiration; whole chain returned).

## Why it matters

- [Ticket 14](14-schwab-option-price-cli.md) plans a "Schwab cross-check: cents tolerance". A tolerance is only meaningful if Schwab's theoretical is internally consistent.
- The research note's claim that anchoring to the mark and solving our own IV is better than using Schwab's IV rests on item 9.

## Comments
