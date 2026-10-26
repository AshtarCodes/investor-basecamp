# Re-run the ANALYTICAL chain probe during a market-hours weekday

Type: task
Status: resolved
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
- Whether the rate behind the default `theoreticalOptionValue` is still about 0.04% on SPX and XSP (the call-minus-put regression in [schwab-implied-rate.md](../../../docs/research/schwab-implied-rate.md)), and whether `ANALYTICAL` still honours a passed `interestRate`. [Ticket 14](14-schwab-option-price-cli.md)'s cross-check depends on the second.

## Why it matters

- [Ticket 14](14-schwab-option-price-cli.md) plans a "Schwab cross-check: cents tolerance". A tolerance is only meaningful if Schwab's theoretical is internally consistent.
- The research note's claim that anchoring to the mark and solving our own IV is better than using Schwab's IV rests on item 9.

## Answer

Both gaps survive live quotes, so the argument in [ADR 0001](../../../docs/adr/0001-own-pricing-model.md) and the research note stands, and the "known correct input" question stays closed. Schwab's no-override theoretical is not a reference to hold ours to within cents. Use `ANALYTICAL` with explicit inputs for the cross-check.

**Run:** Monday 2026-10-26, 09:48 to 09:51 ET, from branch `prototype/schwab-analytical-chain` (7e4964f) in a separate worktree, probe unchanged for SPY. SPX and XSP ran with a scaled copy of the probe (strikes 3000/7630/9000/10000 and 300/763/900/1000) and the symbol URL-encoded as `%24SPX` and `%24XSP`; the plain symbol returned 400. **This was inside the first 15 minutes after the open**, which the ticket asked to avoid; the user chose to run at 09:48. The quotes look healthy anyway: `isDelayed` false, SPY call spreads 4 to 19 cents (K 754 to 773), every quote stamped within the same second. A rerun after 10:00 would remove the doubt and is cheap.

| | First run (Sat 2026-10-24) | SPY | SPX | XSP |
|---|---|---|---|---|
| Contracts in the T3 sample | 42 | 42 | 84 | 66 |
| Schwab IV minus IV(mark), q=0, median / min / max (vol points) | about -1.6 to -1.9 median | -1.61 / -2.96 / +2.67 | -1.67 / -2.52 / +1.88 | -1.51 / -2.69 / +2.25 |
| Same at q=1.2% | | -2.06 / -2.63 / +2.20 | -1.64 / -2.92 / +1.48 | -1.61 / -3.10 / +2.66 |
| Default `theoreticalOptionValue` within 2c of the mark | | 0 of 42 | 5 of 84 | 18 of 66 |

- **Item 8 persists.** SPY 25-day K=763 call: theo 11.311, Black-Scholes at Schwab's displayed IV (13.916), rate (4.043%), DTE and spot 12.189, mark 13.35. Theo is 0.88 below the model at q=0, and 0.60 below at q=1%. The first run's gap was 0.95. The gap is not noise.
- **Item 9 persists.** Schwab's IV is consistently below the IV of its own mark by 1.5 to 2 vol points, and it jumps between adjacent strikes: on the SPY 2026-11-20 calls it is 13.594 at K=765 and 16.065 at K=766 (+2.47) while the marks are smooth (12.18, 11.58).
- **Request shape, unchanged.** Overrides are honoured for one expiration per call only: with two expiries the root `volatility` is the chain's own (13.9, 13.7, 13.6 for SPY, SPX, XSP) and the contracts keep their own IVs. The whole chain comes back even with `strike=` set (237 SPY calls). With one expiry, `volatility=20` gives every contract IV 20.0. Without dates, the root volatility is 29.0.
- **Rate behind the default theo.** The call-minus-put regression of the research note on SPX and XSP gives about 0.04% again: SPX 0.037% to 0.050% across 17 expiries (25 to 144 days), XSP 0.030% to 0.054% for most of 14 expiries. A few thin expiries scatter (SPX 2026-12-02 0.157% on 39 strikes; XSP 2026-11-27 0.009% and 2026-11-23 0.095% on 22 strikes). Flat across tenors, not the displayed 4.043%.
- **`ANALYTICAL` still honours a passed `interestRate`.** Passing 3 fits 3.035% (SPX) and 3.034% (XSP); passing 4.043 fits 4.090% and 4.093%, so the fitted rate runs about 0.04 to 0.05 points above the passed one, which is about the size of the 0.047% default. [Ticket 14](14-schwab-option-price-cli.md)'s cross-check can pass our rate.
- **SPX and XSP theoreticals are European.** At flat vol 20, deep ITM puts sit below intrinsic and on the European floor: SPX K=9000 theo 1317.759 against intrinsic 1342.780 and floor 1317.892; XSP K=900 theo 131.768 against 134.270 and 131.781. SPY (K=900, 1000) sits on intrinsic, so American. T4 agrees: SPX K=8040 and XSP K=804 have the mark below intrinsic (380.1 against 382.2, 38.15 against 38.32), and SPY K=801 has the mark above (39.5 against 37.79).
- **Continuous yield from a deep ITM call at flat vol.** SPY 0.992% at 365, 1.000% at 360, 1.176% at 252: stable across the day basis choice, unchanged from the first run (0.98%). SPX and XSP imply about 0% at 365 and 360 (-0.018%, 0.003%), as the regression's intercept found.
- **SINGLE against ANALYTICAL without overrides** still differs on every contract (root volatility 29.0 against 13.9, 13.7, 13.6), so the two are not the same call.

Probe output is not committed: the verdict file on the prototype branch is unchanged, and the numbers above are the record.

## Comments
