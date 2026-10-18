# Pricing models and inputs

Research for `.scratch/portfolio-risk-wayfinding/issues/06-pricing-inputs-and-models.md`, gathered 2026-10-17.

Each claim carries a source label and a confidence level:

- **[Primary]**: the paper, exchange, clearing house, regulator, or government agency that owns the fact.
- **[Vendor]**: Schwab's own documentation about Schwab's own products.
- **[Secondary]**: community SDKs, write-ups, or transcriptions. These are labelled wherever they are used.
- **[Experiment]**: something I measured with a throwaway harness written for this research: Node 22.22.2 (V8, the same engine as Chrome) on an arm64 Mac. The harness reproduces every published value cited in section 6, so its formulas are known to be right, but the numbers are mine, not a publication's.

Confidence: **High** means stated directly by a primary source or verified by reproduction; **Medium** means inferred from primary sources or stated by a credible secondary source; **Low** means indirect evidence only.

## Bottom line

- **Price American equity options with a Leisen-Reimer tree (odd n, about 101 to 201 steps) that drops discrete cash dividends, and use Black-Scholes-Merton for the European index options (SPX, SPXW, XSP).** At the stated workload, 5,000 American prices take about 40 ms, and with finite-difference greeks at every grid point (35,000 prices) about 0.3 s at n=101 or 0.9 s at n=201, single-threaded, so run it in a Web Worker. At n=101 Leisen-Reimer is about 25 times more accurate than Bjerksund-Stensland 2002 in the worst case, and Bjerksund-Stensland cannot represent discrete dividends at all.
- **Schwab says it uses Black-Scholes for European options and Bjerksund-Stensland for American options, but publishes neither its rate source, its dividend treatment, nor its day count.** thinkScript's own signature (a single `yield` and a single "global interest rate") points to a continuous dividend yield and one flat rate. So expect our numbers to match Schwab's to within cents only when we feed in Schwab's own implied volatility, rate, and days to expiry and use Bjerksund-Stensland with a continuous yield. Against our preferred model, expect gaps of tens of cents near ex-dividend dates and in high-volatility, long-dated options.
- **Discrete dividends are needed for single-stock and ETF options.** A continuous yield moved prices by up to about $0.30 per share for calls and $0.60 for puts when an ex-date falls inside a 30-day option. The Schwab quote's `fundamental` block carries `divAmount` (which appears to be annualised), `divPayAmount` (per payment), `divYield` (which appears to be in percent), `divFreq`, `divExDate`, `divPayDate`, `nextDivExDate`, `nextDivPayDate`, and `declarationDate`. The field units come from a community mirror of the spec and must be confirmed on a live payload.
- **For the rate, read Treasury's daily XML feed: it is official, needs no key, and sends `Access-Control-Allow-Origin: *`.** FRED's API needs a key. Use the coupon-equivalent rate (constant-maturity yield) interpolated to each expiry and converted to continuous compounding. Matching the tenor matters only for long-dated options: a 32 basis point curve slope moves a one-year at-the-money option by about $0.15 per share, but a 30-day option by about $0.01.
- **Count time to expiry in calendar minutes divided by 525,600, to the settlement instant.** That instant is 4:00 pm ET for PM-settled equity, ETF, SPXW, and XSP options, and 9:30 am ET on expiration Friday for AM-settled SPX (whose last trade is Thursday). For test oracles, Haug's Black-Scholes-Merton values (4 decimals, through QuantLib's transcription) and the Bjerksund-Stensland 2002 paper's own Tables 1 to 4 (2 decimals) are reliable, and all were reproduced here. I could not source 4-decimal Bjerksund-Stensland 2002 values from Haug's 2nd edition.

## 1. American options: Bjerksund-Stensland 2002 versus a binomial tree

### What the primary sources say

