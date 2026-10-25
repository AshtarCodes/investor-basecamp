# What rate does Schwab's theoretical value use?

Gathered 2026-10-24 (a Saturday, market closed, so quotes are the last session's) with `pnpm schwab get` on `/marketdata/v1/chains`. It follows up the open question in [the ADR 0001 fact-check](pricing-model-adr-0001-fact-check.md) ("Schwab's actual rate source and tenor") and the rate gap in [pricing-engine-vs-schwab-iren.md](pricing-engine-vs-schwab-iren.md).

Labels: **[Read]** is a value taken from a Schwab payload. **[Own]** is our computation. Nothing here was checked against a thinkorswim screen.

## Bottom line

- **The chain's `interestRate` (4.032) is not what Schwab's default `theoreticalOptionValue` uses.** On SPX, SPXW and XSP the default theoretical values imply a discount rate of about **0.040%**, not 4%. [Own]
- **It is flat across expiries**, 27 to 249 days (0.039% to 0.041%). So it is not a Treasury tenor of any length: the par curve runs from 4.07% (1 month) to 4.94% (10 years) on the same day, in continuous terms.
- **Asked explicitly, Schwab does use a real rate.** With `strategy=ANALYTICAL`, the theoretical values imply the rate you pass in (4.032 gives 4.030, 10 gives 9.995, 100 gives 99.945), and with no override they imply the chain rate. The unit is percent. [Own]
- So there are two rates inside Schwab: the displayed 4.032, which `ANALYTICAL` honours, and a near-zero one behind the default values. I did not find where the near-zero one comes from.
- For the engine: a cents-level cross-check against Schwab's default theoretical value cannot use the Treasury rate. Use `ANALYTICAL` with explicit inputs, which honour ours. Our Treasury curve is still the right rate for our own prices.

## Method [Own]

Schwab's call and put theoretical values at the same strike and expiry obey put-call parity to 0.001 on every index expiry, so they are European Black-Scholes values with one rate and one yield:

`C − P = S·e^(−qT) − K·e^(−rT)`

Regressing `C − P` on `K` across the strikes within 8% of spot gives a slope of `−e^(−rT)`. That fixes `r` without knowing the IV or the exact time to expiry, and the intercept gives `q`. T is `daysToExpiration / 365`. Solving for `r` and `q` from one strike does not work: only `r − q` is pinned down there.

## Results

Default (`SINGLE`) chain, no overrides, `isDelayed` false [Read], rate fitted by the regression above [Own]:

| Underlying | Expiries | Fitted rate | Fitted yield |
| --- | --- | --- | --- |
| SPX and SPXW (European, cash-settled) | 27 to 249 days | 0.039% to 0.041% | about 0 |
| XSP | 118 to 236 days | 0.039% to 0.041% | about 0 |

Short expiries (under 25 days) are too noisy to fit and are left out. The chain root reports `dividendYield` 0.0, which matches the fitted yield.

Checking the other way, with the contract IV from the payload [Own]:

| Expiry | Median gap, r = 4.032%, q = 0 | Median gap, r = 0.04032%, q = 0 |
| --- | --- | --- |
| 2026-12-18 | $23.27 | $0.68 |
| 2027-03-19 | $62.27 | $0.87 |
| 2027-06-17 | $99.59 | $0.82 |

Gaps are `|BSM − theoreticalOptionValue|` over calls and puts within 5% of spot, on an index near 7,624. The tiny rate removes nearly all of the gap but not all of it, and I did not explain the remaining $0.7 to $0.9.

IREN calls (no dividends, so American and European agree), median `BSM − theoretical` at the contract IV [Own]:

| Expiry | r = 4.032% | r = 0.04% |
| --- | --- | --- |
| 2026-12-18 | +0.035 | −0.019 |
| 2027-01-15 | +0.039 | −0.051 |
| 2027-02-19 | +0.066 | −0.048 |
| 2027-03-19 | +0.174 | +0.036 |
| 2027-04-16 | +0.013 | −0.150 |
| 2027-05-21 | +0.106 | −0.084 |

Neither rate fits, and the signs differ between expiries, so the equity case is **not** settled by this probe. The earlier note's "effective rate of 1.29% and 0.80%" sits between the two, which fits a low rate plus the unexplained time offset found there. Equity puts and dividend payers (SPY) were not tested, because their theoretical values are American and parity does not apply.

## What this does not tell us

- Why the default values use about 0.04%. It could be a hard-coded or stale input, or a different rate series. Nothing in the payloads says.
- Whether the equity default values use the same rate as the index ones. IREN is inconclusive.
- Whether any of it changes during market hours. [Ticket 15](../../.scratch/portfolio-risk-wayfinding/issues/15-rerun-analytical-probe-in-market-hours.md) is the natural place to repeat it, and a weekday run should rerun the regression on SPX and XSP.

## Consequences for the engine

- The Treasury curve in [ticket 17](../../.scratch/portfolio-risk-wayfinding/issues/17-engine-rate-and-dividend-inputs.md) stays the rate for our prices. Its fallback to the chain's `interestRate` is a displayed number that Schwab's own default values do not use.
- [Ticket 14](../../.scratch/portfolio-risk-wayfinding/issues/14-schwab-option-price-cli.md)'s "Schwab cross-check: cents tolerance" should compare against an `ANALYTICAL` chain with our rate and IV passed in, not against the default `theoreticalOptionValue`. Otherwise a 4% rate on a 249-day SPX option shows a $100 gap that is Schwab's input, not our model.
