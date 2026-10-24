# Which pricing models and inputs should the engine use?

Type: research
Status: resolved

## Question

Gather the facts the pricing engine's design waits on, from primary sources:

- **American options:** how accurate and fast Bjerksund-Stensland 2002 is compared with a binomial tree (CRR or Leisen-Reimer), for repricing roughly 50 Positions across a grid of about 100 Shocks in the browser.
- **What thinkorswim uses:** which model and inputs thinkorswim and the Schwab API use for their own theoretical values, IV, and greeks, so we know how close our cross-check should be expected to land.
- **Dividends:** whether a continuous dividend yield is good enough for American equity options near ex-dividend dates, or whether discrete dividends are needed. Also which dividend fields the Schwab quote exposes (yield, amount, next ex-date).
- **Risk-free rate:** a free, official source for a daily short-term Treasury rate (for example FRED or Treasury.gov), and which tenor is conventional for option pricing.
- **Time to expiry:** calendar-day versus trading-day conventions, and what time of day expiry is counted at for equity options versus AM-settled index options (SPX).
- **Test oracles:** published reference values (for example Haug, "The Complete Guide to Option Pricing Formulas") for Black-Scholes-Merton and Bjerksund-Stensland 2002 that unit tests can check against.

## Answer

Resolved 2026-10-17 by [Research pricing models and inputs](0de4fb03-f042-47a3-8fc3-88dc21a9634a). Full findings, with a source and confidence level for every claim: `docs/research/pricing-models-and-inputs.md` on the local branch `research/pricing-models-and-inputs` (commit `84eae1f`, worktree at `../investor-basecamp-worktrees/research-pricing-models-and-inputs`). The branch is never merged.

- **American options:** use a Leisen-Reimer tree (odd step count, about 101 to 201) with discrete cash dividends. Use Black-Scholes-Merton for European index options (SPX, SPXW, XSP). At n=101 it is about 25 times more accurate in the worst case than Bjerksund-Stensland 2002, which can't model discrete dividends and degrades above about 40% volatility. Cost: about 0.3 s (n=101) to 0.9 s (n=201) for the whole grid with finite-difference greeks, single-threaded in Node. *Superseded 2026-10-24:* the engine runs server-side as a Python worker, not in a Web Worker; see [ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md).
- **Schwab's own values:** Black-Scholes for European and Bjerksund-Stensland for American options. It doesn't publish its rate, dividend treatment, or day count, and the evidence points to one flat rate and a continuous yield. Our values will match Schwab's to within cents only when we feed in Schwab's own inputs. Under our preferred model, expect gaps of tens of cents near ex-dividend dates and on long-dated, high-volatility options. So the cross-check needs a tolerance, not equality.
- **Dividends:** discrete dividends are needed for single stocks and ETFs. A continuous yield was off by up to about $0.30 per share on calls and $0.60 on puts when an ex-date falls inside a 30-day option. The Schwab quote's `fundamental` block appears to carry `divAmount`, `divPayAmount`, `divYield`, `divFreq`, `divExDate`, `nextDivExDate`, and related fields. The units come from a community source, so a live payload must confirm them.
- **Risk-free rate:** Treasury.gov's daily yield curve XML feed is official and keyless, and it allows browser requests. FRED needs a key. Interpolate the curve to each expiry and convert to continuous compounding. Matching the tenor matters mostly for long-dated options.
- **Time to expiry:** count calendar minutes divided by 525,600, up to the settlement instant. That's 4:00 pm ET for equity, ETF, SPXW, and XSP options, and 9:30 am ET on expiration Friday for AM-settled SPX.
- **Test oracles:** Haug's Black-Scholes-Merton values (4 decimals) and Tables 1 to 4 of the Bjerksund-Stensland 2002 paper (2 decimals) were reproduced. QuantLib's Bjerksund-Stensland value of 5.2704 is from the 1993 model, so it isn't valid for 2002.
- **Still unknown:** Schwab's actual rate source and tenor, whether its American model is the 1993 or 2002 version, its day count, and the units of the dividend fields and of the option chain's `volatility` and `interestRate`. These go to "Pull real Schwab payloads for your accounts".