- **Bjerksund-Stensland 2002 is a closed-form lower bound.** It assumes a feasible but non-optimal exercise strategy: a flat exercise boundary over each of two sub-periods, split at the golden ratio, t = ½(√5 − 1)T. Puts are priced through the put-call transformation P(S, K, T, r, b, σ) = C(K, S, T, r − b, −b, σ). Where b ≥ r, early exercise of a call is never optimal, and the price is the European one. [Primary] High. [Bjerksund & Stensland (2002), "Closed Form Valuation of American Options", NHH Discussion Paper 2002:9, revised 21 Oct 2002](https://hdl.handle.net/11250/163705)
- **The paper's reported accuracy covers only modest volatilities.** Against a 3,201-step binomial tree on the Barone-Adesi-Whaley test set (K = 100, σ ≤ 0.40, T ≤ 3), the two-step method's worst errors were 0.03 (Table 1), 0.04 (Tables 2 and 3) and 0.07 (Table 4). The authors note that "more accurate methods exist, but at the expense of computer efficiency". They state that greeks can be derived in closed form but omit them. [Primary] High. [Same paper](https://hdl.handle.net/11250/163705)
- **Leisen-Reimer trees converge faster than CRR.** The authors prove first-order convergence for Cox-Ross-Rubinstein (CRR) trees, which also oscillate. Their trees use the Peizer-Pratt inversion with an odd number of steps. For European options they converge at second order with "much smaller initial error". For American options convergence is first order, but they reach "the same accuracy on average ten-times faster than previous binomial methods". [Primary] High. [Leisen & Reimer (1996), Applied Mathematical Finance 3(4):319–346](https://doi.org/10.1080/13504869600000015); [working-paper text](https://wiwi.uni-bonn.de/sfb303/papers/1995/b/bonnsfb309.pdf)

### Measured accuracy and speed

All figures in this subsection are [Experiment].

The accuracy sample was 300 random American options: S = 100, K from 80 to 120, 7 to 365 days, σ from 15% to 80%, r = 4.3%, dividend yield 0 to 4%, calls and puts. The reference price for each is a Leisen-Reimer tree with n = 10,001.

| Method | Max abs error | RMSE | Max relative error (prices > $0.50) |
| --- | --- | --- | --- |
| European BSM (ignores early exercise) | 1.3055 | 0.2152 | 7.11% |
| Bjerksund-Stensland 2002 | 0.2394 | 0.0496 | 0.79% |
| CRR, n = 100 | 0.0649 | 0.0237 | 0.59% |
| CRR, n = 500 | 0.0124 | 0.0044 | 0.17% |
| Leisen-Reimer, n = 101 | 0.0090 | 0.0017 | 0.11% |
| Leisen-Reimer, n = 201 | 0.0044 | 0.0009 | 0.06% |
| Leisen-Reimer, n = 501 | 0.0017 | 0.0003 | 0.02% |

The speed test priced 50 Positions across 100 spot Shocks. "With greeks" adds central differences for delta and gamma, a ±1-point vega, a one-day theta, and a 1 basis point rho at every grid point, which is 7 prices per point. Times are the median of 5 runs on one thread.

| Method | 5,000 prices | 35,000 prices (with greeks) |
| --- | --- | --- |
| Bjerksund-Stensland 2002 | 22 ms | 150 ms |
| CRR, n = 100 | 39 ms | 271 ms |
| Leisen-Reimer, n = 101 | 40 ms | 279 ms |
| Leisen-Reimer, n = 201 | 122 ms | 859 ms |
| Leisen-Reimer, n = 501 | 631 ms | 4,501 ms |

Three findings matter for the design:

- **Bjerksund-Stensland 2002's error grows quickly with volatility.** I priced a grid of puts and calls at T of 0.1, 0.5, and 1 year, K/S of 0.8, 1.0, and 1.2, and q of 0 and 3%. The worst absolute error per $100 of underlying was 0.04 at σ = 20%, 0.08 at 40%, 0.21 at 60%, and 0.46 at 80%. The paper never tests above 40%, so this doesn't contradict it. [Experiment] High.
- **Bjerksund-Stensland 2002 can price below the European value.** Take a call with S = 100, K = 80, T = 1, r = 4.3%, q = 3%, σ = 80%. Bjerksund-Stensland gives 38.070, the European value is 38.299, and the true American value is 38.526 (CRR at 4,000 steps agrees). To rule out a bug, I valued the paper's own two-step exercise rule on an 8,000-step lattice and got 38.0815, matching the closed form up to discrete-monitoring bias. The heuristic boundary is simply poor in that region. Taking max(BS2002, European) is a cheap guard, but it doesn't recover accuracy. [Experiment] High.
- **Greeks.** Finite-difference gamma from Bjerksund-Stensland is accurate away from early exercise. Near the model's approximate exercise boundary, though, the price kinks into intrinsic value at the wrong spot. For a put with K = 100, T = 0.25, σ = 30%, the Bjerksund-Stensland gamma is 0.034 at S = 80 against a true 0.017. CRR with n = 100 oscillates: its gamma error reaches 147% of peak gamma. Leisen-Reimer at n = 101 stayed within 5% of peak gamma across S from 80 to 120, and n = 201 within 2%. [Experiment] High.

Trees also handle discrete cash dividends directly (section 3); Bjerksund-Stensland only accepts a continuous cost of carry b. [Primary] High. [Bjerksund & Stensland 2002, section 2](https://hdl.handle.net/11250/163705)

**Recommendation.** Use Leisen-Reimer with n = 101 for the Shock grid and n = 201 for the headline values and greeks of the current Snapshot, with discrete dividends, inside a Web Worker. Use closed-form Black-Scholes-Merton for European-exercise index options (SPX, SPXW, XSP). Keep Bjerksund-Stensland 2002 only as a "Schwab mode" pricer for cross-checking (section 2). Avoid CRR: it costs the same as Leisen-Reimer and gives jagged gammas.

## 2. What thinkorswim and the Schwab Trader API use

### Documented

- **Models.** "Charles Schwab uses the Black-Scholes model for European-style options, and the Bjerksund-Stensland for American-style options." The glossary entry "Model" repeats this. [Vendor] High. [thinkorswim Learning Center glossary, "Option Pricing Model"](https://toslc.thinkorswim.com/center/Glossary/O); [glossary, "Model"](https://toslc.thinkorswim.com/center/Glossary/M)
- **Implied volatility.** thinkorswim's Implied Volatility study "is calculated using approximation method based on the Bjerksund-Stensland model". The page doesn't say whether that means 1993 or 2002. [Vendor] High (model family); Low (which version). [ImpVolatility study](https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/G-L/ImpVolatility)
- **Inputs to thinkScript's theoretical price.** `OptionPrice(strike, isPut, daysToExpiration, underlyingPrice, Volatility, isEuropean, yield, interestRate)`. By default `yield` comes from `GetYield()` ("the yield of the current stock or the underlying symbol") and `interestRate` from `GetInterestRate()` ("the global interest rate"). [Vendor] High. [OptionPrice](https://toslc.thinkorswim.com/center/reference/thinkScript/Functions/Option-Related/OptionPrice); [GetYield](https://toslc.thinkorswim.com/center/reference/thinkScript/Functions/Others/GetYield); [GetInterestRate](https://toslc.thinkorswim.com/center/reference/thinkScript/Functions/Others/GetInterestRate)
  - Inference: a single scalar yield means a continuous dividend yield, not a dividend schedule, and a single global rate means no tenor matching. Medium.
- **Volatility setting.** thinkorswim's Setup > General > Calculations offers three volatility modes for theoretical values: individual implied volatility, volatility smile approximation, and fixed volatility per expiration date. [Vendor] High. [thinkorswim Setup](https://toslc.thinkorswim.com/center/howToTos/thinkManual/Getting-Started/thinkorswim-Setup)
- **Days to expiration.** `GetDaysToExpiration()` "returns the number of days till the expiration". Its example labels `== 1` as "Expiration Friday" and `== 7 * weeks + 1` as four weeks before, which suggests whole calendar days counted inclusively of expiration day, with no time of day. [Vendor] Low (inferred from an example). [GetDaysToExpiration](https://toslc.thinkorswim.com/center/reference/thinkScript/Functions/Option-Related/GetDaysToExpiration)
- **Option-chain response fields.** Each contract carries `volatility`, `delta`, `gamma`, `theta`, `vega`, `rho`, `theoreticalOptionValue`, `theoreticalVolatility`, `daysToExpiration`, `expirationDate`, `lastTradingDay`, `expirationType`, and `settlementType`. At the top level the chain carries `interestRate`, `volatility`, `underlyingPrice`, and `daysToExpiration`. An `ANALYTICAL` strategy request accepts `volatility`, `underlyingPrice`, `interestRate`, and `daysToExpiration` overrides; there is **no dividend override**. [Secondary] Medium. [schwab-py `get_option_chain`](https://schwab-py.readthedocs.io/en/latest/client.html); [`schwab_api` Rust crate option-chain model](https://docs.rs/schwab_api/latest/src/schwab_api/model/market_data/option_chain.rs.html). Schwab's own spec is behind the developer-portal login (`developer.schwab.com` returned HTTP 403 without a session), so these mirrors are the best available.

### Indirect evidence on inputs

StreetSmart Edge, an older Schwab platform whose help site no longer resolves, documented its "Theoretical View" defaults. The percent-interest input "defaults to the current $IRX (CBOE 13 week treasury bill index…)". The dividend-yield input "assumes a continuous dividend… It defaults to the actual dividend yield paid over the last year". Model choices there were Black-Scholes, Barone-Adesi-Whaley, and Cox-Ross-Rubinstein, and theta was "the change in option value for the next day passing". [Vendor, different platform] Low as evidence for thinkorswim or the API. Quoted from search-index captures of [StreetSmart Edge help 1.58, "Theoretical View"](https://help.streetsmart.schwab.com/edge/1.58/Content/Theoretical%20View.htm) and [1.40](https://help.streetsmart.schwab.com/edge/1.40/Content/Theoretical%20View.htm), which could not be re-fetched today.

### Not documented anywhere I could find

- Which rate the thinkorswim "global interest rate" and the API's `interestRate` are.
- Whether the Bjerksund-Stensland variant is 1993 or 2002.
- Whether time is counted in calendar or trading days, and at what time of day.
- Whether `theoreticalOptionValue` is computed from the contract's own IV or from a smoothed IV.

### How close the cross-check should land

This part is my judgment, not documented.

- **Schwab mode should land within about $0.01 to $0.02.** Schwab mode means Bjerksund-Stensland 2002 for American options and BSM for European ones, fed with the chain's own `volatility`, top-level `interestRate`, contract `daysToExpiration`, and `divYield` as a continuous yield. If the documented models and the inferred inputs are right, this should match `theoreticalOptionValue` to within a cent or two for liquid, near-the-money contracts. Residual gaps would come from the 1993 versus 2002 variant, day count, and time of day. This should be tested on real payloads under issue 05.
- **Our preferred model will differ by more.** Leisen-Reimer with discrete dividends should differ from Schwab by up to tens of cents around ex-dividend dates (section 3), and by up to tenths per $100 of underlying for high-IV, long-dated, deep in-the-money American options (section 1). Those differences are expected, not bugs.
- **Greeks need unit conversion before comparing.** Compare in the units Schwab uses (theta per calendar day, vega per volatility point) once a live payload confirms them.

**Recommendation.** Build the cross-check as two comparisons. First, Schwab mode against `theoreticalOptionValue` and the greeks, with a tight tolerance, to validate our plumbing. Second, our model against Schwab mode, reporting the difference rather than failing on it. Confirm the units of `volatility` and `interestRate` (percent or fraction) from a live payload first.

## 3. Dividends

### Continuous yield versus discrete dividends

- **Early exercise of a call only happens just before an ex-date.** "For an American-style call option with a discrete dividend, early exercise is only optimal instantaneously prior to the ex-dividend date (Merton, 1973)." [Primary] High. [Haug, Haug & Lewis (2003), "Back to Basics: a new approach to the discrete dividend problem", Wilmott](https://doi.org/10.1002/wilm.42820030514); [preprint](https://nccr-finrisk.uzh.ch/media/pdf/ODD.pdf)
- **A yield is not viable for single-stock options.** "For options on a large portfolio of stocks, one can approximate discrete dividend payouts with a dividend yield… For options on one stock, this is not a viable approximation, and the discreteness of the dividend has to be explicitly modelled." [Primary] High. [Same paper](https://nccr-finrisk.uzh.ch/media/pdf/ODD.pdf)
- **Common shortcuts are biased.** The same paper shows that escrowed-dividend shortcuts (spot minus the present value of dividends), including Black (1975) and Roll-Geske-Whaley, "will in general undervalue call options". The mispricing is larger the later the dividend falls, and Roll-Geske-Whaley "can open up arbitrage opportunities". It proposes letting the full price evolve and dropping it by the cash dividend at the ex-date. [Primary] High. [Same paper](https://nccr-finrisk.uzh.ch/media/pdf/ODD.pdf)
- **The clearing house's view.** "As a general rule, no adjustment is made for ordinary cash dividends." "A call holder becomes entitled to the dividend if he exercises the option prior to the ex-dividend date…", so "a call writer's chances of being assigned an exercise may increase as the ex-date… approaches." Only non-ordinary dividends of at least $12.50 per contract trigger an adjustment. [Primary] High. [OCC, Characteristics and Risks of Standardized Options (June 2024), ch. III](https://www.theocc.com/getcontentasset/dd6200a7-5982-4226-90e4-1f2d32a89911/dfc3d011-8f63-43f6-9ed8-4b444333a1d0/june_2024_riskstoc.pdf); [OCC interpretative guidance on cash dividends](https://www.theocc.com/getcontentasset/21ed2c99-ab15-472a-aef1-a142f140e2b7/dfc3d011-8f63-43f6-9ed8-4b444333a1d0/interpretative-guidance-on-the-adjustment-policy-for-cash-dividends-and-distributions.pdf)

### Measured size of the error

[Experiment] High for the direction of the error; Medium for exact size, because the discrete column uses an escrowed-dividend lattice, which Haug, Haug & Lewis show is slightly biased.

Inputs: an American option with S = 100, σ = 25%, r = 4.3%, and one $1.00 dividend (the "discrete" column), against a continuous q = 4%, which is the same annual amount.

| Type | K | Days to expiry | Ex-date (day) | Discrete | Continuous q (Leisen-Reimer) | Continuous q (Bjerksund-Stensland) |
| --- | --- | --- | --- | --- | --- | --- |
| Call | 100 | 30 | 10 | 2.5600 | 2.8617 | 2.8615 |
| Call | 95 | 30 | 10 | 5.6838 | 5.9713 | 5.9709 |
| Call | 90 | 30 | 29 | 10.4767 | 10.2066 | 10.2057 |
| Call | 90 | 90 | 45 | 11.4100 | 11.2592 | 11.2572 |
| Put | 100 | 30 | 29 | 3.1780 | 2.8393 | n/a |
| Put | 110 | 30 | 29 | 10.8814 | 10.2831 | n/a |

The error goes in both directions and reaches about $0.30 per share ($30 per contract) for calls and $0.60 for puts, whenever a whole quarterly dividend falls inside a short option's life. A continuous yield spreads only about a third of it over 30 days.

### Dividend fields in the Schwab quote

These come from `GET /marketdata/v1/quotes?fields=fundamental` (or `all`), in the per-symbol `fundamental` object. [Secondary] Medium. [`schwab_api` crate, Fundamental struct (doc comments mirror the OpenAPI descriptions and examples)](https://docs.rs/schwab_api/latest/src/schwab_api/model/market_data/quote_response/equity.rs.html); [`schwab-sdk` crate quotes model](https://docs.rs/schwab-sdk/latest/src/schwab_sdk/market_data/quotes.rs.html)

| Field | Spec description | Spec example |
| --- | --- | --- |
| `divAmount` | Dividend Amount | 0.88 |
| `divPayAmount` | Dividend Pay Amount | 0.22 |
| `divYield` | Dividend yield | 0.7 |
| `divFreq` | 1, 2, 3, 4, 6, 11, or 12 payments a year (nullable) | — |
| `divExDate` | Dividend date | 2021-05-07T00:00:00Z |
| `divPayDate` | Dividend pay date | 2021-05-13T00:00:00Z |
| `declarationDate` | Declaration date | 2021-04-28T00:00:00Z |
| `nextDivExDate` | Next Dividend date | 2021-02-12T00:00:00Z |
| `nextDivPayDate` | Next Dividend pay date | 2021-02-12T00:00:00Z |

**Inferred units.** The example values match Apple's April 2021 dividend: declared 28 April 2021, $0.22 per share, payable 13 May. That makes `divAmount` the annualised amount (4 × 0.22 = 0.88), `divPayAmount` the per-payment amount, and `divYield` a percentage (0.88 ÷ ~$125 ≈ 0.70%). [Primary for Apple's dividend: [Apple dividend history](https://investor.apple.com/dividend-history/default.aspx), [Apple Q2 FY21 press release](https://www.apple.com/newsroom/2021/04/apple-reports-second-quarter-results/)]. Inference Medium.

**Conflicting sources.** One community project says `divYield` is in percent, "verified against the live API" ([schwab_cli](https://github.com/weig/schwab_cli/blob/567782c1/src/schwab_cli/output/fundamentals.py), [Secondary]). Another crate's comment calls it "a fraction" ([schwab-sdk](https://docs.rs/schwab-sdk/latest/src/schwab_sdk/market_data/quotes.rs.html), [Secondary]). The spec's own example dates are inconsistent (`nextDivExDate` precedes `divExDate`), so they say nothing about whether `nextDivExDate` is announced or projected. Low.

**Recommendation.** Model the next dividend discretely, with amount `divPayAmount` and ex-date `nextDivExDate`, falling back to `divExDate` + 12/`divFreq` months. Project later dividends inside the option's life at the same amount and frequency. Use a cash drop at the ex-date in the Leisen-Reimer tree. Use a continuous yield only for index options (SPX, SPXW, XSP), which are European. Pull one live payload (issue 05) to pin down `divAmount` versus `divPayAmount`, the percent units of `divYield`, and how fresh `nextDivExDate` is, before relying on them.

## 4. Risk-free rate

### Sources

- **Treasury daily XML feed.** `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=<key>&field_tdr_date_value_month=<yyyymm>`, with keys including `daily_treasury_yield_curve` (par/CMT, 1, 1.5, 2, 3, 4, and 6 months, then 1 to 30 years) and `daily_treasury_bill_rates`. No key or registration is mentioned. [Primary] High. [Treasury Daily Interest Rate XML Feed](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed)
  - On 2026-10-17 the feed returned HTTP 200 with `Access-Control-Allow-Origin: *` and no key, and the 2026-10-16 row was stamped `2026-10-17T02:01Z`. [Experiment] High.
- **What the Treasury rates are.** They are indicative bid-side quotes obtained by the New York Fed "at approximately 3:30 PM each business day". "Bank Discount" is on par value with a 360-day year. "Coupon Equivalent, also called the Bond Equivalent, or the Investment Yield" is on purchase price with a 365- or 366-day year. CMT yields are bond-equivalent (semiannual) on actual/365, floored at zero. [Primary] High. [Treasury Daily Rates text view and notes](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_bill_rates&field_tdr_date_value_month=202610); [Interest Rates FAQ](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/interest-rates-frequently-asked-questions)
- **FRED.** `DGS3MO` is the 3-month constant maturity, investment basis; `DTB3` is the 3-month bill on a discount basis. Both are daily, sourced from the Fed's H.15, and published the next business day. The FRED API needs a key: "All web service requests require an API key", and each user needs their own. [Primary] High. [DGS3MO](https://fred.stlouisfed.org/series/DGS3MO); [DTB3](https://fred.stlouisfed.org/series/DTB3); [FRED API keys](https://fred.stlouisfed.org/docs/api/api_key.html)
  - The series-page download URL (`fredgraph.csv?id=DGS3MO`) returned data without a key but sent no CORS header. It's an undocumented convenience link. [Experiment] Medium.
- **Fed H.15.** Posted daily at 4:15 pm; footnotes say bill rates are "on a discount basis" and "annualized using a 360-day year". On 2026-10-15: 1-month CMT 4.17, 3-month CMT 4.28, 1-year CMT 4.49, 3-month bill (discount) 4.10. [Primary] High. [H.15 Selected Interest Rates](https://www.federalreserve.gov/releases/h15/)

DTB3 (4.10) and DGS3MO (4.28) differ mostly by convention, not market. Don't feed the discount-basis rate into a continuous-compounding model.

### Tenor convention

- **Cboe matches tenor.** The VIX calculation uses "U.S. Treasury yield curve rates (commonly referred to as 'Constant Maturity Treasury' rates), to which a cubic spline is applied to derive yields on the expiration dates", so different expiries get different rates. [Primary] High. [Cboe VIX Methodology](https://cdn.cboe.com/resources/vix/VIX_Methodology.pdf)
- **Schwab's retired platform did not.** StreetSmart Edge used the 13-week bill ($IRX) for everything. thinkorswim exposes one "global interest rate" (section 2). [Vendor] Low to Medium.
- **The tenor choice is small for short options.** Using the 1-month (4.17%) versus 1-year (4.49%) CMT from 2026-10-15, a 32 basis point gap, moved an at-the-money call (S = K = 100, σ = 30%) by $0.003 at 7 days, $0.013 at 30 days, $0.039 at 90 days, and $0.153 at 1 year. [Experiment] High.

### Conversion to continuous compounding

These are derived from Treasury's definitions above; Medium.

- **CMT** (semiannual bond-equivalent, per the Treasury FAQ's APY formula): r_c = 2 ln(1 + y/2).
- **Bill coupon-equivalent** (simple yield on actual/365 over d days): r_c = (365/d) ln(1 + y·d/365).
- At 4% to 4.3% the conversion lowers the rate by about 4 to 5 basis points for a CMT, and by about 1 to 2 basis points for a 4- to 13-week bill. That is negligible next to IV error for short options.

**Recommendation.** Fetch `daily_treasury_yield_curve` once a day, server-side or in the browser, and store it. Linearly interpolate the CMT points (1, 1.5, 2, 3, 4, 6 months, 1 year, and so on) to each option's expiry, convert to continuous, and fall back to the latest available day on holidays. Tenor matching is cheap once the curve is cached, so do it, but it only changes long-dated (LEAPS) values. Don't use FRED in the browser: it needs a key and lacks CORS.

## 5. Time to expiry

### Settlement instants

- **Standard equity options.** American-style, monthly expiry on the third Friday, trading 9:30 am to 4:00 pm ET. [Primary] High. [OCC Equity Options specs](https://www.theocc.com/clearance-and-settlement/clearing/equity-options-product-specifications)
  - Since February 2015 the formal expiration date is the third Friday, with expiration time 11:59 pm ET. [Primary] High. [SEC Release 34-69772](https://www.sec.gov/files/rules/sro/occ/2013/34-69772.pdf)
  - Holders have until 5:30 pm ET to make a final exercise decision. [Primary] High. [FINRA Information Notice 2/3/21, Rule 2360(b)(23)(A)(iii)](https://www.finra.org/rules-guidance/notices/information-notice-020321)
  - The last price observation is the 4:00 pm close; the after-hours exercise window is a tail risk rather than a pricing input. Medium (my judgment).
- **SPX, AM-settled.** Trading "will ordinarily cease on the business day (usually a Thursday) preceding the day on which the exercise-settlement value… is calculated". Settlement comes from a special opening quotation built from each constituent's opening trade on expiration Friday, and it "is not anchored to a specific time of day". [Primary] High. [Cboe SPX specifications](https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/); [Cboe, Settlement of A.M.-Settled SPX Options](https://cdn.cboe.com/resources/spx/Settlement_of_Standard_AM_Settled_SP_500_Index_Options.pdf)
- **SPXW, PM-settled.** Trading "will ordinarily cease on the day of expiration, 4:00 pm ET, and at 1:00 pm ET for any half day holiday". Settlement uses closing prices. [Primary] High. [Cboe SPX specifications](https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/); [SPX fact sheet](https://cdn.cboe.com/resources/spx/spx-fact-sheet.pdf)
- **XSP.** European, with settlement value "one-tenth (1/10th) the official closing price of the S&P 500 Index… on the last trading day". The last trading day is the expiration date, and expiring series stop trading at 4:00 pm ET (3:00 pm Chicago). Cboe's fact sheet lists XSP as PM-settled. Cboe rules still allow AM-settled XSP series. [Primary] High. [Cboe XSP specifications](https://www.cboe.com/tradable_products/sp_500/mini_spx_options/specifications/); [XSP fact sheet](https://cdn.cboe.com/resources/xsp/XSP_Options_Fact_Sheet.pdf); [SR-CBOE-2025-022, Rule 4.13 Interpretation .13](https://www.sec.gov/files/rules/sro/cboe/2025/34-102752-ex5.pdf)
- **Cboe's own clock.** "Standard SPX options are deemed to expire at the open of trading (i.e., 9:30 a.m. ET)… Weekly SPXW options are deemed to expire at the close of trading (i.e., 4:00 p.m. ET)." The VIX "measures time-to-expiration in calendar days and divides each day into minutes": T = (minutes left today + minutes to settlement on the settlement day + minutes in the days between) / 525,600. [Primary] High. [Cboe VIX Methodology](https://cdn.cboe.com/resources/vix/VIX_Methodology.pdf); [Cboe Volatility Index Mathematics Methodology](https://cdn.cboe.com/resources/indices/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf)

### Calendar time versus trading time

- **Most variance arrives during trading hours.** "The variance of returns from the open to the close of trading on an average day is over six times larger than the variance of close-to-open returns over a weekend, even though the weekend is eleven times longer"; per hour, trading-time variance is 13 to 100 times larger. [Primary] High. [French & Roll (1986), Journal of Financial Economics 17:5–26](https://www.anderson.ucla.edu/documents/areas/fac/finance/1986-3.pdf)
- **The choice matters a lot for short-dated theta.** A 7-day at-the-money call (σ = 30%) loses 0.42 from Friday to Monday on a calendar clock, but 0.19 on a one-trading-day (÷252) clock. [Experiment] High.
- **AM versus PM matters near expiry.** The 6.5-hour gap between an AM and a PM expiry is worth about 0.033% of the underlying for an at-the-money option two days out at σ = 15%, roughly 2 SPX points. [Experiment] High.
- **Market IVs are calendar-based.** Cboe uses calendar minutes, and thinkorswim's days-to-expiration appears to count calendar days (section 2), so a trading-day clock would make our IVs inconsistent with theirs. High for Cboe; Low for Schwab.

**Recommendation.** Compute T = (settlement instant − now) in minutes / 525,600, working in `America/New_York` so daylight-saving changes are handled. Use 16:00 ET on the expiration date for equity, ETF, SPXW, and XSP options (13:00 on half days for SPXW), and 09:30 ET on the settlement Friday for AM-settled SPX, whose last trade is Thursday. Report theta per calendar day. Move the days-forward part of a Shock in calendar days. A trading-time clock is a possible later refinement for 0 to 7 day options, but it would make our IVs inconsistent with quoted ones.

## 6. Test oracles

### Black-Scholes-Merton (Haug)

These are Haug's values from *The Complete Guide to Option Pricing Formulas*, 1st edition (1998), pages 2 to 27, as transcribed in QuantLib's test suite. The book itself wasn't available to me, so QuantLib is the transcription [Secondary]. I recomputed every row to 4 decimals with generalised BSM, using b = r − q; all match [Experiment]. High. [QuantLib `test-suite/europeanoption.cpp`, `testValues` and `testGreekValues`](https://github.com/lballabio/QuantLib/blob/master/test-suite/europeanoption.cpp)

| Type | S | K | T | r | q (b = r − q) | σ | Expected |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Call | 60 | 65 | 0.25 | 0.08 | 0.00 | 0.30 | 2.1334 |
| Put | 100 | 95 | 0.50 | 0.10 | 0.05 | 0.20 | 2.4648 |
| Put | 19 | 19 | 0.75 | 0.10 | 0.10 | 0.28 | 1.7011 |
| Call | 19 | 19 | 0.75 | 0.10 | 0.10 | 0.28 | 1.7011 |
| Call | 1.56 | 1.60 | 0.50 | 0.06 | 0.08 | 0.12 | 0.0291 |
| Put | 75 | 70 | 0.50 | 0.10 | 0.05 | 0.35 | 4.0870 |
| Call | 42 | 40 | 0.75 | 0.04 | 0.08 | 0.35 | 5.0975 |
| Call delta | 105 | 100 | 0.50 | 0.10 | 0.10 | 0.36 | 0.5946 |
| Put delta | 105 | 100 | 0.50 | 0.10 | 0.10 | 0.36 | −0.3566 |
| Gamma (call or put) | 55 | 60 | 0.75 | 0.10 | 0.00 | 0.30 | 0.0278 |
| Vega (per 1.00 σ) | 55 | 60 | 0.75 | 0.10 | 0.00 | 0.30 | 18.9358 |
| Put theta (per year) | 430 | 405 | 1/12 | 0.07 | 0.05 | 0.20 | −31.1924 |
| Put theta (per day, ÷365) | 430 | 405 | 1/12 | 0.07 | 0.05 | 0.20 | −0.0855 |
| Call rho (per 1.00 r) | 72 | 75 | 1.00 | 0.09 | 0.00 | 0.19 | 38.7325 |
| Put dividend rho | 500 | 490 | 0.25 | 0.08 | 0.05 | 0.15 | 42.2254 |

QuantLib also transcribes Haug's page-24 grid of 36 European values (K = 100, r = q = 0.10, T of 0.10 or 0.50, σ of 0.15, 0.25, or 0.35); use a tolerance of 1e-4.

### Bjerksund-Stensland 2002 (from the paper)

These are values from the paper's Tables 1 to 3, all with K = 100. The paper prints 2 decimals, so use a tolerance of 0.005. I reproduced all 65 two-step values and all 65 flat-boundary values to within 0.005 [Experiment]. [Primary] High. [Bjerksund & Stensland (2002), Tables 1–3](https://hdl.handle.net/11250/163705)

Column meanings:

- **"Two-step"** is the Bjerksund-Stensland 2002 value.
- **"Flat"** is the paper's one-boundary variant, which uses the *modified* h(T) from its Eq. (11). It is not the 1993 model.
- **"Binomial"** is the paper's 3,201-step reference tree.

| Type | S | T | r | b | σ | Binomial | Flat | Two-step |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Call | 90 | 0.25 | 0.08 | −0.04 | 0.20 | 0.58 | 0.57 | 0.58 |
| Call | 100 | 0.25 | 0.08 | −0.04 | 0.20 | 3.52 | 3.49 | 3.51 |
| Call | 110 | 0.25 | 0.08 | −0.04 | 0.20 | 10.36 | 10.32 | 10.34 |
| Put | 100 | 0.25 | 0.08 | −0.04 | 0.20 | 4.39 | 4.40 | 4.40 |
| Call | 100 | 0.25 | 0.08 | −0.04 | 0.40 | 7.41 | 7.37 | 7.39 |
| Call | 120 | 0.25 | 0.08 | −0.04 | 0.40 | 21.29 | 21.23 | 21.26 |
| Call | 100 | 0.50 | 0.08 | −0.04 | 0.20 | 4.71 | 4.65 | 4.69 |
| Put | 90 | 0.25 | 0.08 | 0.04 | 0.20 | 10.22 | 10.19 | 10.21 |
| Put | 100 | 0.25 | 0.08 | 0.04 | 0.20 | 3.55 | 3.51 | 3.53 |
| Put | 80 | 0.25 | 0.08 | 0.04 | 0.40 | 20.59 | 20.53 | 20.55 |
| Put | 100 | 0.25 | 0.08 | 0.04 | 0.40 | 7.47 | 7.42 | 7.45 |
| Put | 100 | 0.50 | 0.08 | 0.04 | 0.20 | 4.77 | 4.70 | 4.74 |
| Put | 100 | 0.25 | 0.08 | 0.08 | 0.20 | 3.22 | 3.16 | 3.20 |
| Put | 90 | 0.25 | 0.08 | 0.08 | 0.40 | 12.57 | 12.48 | 12.54 |
| Put | 100 | 0.50 | 0.08 | 0.08 | 0.20 | 4.19 | 4.11 | 4.15 |

Table 4 adds T = 3 cases with b of −0.04, 0, 0.04, and 0.08, and is worth transcribing too.

### Values that look like oracles but aren't for this model

- **Haug 1998 page 27, call S = 42, K = 40, T = 0.75, r = 0.04, q = 0.08, σ = 0.35 → 5.2704.** QuantLib transcribes this as a Bjerksund-Stensland value, but it is the **1993** flat-boundary model, which is what QuantLib's engine implements ("Bjerksund and Stensland pricing engine for American options (1993)"). Use it only if a 1993 variant is ever implemented. [Secondary] High. [QuantLib `americanoption.cpp`](https://github.com/lballabio/QuantLib/blob/master/test-suite/americanoption.cpp); [`bjerksundstenslandengine.hpp`](https://github.com/lballabio/QuantLib/blob/master/ql/pricingengines/vanilla/bjerksundstenslandengine.hpp)
- **Haug's 2nd edition (2007)** covers Bjerksund-Stensland 2002, but I couldn't access the book, so none of its numbers appear here.

### Property tests that need no published numbers

- An American call with b ≥ r equals the BSM call.
- A put priced directly equals the put-call transformation of a call (Bjerksund-Stensland Eq. 19).
- Leisen-Reimer converges monotonically as odd n grows.
- An American price is at least the larger of the European price and intrinsic value. Bjerksund-Stensland 2002 *fails* this at high σ and long T (section 1), so assert it on the tree, not on Bjerksund-Stensland.

**Recommendation.** Unit-test BSM prices and greeks against the Haug table at 1e-4. Test Bjerksund-Stensland 2002 against the paper's two-step column at 0.005. Test the Leisen-Reimer American pricer against the paper's binomial column at about 0.015: my n = 3,201 trees differed from it by up to 0.011, so its last digit isn't exact. Add the property tests above.

## Open questions

- Which rate thinkorswim and the Schwab API use for `interestRate`, and whether it is matched to expiry. Not documented. The API echoes the rate in the chain response, so record it from live payloads.
- Whether Schwab's American model is Bjerksund-Stensland 1993 or 2002, and its day count and time-of-day convention. Not documented. These could be inferred by fitting `theoreticalOptionValue` on live chains.
- The exact units and semantics of the Schwab `divAmount`, `divYield`, `nextDivExDate`, chain `volatility`, and `interestRate` fields. Community sources conflict, and the official spec is behind the developer-portal login. Settle this in issue 05.
- Whether thinkorswim models discrete dividends anywhere (for example in Analyze). No first-party statement found either way.
- How fast Safari's and Firefox's JavaScript engines run the same harness. Only V8 (Node) was measured.
