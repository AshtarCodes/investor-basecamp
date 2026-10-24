# Verdict: Schwab `/chains` ANALYTICAL strategy

Prototype: [`prototype_analytical_chain.py`](../prototype_analytical_chain.py). Run from the repo root:

```bash
uv run --project tools/schwab python tools/schwab/prototype_analytical_chain.py SPY
```

Run once on **2026-10-24 (Saturday, market closed)** against SPY, expiries 2026-11-20 to 2027-01-22. Quotes were last-session values, so fields may carry different timestamps. Re-run during market hours before relying on any number below that compares Schwab's fields with each other.

## Questions and answers

| # | Question | Answer | Evidence |
| --- | --- | --- | --- |
| 1 | Do the `volatility`, `underlyingPrice`, `interestRate`, `daysToExpiration` overrides work? | **Yes, but only when the request covers exactly one expiration** (`fromDate` equals `toDate`). With two expirations, or with no dates, they are silently ignored: HTTP 200, root values unchanged. | T1: root `volatility` echoes 20.0 for one expiry; stays 14.206 (two expiries) and 29.0 (no dates). |
| 2 | Does an override respect `strike` / `strikeCount`? | **No.** With any override the whole chain for that expiry comes back (237 call strikes, 474 with puts). Filter on our side. | T1: `strike=762` plus `volatility=20` returned 237 contracts. |
| 3 | Is the volatility override a shift or a level? | **A flat level.** Every contract's `volatility` becomes the override, so the smile is gone. With any other override (spot, rate, days) every contract's `volatility` is also replaced by one flat number: the chain root `volatility` (14.206 here, which equals the IV of the first, near-the-money call). | T1: distinct contract IVs `[20.0]`; with `r=3`, `K=762` shows `iv=14.206`, not its own 14.066. |
| 4 | Does the spot override re-solve IV? | Not usefully. With `underlyingPrice=700` the deep ITM K=300 call keeps the IV it had from its mark (98.7) and the theoretical drops to 400.4. Per-contract IV is not recomputed for a hypothetical spot. | T1. |
| 5 | American or European? | **American-style for SPY.** At a flat 20 vol, deep ITM puts have `theoreticalOptionValue` equal to intrinsic to the cent (K=900: 138.89 = 900 - 761.11; K=1000: 238.89), while a European put would be about 2.7-3.0 lower. | T1b. |
| 6 | What dividend does it assume? | A continuous yield near **0.98%** (0.99% on a 360 basis) from a deep ITM call, assuming `theo = S e^(-qT) - K e^(-rT)`. The day basis cannot be separated with one point. | T1c. |
| 7 | Can we reproduce override-mode values with textbook Black-Scholes + q = 0.98%? | **Partly.** Two of four cases match to a few cents (days=10: -0.004; S=700: +0.003). The other two (vol=20, r=3) are 0.15-0.22 higher at the money, which an American model or a slightly different q would explain. We did not separate those. | Manual check, illustrative inputs from the script's T1 output. |
| 8 | Does the **no-override** `theoreticalOptionValue` follow from the displayed IV, rate, DTE and spot? | **No.** For the 2026-11-20 K=762 call: theo 11.068; Black-Scholes at the displayed IV 14.066%, r 4.032%, 27 days, q 0.98% gives 12.020 (**-0.95**). Mark is 13.34. | Manual check; T3. |
| 9 | Does Schwab's own `volatility` reproduce its own mark? | **No, by about 1.6-1.9 vol points.** Schwab IV minus the IV that textbook Black-Scholes needs for the mark: median -1.57 (q=0) / -1.89 (q=1.2%) over 42 contracts, range -3.35 to +2.78. Adjacent call strikes jump (K=762: 14.07, K=763: 16.61). `theoreticalOptionValue` is within 2 cents of the mark on 21 of 42 contracts and off by dollars on others. | T3. Possibly a stale-quote artefact: see the note above. |

## What this means

- ANALYTICAL is a usable but narrow what-if tool: one expiry per call, one flat IV, one spot, one rate, one day count, no dividend input, no strike filter, and a silent no-op when the request shape is wrong. It cannot apply "each contract's IV plus 5 points". Cross-checking our shocked values against it is feasible for single-expiry, flat-vol cells only.
- Schwab's theoretical engine looks like American-style Black-Scholes family with a continuous yield near 1% for SPY, consistent with the thinkorswim description. We could not confirm the variant.
- Schwab's numbers are **not one consistent set**. In this snapshot its IV, its theoretical value and its mark do not reproduce each other under any single textbook model I tried (items 8 and 9). That bears on the ADR: anchoring to the **mark** and solving our own IV so the base equals the mark is more defensible than treating Schwab's IV as a "known correct" input. Confirm with a market-hours re-run first.
- Rough size, derived not measured: for the near-the-money 27-day SPY call, vega is about $0.83 per vol point per share, so a 1.6-point IV gap is about $1.3 per share, or about $130 per contract, at the base value.

## Not tested

- Market hours (everything here is a Saturday snapshot).
- Index options (SPX/XSP, European), hard-to-borrow equities, and any contract with a known near-term ex-dividend date.
- Whether `daysToExpiration` overrides change the day basis, and how Schwab handles non-integer days.
- The dividend/early-exercise reason for the 0.15-0.22 gaps in item 7.
- Rate limits for repeated ANALYTICAL calls.

## Capture

This script and verdict live on the throwaway branch `prototype/schwab-analytical-chain`, kept as a primary source and not merged into main. The decision to keep on main: the ADR anchors Scenarios to the mark with our own solved IV (see `docs/adr/0001-own-pricing-model.md`).
