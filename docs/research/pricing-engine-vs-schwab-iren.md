# Pricing engine against Schwab's values: IREN long-dated calls

Gathered 2026-10-24 with the engine from [ticket 16](../../.scratch/portfolio-risk-wayfinding/issues/16-pricing-engine-package.md) (`packages/pricing-engine`). It checks the expected gap that [ADR 0001](../adr/0001-own-pricing-model.md) predicts against two real Schwab quotes, and measures how much that gap matters to Shock P/L.

Labels: **[Read]** is a value taken from a Schwab quote. **[Own]** is our computation. Neither is a published reference: the Schwab values were not checked against a live thinkorswim screen.

## Bottom line

- For a long-dated call on a non-dividend payer, the engine's Greeks agree with Schwab's to within about 1%. Schwab's IV runs 0.7 to 0.8 vol point above ours for the same Mark, and I could not find the cause.
- That gap barely moves Shock P/L, because every base value is solved from the Mark through our own model. In the cases below it changed the largest Shock P/L by 0.2% to 2%.
- The relative error is largest for **short-dated, low-priced** options. A fixed gap of about a day is a large share of a 3 to 7 day life, and a few cents is a large share of a small Mark. Treat per-contract IV and per-contract Shock P/L on those options as noisier than on long-dated ones.

## 1. The comparison [Read] [Own]

Quotes pulled with `pnpm schwab get "/marketdata/v1/quotes?symbols=…"` for IREN `270115C00040000` and `270115C00055000` (American exercise, physical settlement, no dividends: `divYield` 0). The market was closed, so the option `quoteTime` is 2026-10-23 20:00 UTC (4:00 pm ET Friday) and Schwab's `underlyingPrice` is 24.8911 (the stock's own mark was 24.905; the engine used `underlyingPrice`). The rate was 4.04%, the chain-root `interestRate` from earlier captures (4.03 to 4.04) rather than a Treasury curve, which is [ticket 17](../../.scratch/portfolio-risk-wayfinding/issues/17-engine-rate-and-dividend-inputs.md). The engine priced both with the closed form (`american_closed_form`) with 84.04 days of life.

"Ours" is the engine solving the Mark-implied IV from Schwab's Mark and taking Greeks at that IV.

| | $40 ours | $40 Schwab | $55 ours | $55 Schwab |
| --- | --- | --- | --- | --- |
| Mark | 1.295 | 1.295 | 0.42 | 0.42 |
| IV | 99.67% | 100.44% | 102.58% | 103.29% |
| Delta | 0.2317 | 0.2312 | 0.0892 | 0.0891 |
| Gamma | 0.02561 | 0.02551 | 0.01317 | 0.01311 |
| Vega | 0.03641 | 0.03633 | 0.01927 | 0.01920 |
| Theta | −0.02209 | −0.02212 | −0.01196 | −0.01192 |
| Rho | 0.01030 | 0.01020 | 0.00414 | 0.00411 |

- Units match with no conversion: vega per vol point, theta per calendar day, rho per percentage point of rate.
- Schwab's `theoreticalOptionValue` equals its Mark (1.29502 and 0.42026), so Schwab also solves its IV to reproduce the Mark.
- At Schwab's IV, our model prices 2.8 cents too high on the $40 call (1.3234 against 1.2950) and 1.4 cents too high on the $55 call (0.4338 against 0.4203).

### The gap is unexplained

Holding Schwab's IV and the rate fixed, our model reproduces Schwab's theoretical value if the valuation moves 1.27 days later on the $40 call and 1.11 days later on the $55 call (about 82.8 to 82.9 days of life instead of 84.04). Alternatively an effective rate of 1.29% and 0.80% would do it.

Neither is a clean fit. The two strikes need different offsets, and a rate of 1% contradicts both the chain's 4% and Schwab's rho matching ours at 4%. The model Schwab names (Bjerksund-Stensland) reduces to Black-Scholes for a call with no dividends, so the model choice should not explain it. Candidates not yet tested: a trading-day or integer-DTE time convention, a different day count, or a borrow cost. This is one snapshot taken with the market closed.

## 2. How much the gap matters to Shock P/L [Own]

Shock P/L is model(shock) minus model(base), with the base IV solved so that model(base) equals the Mark ([ADR 0001](../adr/0001-own-pricing-model.md)). A constant offset therefore cancels at the base and only a second-order effect remains.

**Method.** Model Schwab as our engine with 1.2 fewer days of life, its IV recalibrated to the same Mark. Reprice both under spot moves of ±15% and ±30%, IV shifts of −20, 0 and +20 vol points, and 0 days or half the remaining life forward. Report the largest difference in Shock P/L per share. (The 1.2 days is the offset fitted above, not a known cause.)

| Contract (rate 4.04%) | Mark | Largest Shock P/L difference | Largest Shock P/L | Difference as % of Mark |
| --- | --- | --- | --- | --- |
| IREN $55 call, 84 days, 103% vol | 0.43 | 2.6¢ | 207¢ | 6.1% |
| IREN $55 call, 365 days, 103% vol | 4.70 | 2.2¢ | 605¢ | 0.5% |
| IREN $40 call, 84 days, 100% vol | 1.31 | 4.3¢ | 370¢ | 3.3% |
| IREN $22 put, 30 days, 80% vol | 0.97 | 4.2¢ | 421¢ | 4.3% |
| IREN $22 put, 7 days, 80% vol | 0.17 | 9.5¢ | 445¢ | **55.8%** |
| IREN $25 call, 7 days, 60% vol | 0.78 | 2.3¢ | 661¢ | 2.9% |
| IREN $25 call, 3 days, 60% vol | 0.49 | 1.0¢ | 687¢ | 2.0% |
| $100 put, 600 days, 20% vol | 7.69 | 1.9¢ | 2,523¢ | 0.2% |
| $100 call, 84 days, 30% vol | 6.19 | 5.8¢ | 2,648¢ | 0.9% |

Reading the table:

- Against the largest Shock P/L of each contract the difference is 0.2% to 2%, and it was under 10 cents per share in every case.
- Against the Mark it is much larger on small or short-dated contracts. The 7-day put is 56% of its Mark off, yet only about 2% of its worst Shock P/L. A gap that is invisible in a portfolio loss can be large in one contract's own price.

## What this does not cover

- Only calls and puts with **no dividends**. ADR 0001 expects larger gaps on dividend-paying options, up to tens of cents, and that is untested here.
- Only a time offset was modelled. A rate or borrow-cost cause could behave differently, though I expect a similar size.
- One snapshot of two contracts, with the market closed and an assumed rate. Repeat it during market hours, over more expiries and strikes, before treating any number here as stable. [Ticket 15](../../.scratch/portfolio-risk-wayfinding/issues/15-rerun-analytical-probe-in-market-hours.md) is the natural place for the market-hours rerun.
