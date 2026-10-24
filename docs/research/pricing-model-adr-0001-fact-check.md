# Fact-check: ADR 0001 "Compute IV and greeks with our own pricing model"

Gathered 2026-10-23. Scope: [ADR 0001](../adr/0001-own-pricing-model.md) (Leisen-Reimer tree with discrete dividends for American options, Black-Scholes-Merton for European index options, own IV and greeks instead of Schwab's).

Labels used throughout:

- **[Read]**: I opened the primary source and read the cited passage.
- **[Cited]**: I could not open it. The claim is relayed from another document I did read, and is not independently verified.
- **[Own]**: my computation (section 4), not a publication.
- **[Secondary]**: community SDK docs or write-ups. Never used as the only support for a verdict.

## 1. Bottom line

The strategy is **not optimal as written**, though its core choices are defensible. For American options, Leisen-Reimer (LR) is a good numerical engine: with no dividends, n=201 was within 0.5 cent of a converged reference in every case I ran, against up to 15 cents for Barone-Adesi-Whaley (BAW) and 24 cents for a Bjerksund-Stensland 1993 implementation. But "with discrete dividends" is under-specified, and that is where the money is. The only tree that recombines is the escrowed one, which runs below the cash-drop (spot) dividend model by 8 cents (about 0.4 vol point) for one dividend late in a 3-month 40% option, and by $1.25 (about 2.7 vol points) on a 2-year 60% option with quarterly dividends. For several dividends or long expiries, use a finite-difference (PDE) solver with the cash drop at the ex-date, or a Vellekoop-Nieuwenhuis-style tree. For American calls on non-dividend stocks (most current holdings) use closed-form BSM, because early exercise is never optimal.

For European index options, the BSM formula is right but the usual inputs are not. Price off the **parity-implied forward** per expiry (Black-76 form), not spot with a continuous yield. A wrong yield alone moves SPX call IV and put IV in opposite directions by 0.4 to 1.2 vol points (section 4.6). VIX options need the VIX **future** of the same expiry, not spot VIX. Settlement clock (AM versus PM) and expiry-specific rates also matter near expiry.

The ADR's reason for "own model" (consistent base and shocked values, hypothetical Positions) is sound. Its supporting claim that "Schwab's numbers can't be reproduced" is overstated: thinkorswim documentation names the models (Black-Scholes, Bjerksund-Stensland), the chain payload returns a rate, volatility and days-to-expiry, and Schwab's `/chains` ANALYTICAL strategy accepts volatility, underlying price, rate and days-to-expiration overrides. What the Schwab OpenAPI specifications do **not** do (section 7) is define any of those fields, document a dividend input, or name a model, so the ADR is right that the exact numbers are not reproducible from published material. Suggested amendments are in section 5.

## 2. Claim-by-claim table

Verdicts: confirmed / partly / unsupported / wrong.

| # | Claim (ADR or from the brief) | Verdict | Evidence | Source |
| --- | --- | --- | --- | --- |
| 1 | LR converges faster and more smoothly than CRR for vanilla options | **Confirmed** | CRR is proved order 1 and oscillates. LR "converge[s] smoothly... order of convergence two with much smaller initial error" for European calls. [Own] European ATM call, n=101: LR error 4e-5, CRR 2e-2. | Leisen & Reimer, SFB 303 DP B-309 (1995), abstract and sec. 3-5 [Read]. Journal version AMF 3(4):319-346 (1996) is paywalled [Cited]. |
| 2 | LR is better for American options too | **Confirmed, with a limit** | Abstract: American options still "order of convergence one but smaller initial error". Sec. 5: early-exercise premia "involve original sources of irregularities". [Own] American put, n=201: LR error 4e-4, CRR 1.05e-2; LR error at n=1001 is still 1.8e-4 (first order). The "ten times faster" figure in earlier repo notes is not in the working paper I read: unsupported by what I read. | B-309 abstract and sec. 5 [Read] |
| 3 | LR needs an odd step count | **Confirmed** | Explicit Peizer-Pratt inversion requires the "restrict the set of refinements to odd integers"; the strike sits "at the center of the tree" between two terminal nodes. QuantLib silently bumps even `steps` to `steps+1`. | B-309 sec. 4 [Read]; QuantLib `ql/methods/lattices/binomialtree.cpp` `LeisenReimer::LeisenReimer` [Read] |
| 4 | LR is suited to greeks | **Partly** | LR's benefit is a smooth price in S and sigma, which helps **bumped** greeks. [Own] Bump-gamma with h=0.05: LR n=101 range 0.025-0.030 (reference 0.0274); CRR range 0.00-0.94. Tree-**node** delta and gamma (Hull style) are about equally good for CRR and LR (section 4.4). QuantLib's own comment says tree greeks "are not overly accurate". | QuantLib `binomialengine.hpp` `\todo` note [Read]; [Own] |
| 5 | An "LR tree with discrete dividends" is a well-defined, standard method | **Partly / under-specified** | LR (1996) treats no dividends. QuantLib's `BinomialVanillaEngine` accepts one flat yield q read at maturity, no dividend schedule. QuantLib's discrete-dividend American pricer is the finite-difference `FdBlackScholesVanillaEngine` with a `DividendSchedule` and a choice of `Spot` or `Escrowed`. A recombining tree can only do escrowed (or proportional) dividends. | B-309 [Read]; QuantLib `binomialengine.hpp`, `fdblackscholesvanillaengine.hpp` [Read] |
| 6 | Escrowed (spot minus PV of dividends) is biased | **Confirmed** | QuantLib docs: Haug, Haug & Lewis argue the escrowed (Merton-73) scheme "underprices call options". Cosma et al.: escrow "does not properly integrate the early exercise premium... and tends to underprice". [Own] Escrowed is below the cash-drop reference in all 36 dividend cases: 0.2-8 cents (24 single-dividend cases), 0.25-1.3 dollars (12 quarterly cases), same vol input. HHL itself: [Cited], host unreachable. | QuantLib.js docs `FdDividendEngineMerton73` [Read]; Cosma, Galluccio, Pederzoli, Scaillet, arXiv:1612.03031, intro [Read]; Haug, Haug & Lewis, Wilmott 2003(9):37-47 [Cited]; [Own] |
| 7 | Cash dividends give a non-recombining tree; negative prices are possible | **Confirmed** | "The known dividend amount assumption does not lead to a recombining tree, and a new tree is originated at each node following an ex-dividend date." Piecewise lognormal "allows for negative stock prices, if a_i > S(t_i-)"; HHL define liquidator (floor at 0) and survivor policies. | Cosma et al. intro [Read]; Healy, arXiv:2106.12971, sec. 4.1 [Read] |
| 8 | Which discrete-dividend treatment is accurate for American early exercise | **Partly answerable** | Early exercise of a call is only optimal just before an ex-date (Merton 1973, via HHL) [Cited]. Cosma et al. show a wrong dividend treatment "leads to an incorrect exercise decision". The cash-drop (QuantLib `Spot`) model is the one HHL/Healy argue for. Healy's semi-analytic European basket price agrees with my FD reference to 6e-5 (section 4.1). No source shows which model the *market* uses; that is unknown. | Cosma et al. [Read]; QuantLib docs [Read]; [Own] |
| 9 | SPX, SPXW, XSP, NDX, RUT, VIX options are European | **Confirmed** | SPX: "European - SPX options generally may be exercised only on the expiration date." XSP: "European". VIX/VIXW: "European". MRUT: "European". RUT product page: "European-Style Exercise" and "AM or PM Settlement". NDX/NDXP: "The product would have European-style exercise" (Phlx rule filing, which also covers NDXP; it states NDX a.m.-settled third-Friday and that NDXP ceases at 4:00 pm). | Cboe spec pages [Read]; SEC Rel. 34-98644 (Phlx, 2023) [Read] |
| 10 | OEX is American, XEO European; SPY/QQQ/IWM American | **Confirmed (Cboe); OCC not opened** | OEX: "American - ... any business day up to and including on the expiration date". XEO: "European". Cboe site text: "stock and ETF options (American-style) can be exercised any time before expiration." Schwab chain rows in our captures show `exerciseType` `A` for equity and `E` for the VIX sample. OCC spec page returned HTTP 403. | Cboe OEX/XEO spec pages and Cboe index-options marketing text [Read]; `docs/schwab/observations.md` (own captures) [Read]; OCC [not opened] |
| 11 | AM versus PM settlement and time to expiry | **Confirmed** | SPX (standard): settles on opening sales prices of constituents, last trading day usually Thursday. SPXW: "cease on the day of expiration, 4:00 pm ET". XSP: settles on the official **closing** price. NDX standard a.m.; NDXP p.m. (closing value). VIX/VIXW: Special Opening Quotation (SOQ) of VIX, last trade the day before, 4:00 pm CT. OEX/XEO: closing prices. VIX methodology has separate settlement-day terms for AM-settled and PM-settled SPX. Cash settles the business day after expiration. | Cboe SPX/XSP/VIX/OEX/XEO spec pages [Read]; Cboe VIX Methodology, "M_Settlement day" definition [Read]; Phlx filing [Read] |
| 12 | BSM with a continuous dividend yield is right for index options | **Partly** | BSM is the right formula for European exercise. Cboe's own method derives the forward from parity: `F = Strike + e^(RT) x (Call - Put)` at the strike where the call-put difference is smallest, with a per-maturity Treasury rate. A spot-plus-q input is an estimate of that forward. [Own] with true q=1.3%, a model q of 1.0% or 1.6% makes call IV and put IV disagree by 0.4-1.2 vol points. | Cboe VIX Methodology, forward formula and "Risk-Free Interest Rates" [Read]; [Own] section 4.6 |
| 13 | VIX options are priced off spot VIX | **Wrong (if intended)** | Cboe's own margin text for VIX/VIXW options: "The price of the VIX futures contract with a corresponding expiration will be used to calculate theoretical gains and losses". Settlement is the SOQ, not spot. Valuation-point range is +/-20% under Cboe Rule 12.4. | Cboe VIX options spec page [Read] |
| 14 | "Schwab doesn't publish its rate, dividend treatment, or day count" | **Partly** | Published: "Charles Schwab uses the Black-Scholes model for European-style options, and the Bjerksund-Stensland for American-style options"; the thinkScript `OptionPrice(...)` takes **one** `yield` (default `GetYield()`) and **one** "global interest rate" (default `GetInterestRate()`); the IV study "is calculated using approximation method based on the Bjerksund-Stensland model". Not published: which rate, which 1993/2002 variant, day count. Observed in our captures: chain root `interestRate` ~4.04, `dividendYield`, per-contract `volatility`, integer `daysToExpiration`. | thinkorswim Learning Center: glossary "O", `OptionPrice`, `GetYield`, `GetInterestRate`, `ImpVolatility` [Read]; `observations.md` [Read] |
| 15 | So "its numbers can't be reproduced under a Shock" | **Unsupported** | A "Schwab mode" pricer (Black-Scholes / Bjerksund-Stensland with the payload's rate, yield, IV and DTE) is feasible and can be tested against `theoreticalOptionValue`. The accurate reason to own the model is different: 50 Positions x 100 Shocks cannot go through an API, and Hypothetical Trades and Simulated Portfolios have no quotes. Schwab's own `GET /chains` with `strategy=ANALYTICAL` "allows the use of volatility, underlyingPrice, interestRate, and daysToExpiration params to calculate theoreticalvalues" (spec text, read 2026-10-24), so Schwab itself exposes a what-if calculator with the four inputs a Shock changes. It has no dividend or day-count input, and its model is not named in the spec. See section 7. | Schwab Market Data OpenAPI spec, `/chains` `strategy` parameter [Read, section 7]; thinkorswim pages [Read] |
| 16 | thinkorswim's methodology is unpublished | **Partly** | Setup > Calculations offers volatility modes: individual applied IV, smile approximation, or fixed per expiration. The Analyze-tab theoretical-value help page was not found. The StreetSmart Edge defaults (13-week bill, trailing yield) in earlier notes are from a retired platform, not retrievable now. | thinkorswim Setup page [Read]; StreetSmart Edge help [Cited, unreachable] |
| 17 | One consistent model for base and shocked values is sound | **Partly** | Sound for isolating the effect of the Shock. But GLOSSARY defines Shock P/L "measured from its current market value". If base = market mid and shocked = model, the model-versus-market residual leaks into P/L. Fix: calibrate each contract's IV so the model reproduces its mid, then report model(shock) - model(base). Where no IV exists (section 4.5) carry the residual explicitly. | GLOSSARY.md [Read]; [Own] |
| 18 | Scenario vol: hold fixed / sticky-strike / sticky-delta / per-contract | **No single right answer** | Derman (1999): three rules (sticky-strike, sticky-delta, sticky-implied-tree), "none of these views are absolutely correct". Sticky-strike for a stable, range-bound market ("leave the implied volatility of every option unchanged"); sticky-delta for a trending index; sticky-implied-tree for a jumpy one. GLOSSARY's "IV Shift" (a change to each contract's own IV, independent of the SPY move) is sticky-strike plus a parallel shift. | Derman, GS Quantitative Strategies Research Notes, Jan 1999, "When To Use The Sticky-Strike / Sticky-Delta Rule" [Read] |
| 19 | How regulators specify shocks | **Confirmed (coarsely)** | FINRA Notice 07-11: ranges of -8%/+6% (high-cap broad index), +/-10% (other broad index), +/-15% (equities, narrow index); 10 equidistant valuation points; margin is the greatest loss; scenarios vary "both the underlying price and implied volatility inputs". Vol shock size not stated in what I read. OCC STANS and current Rule 4210(g) not opened. | FINRA Notice 07-11 [Read via fetch summary]; Rule 4210(g), OCC STANS [not opened] |
| 20 | "Differences vs thinkorswim: tens of cents near ex-dividend and on long-dated, high-vol options" | **Partly: plausible order of magnitude, wrong unit, unquantified** | [Own] Against a Black-Scholes-Stensland 1993 + flat-yield proxy for Schwab, price gaps at equal IV are about 0 (early dividend, near-the-money) to about 75 cents (20% vol, call 90, dividend on day 85 of 91), 25 cents (60% vol, 2y, ITM put, no dividend), and 30-40 cents (2y 60% quarterly). But IV and greeks are not in cents: IV gaps are 0.2-2.7 vol points. Both systems back IV out of the same market price, so price gaps at the *market* price are zero by construction. See section 4.5. | [Own] sections 4.2-4.5 |
| 21 | IV by root-finding on an American tree | **Works, with holes** | No root when mid is at or below intrinsic (bid below intrinsic is common deep ITM). Flat price-versus-vol (vega 0) for deep ITM calls just before an ex-date. See section 4.5. | [Own] |
| 22 | Implementation matches the ADR | **No implementation exists** | `src/`, `tests/`, `tools/` contain no pricing code. Only planning documents (issues 06, 14). Planned CLI diverges from the ADR in places; see section 5. | grep of repo [Read] |

## 3. Methodology assessment by instrument class

| Class | Examples | Exercise | Recommended model | Why |
| --- | --- | --- | --- | --- |
| American calls, no dividend, no borrow cost | IREN, CIFR, HOOD, ASTS calls | American, never exercised early (Merton 1973 [Cited]) | **Closed-form BSM** | Exact, fastest, smooth greeks. [Own] LR n=201 error vs FD on no-dividend calls: 0.01-0.02 cent, so no gain from a tree. |
| American puts, no dividend | any equity put | American | **LR tree, n about 201** (or FD) | LR max error 0.44 cent vs CRR(200) 3.9 cents, BAW 15 cents, BS93 24 cents at 60% vol, 2y [Own]. Bump vega/rho/theta are stable across n=101, 201, 501 (section 4.4). |
| American options on dividend payers, 1 dividend, <=3 months | SPY, ordinary stocks | American | **LR tree with escrowed dividends is acceptable; prefer FD with cash drop if the ex-date is late in life or vol is high** | Escrowed gap is 0.2-8 cents / 0.2-0.4 vol point [Own]. A flat-yield approximation is up to 77 cents off for late dividends and ITM calls [Own]. |
| American options on dividend payers, several dividends, or >1 year | LEAPS on SPY/QQQ/IWM | American | **FD (PDE) with cash drop at ex-dates** (QuantLib `Spot`), or a Vellekoop-Nieuwenhuis-style tree | Escrowed vs cash-drop gap grows to $0.25-1.3 and 0.8-2.7 vol points [Own]. Vellekoop-Nieuwenhuis (2006): "arbitrage-free", "simple and efficient"; abstract only [Read, abstract]; full text 403. |
| Hard-to-borrow or high-short-interest equities | many high-IV names | American | Same models, plus a **borrow rate input** | [Own] a 3% carry shifts a 1-year 60% ATM call by $1.9, 10 times the 46 bp rate difference. For HTB, calls can have early-exercise value even with no dividends (my reasoning, not sourced). |
| European cash index options, PM | SPXW, XSP, NDXP, XND, XEO, RUT/MRUT (PM series) | European | **Black-76 / BSM on parity-implied forward F(T)**, per-expiry discount rate, T to 4:00 pm ET | Cboe's method for the forward [Read]. Spot plus q is an estimate of F. |
| European cash index options, AM | SPX standard, NDX standard, RUT (AM series) | European | Same, with **T to 9:30 am ET on the settlement day** (last trade the previous day) | [Own] a 6.5-hour clock error at 1 calendar day to expiry is 2.6 vol points of IV, 1.2 at 2 days, 0.45 at 5 days. |
| VIX options | VIX, VIXW | European | **Black-76 on the VIX future of the same expiry**, T to the Wednesday SOQ | Cboe uses VIX futures for theoretical gains/losses [Read]. Spot VIX is not the forward. Vol-of-vol is large; flat-vol BSM is a rough tool (my judgement). |
| American-style index options | OEX | American | Tree/FD on the parity forward with q implied | Rare. Cash-settled on closing prices; early exercise matters for deep ITM. |
| Options on futures, FLEX, adjusted/non-100 deliverables | /ES options, post-corporate-action contracts | varies | Out of ADR scope. Read `deliverables`, `exerciseType`, `settlementType` per contract; do not infer from the ticker. | Schwab chain rows carry these fields (`observations.md`). |

Notes on the engine, from QuantLib source [Read]:

- The tree engine reads `riskFreeRate` and `dividendYield` once at maturity and builds a flat-rate lattice. A term structure of rates or a dividend schedule is ignored there.
- The FD engine takes a `DividendSchedule`, a `Spot` or `Escrowed` choice, and time/space grids.
- BAW (1987) and Bjerksund-Stensland (QuantLib implements the **1993** version) are closed-form approximations with no discrete dividends.

## 4. Quantitative results [Own computation]

Everything here is my own computation, not a cited source. Scripts live in the scratchpad (not in the repo):

- `/private/tmp/claude-501/-Users-ash-repositories-investor-basecamp/0bef4d2c-0140-4e1d-ab4f-205a2e5bd3af/scratchpad/tools/model_error.py`
- `/private/tmp/claude-501/-Users-ash-repositories-investor-basecamp/0bef4d2c-0140-4e1d-ab4f-205a2e5bd3af/scratchpad/tools/model_extra.py`

They run in a venv with `numpy`, `scipy` and `QuantLib` 1.44 (`venv/bin/python -I tools/model_error.py`). Setup: S=100, r=4.5% continuous, Actual/365, valuation date 2026-10-23, `$1` dividends.

### 4.1 Method and validation

- **Reference.** QuantLib `FdBlackScholesVanillaEngine`, `Spot` cash-dividend model (the price drops by D at the ex-date), 1600 time x 3200 space steps, Douglas scheme with 1 damping step. Doubling the grid moved results by at most 6e-4 (section 4.2 `refdiff` column). For a European option with eight $1 dividends, the same FD reproduces QuantLib's semi-analytic Healy basket price to 6e-5 (call 21.78154 vs 21.78148, put 20.82656 vs 20.82652; K=100, 2y, 40%). The reference is a model, not "truth": no source says the market uses it.
- **Own LR tree** matches QuantLib's `BinomialVanillaEngine("lr", 201)` to 1e-11 (7.479567123823 vs 7.479567123792, American put, no dividend).
- **Own escrowed tree.** The tree runs on S* = S - PV(dividends). Exercise is tested at S* + PV(dividends still pending), so exercise just before an ex-date sees the cum-dividend price. Core of the rollback:

```python
Sstar = S - sum(a*exp(-r*t) for t, a in divs)          # tree runs on S*
# LR: d1 = (ln(S*/K) + (r+s^2/2)T)/(s sqrt T); pbar = PP2(d1,n); p = PP2(d1 - s sqrt T, n)
#     u = e^{r dt} pbar/p;  d = (e^{r dt} - p u)/(1 - p);   PP2 = Peizer-Pratt method 2
for i in range(n-1, -1, -1):
    cont = disc*(p*V[1:] + (1-p)*V[:-1])
    ex   = max(sgn*(S_i + pending_PV(i*dt) - K), 0)    # exercise value uses cum-dividend price
    V    = max(cont, ex)
```

- **Competing methods.** "q-approx" = a flat yield q chosen to carry the same total cash over the option's life (annual yield of dividends/S/T), fed to LR(201), BAW and Bjerksund-Stensland 1993. The last of these is the best available proxy for Schwab's stated model; Schwab's real q, rate and variant are unknown.

### 4.2 No-dividend American options (16 cases: K in {85,100,115}, 20-60% vol, 91 days to 2 years)

Error in dollars per share versus the FD reference. Selected rows:

| Case | LR n=101 | LR n=201 | CRR n=200 | BAW | BS93 |
| --- | --- | --- | --- | --- | --- |
| 20% vol, 91d, put 100 | +0.0004 | +0.0002 | -0.0026 | -0.0079 | -0.0450 |
| 40% vol, 182d, put 115 | -0.0030 | -0.0012 | +0.0127 | -0.0677 | -0.0935 |
| 60% vol, 365d, put 115 | -0.0021 | -0.0006 | +0.0238 | -0.0189 | -0.1447 |
| 60% vol, 730d, put 100 | -0.0032 | -0.0010 | -0.0221 | +0.1539 | -0.1729 |
| 60% vol, 730d, put 115 | -0.0100 | -0.0044 | +0.0107 | +0.1215 | -0.2447 |
| 60% vol, 730d, call 100 (= European) | -0.0002 | -0.0001 | -0.0394 | 0 | 0 |
| **Max abs over 16 cases** | **0.0100** | **0.0044** | **0.0394** | **0.1539** | **0.2447** |

CRR at n=500: max 0.0158. BAW and BS93 are exact for no-dividend calls (they reduce to European), but BS93 is 17-24 cents low on 2-year 60%-vol ITM puts. This matches the ADR's choice of a tree over a closed form for puts. It does not show BSM is wrong for calls.

### 4.3 Discrete dividends: error vs cash-drop reference (dollars per share)

| Case (S=100) | LR esc. n=201 | FD escrowed (QL) | q-approx LR | q-approx BAW | q-approx BS93 |
| --- | --- | --- | --- | --- | --- |
| 1x$1, day 7, 20% vol, 91d, put 110 | -0.004 | -0.002 | -0.432 | -0.445 | -0.450 |
| 1x$1, day 50, 20% vol, 91d, call 90 | -0.014 | -0.012 | -0.294 | -0.292 | -0.304 |
| 1x$1, day 85, 20% vol, 91d, call 90 | -0.026 | -0.018 | -0.759 | -0.757 | -0.769 |
| 1x$1, day 85, 40% vol, 91d, call 100 | -0.080 | -0.075 | -0.393 | -0.390 | -0.399 |
| 1x$1, day 85, 40% vol, 91d, put 100 | -0.073 | -0.074 | -0.076 | -0.076 | -0.086 |
| quarterly $1, 40% vol, 1y, call 100 | -0.308 | -0.309 | -0.283 | -0.233 | -0.317 |
| quarterly $1, 60% vol, 2y, call 100 | -1.251 | -1.243 | -0.744 | -0.487 | -0.838 |
| quarterly $1, 60% vol, 2y, put 120 | -1.282 | -1.277 | -0.612 | -0.335 | -0.952 |
| **Max abs, 24 one-dividend cases** | 0.080 | 0.075 | 0.759 | 0.757 | 0.769 |
| **Max abs, 12 quarterly cases** | 1.282 | 1.277 | 0.792 | 0.531 | 0.973 |

What this shows:

- LR, CRR and QuantLib's own escrowed FD agree with each other within a few cents, and all sit below the cash-drop reference. The gap is therefore the **model definition**, not tree error. With escrowed, sigma applies to S minus PV of dividends, a smaller base, so the same sigma means less total variance than in the cash-drop model.
- European-only check (K=100, 2y, 40% vol, eight $1 dividends): cash-drop 21.78 vs escrowed 20.94, a gap of 0.84. About two thirds of the gap is already there with no early exercise; the rest is the early-exercise treatment.
- A flat yield is worst for a single dividend that lands in the life of an option, especially an ITM call with a late dividend. It is least bad for a dividend that is already spread through the life.
- These price gaps assume the **same sigma**. In practice IV is backed out from the market price, so see 4.5.

### 4.4 Convergence, greeks, stability

American put, S=K=100, 182 days, 30% vol, no dividend, reference 7.47918:

| n | LR error | CRR error | European call: LR error | CRR error |
| --- | --- | --- | --- | --- |
| 11 | -0.0038 | +0.1856 | -0.0030 | +0.1868 |
| 21 | +0.0007 | +0.0988 | -0.0009 | +0.0974 |
| 51 | +0.0006 | +0.0406 | -0.0002 | +0.0400 |
| 101 | +0.0006 | +0.0208 | -0.00004 | +0.0202 |
| 201 | +0.0004 | +0.0105 | -0.00001 | +0.0101 |
| 501 | +0.0003 | +0.0043 | 0 | +0.0041 |
| 1001 | +0.0002 | +0.0022 | 0 | +0.0020 |

LR's American error shrinks slowly (first order, as the paper says) but starts about 30 times lower. Gamma, American put, K=100, 91 days, 30% vol (FD-bump reference):

| S | Reference | LR101 node | CRR100 node | LR201 node | LR101 bump h=1 |
| --- | --- | --- | --- | --- | --- |
| 80 | 0.01814 | 0.01819 | 0.01764 | 0.01841 | 0.01838 |
| 100 | 0.02737 | 0.02750 | 0.02756 | 0.02743 | 0.02735 |
| 120 | 0.00885 | 0.00910 | 0.00884 | 0.00897 | 0.00885 |

With a small bump (h=0.05), LR n=101 gamma stays in 0.025-0.030, but CRR swings between 0.00 and 0.94 (lattice artefact). So the advantage of LR is for bumped greeks, not node greeks. Vega per vol point and theta per day with a dividend at day 60 (LR n=101/201/501 versus FD escrowed): vega 0.2743/0.2742/0.2742 vs 0.2742; theta -0.0178/-0.0178/-0.0179 vs -0.0178. Bumped vega and theta were stable already at n=101. Timing was not re-measured; `.scratch` issue 06 reports about 0.3 s for the grid at n=101 (single thread) [Cited].

### 4.5 IV fits and where Schwab-style numbers diverge

Setup: take the FD cash-drop price at sigma0 as "the market price", then let each model solve for its own IV and reprice a Shock (S -10% / +10%, 30 days forward). Errors are versus the cash-drop model at sigma0.

| Case | Market price | LR-escrowed IV | BS93 + q IV | BAW + q IV | Shocked-price error, LR-esc | BS93+q |
| --- | --- | --- | --- | --- | --- | --- |
| 1x$1 day 85, 91d, 40%, call 100 | 8.332 | 40.41 (+0.41) | 42.03 (+2.03) | 41.98 (+1.98) | +0.001 / +0.006 | +0.086 / -0.245 |
| 1x$1 day 50, 91d, 40%, put 100 | 7.942 | 40.22 (+0.22) | 40.61 (+0.61) | 40.56 (+0.56) | +0.008 / +0.015 | -0.098 / +0.048 |
| quarterly $1, 1y, 40%, call 100 | 15.821 | 40.83 (+0.83) | 40.84 (+0.84) | 40.61 (+0.61) | +0.004 / +0.037 | +0.040 / +0.057 |
| quarterly $1, 2y, 60%, call 100 | 31.978 | 62.66 (+2.66) | 61.75 (+1.75) | 61.00 (+1.00) | -0.030 / +0.143 | -0.050 / +0.181 |
| quarterly $1, 2y, 60%, put 100 | 31.292 | 62.65 (+2.65) | 62.05 (+2.05) | 61.09 (+1.09) | -0.043 / +0.136 | -0.039 / +0.062 |

(Shocked-price errors are for S -10% / S +10%, in dollars.) Read this together with the ADR's "tens of cents" line:

- At the same IV, price gaps between dividend treatments are tens of cents (section 4.3). At the same market price they are zero by construction, and the gap shows up as **IV (0.2-2.7 vol points)** and greeks.
- After per-contract IV calibration, repriced Shocks stay within 0.1-14 cents of the reference for LR-escrowed (4-25 cents for BS93 + flat q) even where the raw price gap is $1.25. So calibrating the IV recovers most of the accuracy, and "same model, calibrated IV" is a stronger argument for the ADR than "better dividend model".
- The raw model/IV gap matters when a user compares our IV to thinkorswim's: expect up to about 1-3 vol points on long, high-vol, dividend-paying options.

Other sources of difference from Schwab-style numbers, same-IV prices, European ATM call, 60% vol, no dividend:

| T | 4.04% vs 4.50% rate | 3% borrow-like carry |
| --- | --- | --- |
| 0.25y | $0.05 | -$0.43 |
| 1y | $0.18 | -$1.88 |
| 2y | $0.32 | -$4.02 |

Clock: Schwab's `daysToExpiration` is an integer with "no intraday fraction" (own captures); section 4.6 shows what that costs near expiry.

IV-solver edge cases, LR n=201:

- **No root below intrinsic.** American put S=100, K=120, 91 days: price is exactly 20.0000 at 1%, 5%, 10% and 20% vol, 21.40 at 40%, 32.29 at 100%. Any mid at or below 20 has no IV; a mid slightly above is ill-conditioned (vega near zero). A bid below intrinsic is common for deep ITM puts.
- **Flat price in vol.** American call S=100, K=70, $2 dividend in 5 days, 36 days to expiry: price is 30.0417 for every vol from 5% to 50%, 30.108 at 80%, 31.54 at 120%. The option is worth its exercise-just-before-ex-date value, so IV is not identified. Deep ITM calls just before ex-dividend should be flagged "no IV", not solved.

### 4.6 European index options

True q = 1.3%, S=6000, T=0.25, r=4.5%, vol 16%, prices generated with the true q:

| Strike | q used 1.0% | q used 1.6% |
| --- | --- | --- |
| 5400 | call IV 14.90, put IV 16.08 (gap -1.18) | call 16.94, put 15.92 (+1.02) |
| 6000 | call 15.79, put 16.17 (-0.38) | call 16.21, put 15.83 (+0.38) |
| 6600 | call 15.90, put 16.54 (-0.64) | call 16.10, put 15.42 (+0.67) |

The parity forward from ATM call and put prices recovers F (6048.193) and q (1.300%) exactly. Settlement clock: ATM call, 15% vol, an extra 6.5 hours of T: price off by 2.8, 1.9 and 1.2 index points at 1, 2 and 5 calendar days, which is 2.6, 1.2 and 0.45 vol points of IV.

## 5. Gaps, risks, and suggested ADR amendments

### 5.1 Omissions that matter for accuracy

| Topic | Why it matters | Support |
| --- | --- | --- |
| Borrow cost (hard-to-borrow) | Largest input error for many high-IV equities. Moves the forward like a dividend yield. Not in the REST specs; the Streamer documentation has `LEVELONE_EQUITIES` field 47 "Hard To Borrow Rate" with no stated unit (section 7.4). | [Own] 4.5; Schwab Streamer documentation [Read] |
| Dividend forecast | Schwab gives `divPayAmount`, `nextDivExDate`, `divFreq`; units were inferred from examples (earlier notes) and `divYield` is percent in our SPY capture. Later dividends must be projected; amount uncertainty dominates for >1y. | `observations.md` [Read] |
| Rate curve | Chain gives one flat `interestRate` (~4.04%, null per contract). A per-expiry Treasury curve (Cboe's VIX method [Read]) changes long-dated values by cents to tens of cents. Which tenor and basis Schwab uses is unknown. | [Own] 4.5 |
| Time convention | Integer DTE vs minutes to 4:00 pm ET (equity, PM) or 9:30 am ET (AM SPX). Calendar-minute time matches Cboe's own VIX convention. | Cboe VIX Methodology [Read] |
| Settlement | Cash settles T+1 for index options (Cboe pages [Read]). Equity T+1 settlement and OCC exercise cut-offs: not opened. | OCC [not opened] |
| Non-standard deliverables | Post-corporate-action options have deliverables other than 100 shares; the ADR does not say they are priced from `deliverables`. | `observations.md` shows the `deliverables` field |
| Weekly / 0DTE | PM-settled weeklies on SPXW, XSP, NDXP trade to 4:00 pm ET (SPXW 1:00 pm on half days [Read]). At <1 day, clock errors dominate (4.6). | Cboe SPX page [Read] |
| Smile dynamics | Not stated anywhere in the ADR or GLOSSARY beyond "IV Shift". | Derman [Read] |
| Hypotheticals | Base-versus-market residual (claim 17). | [Own] |
| Model risk | Both dividend models are assumptions; nothing in the primary literature I opened says which one the listed market quotes. | n/a |

### 5.2 Where planning documents diverge from the ADR

- **ADR says own IV; issue 14 uses Schwab's IV.** The planned `schwab option price` takes `--vol` defaulting to the chain contract IV. That feeds Schwab's IV into our model; the ADR title and text promise our own IV, solved from the market price by our model.
- **Rate.** Issue 06 recommended the Treasury curve; issue 14 uses the chain root `interestRate` (flat, source unknown).
- **Dividends.** ADR says discrete; issue 14 offers `--div-yield` (continuous) and "inferred from underlying quote". The phrase "LR tree with discrete dividends" appears in issue 14 and issue 06 ("drops discrete cash dividends") without saying escrowed or cash-drop.
- **Schwab-mode cross-check.** Issue 06 recommended a Schwab-mode pricer to validate plumbing; the ADR mentions only a tolerance.
- **Earlier "tens of cents" evidence.** It came from an escrowed lattice compared with a continuous yield, not from thinkorswim output.

### 5.3 Suggested ADR wording (do not edit the ADR from this file)

1. Replace "a Leisen-Reimer tree with discrete dividends for American options" with:
   > American options use a lattice or finite-difference solver in which each dividend is a cash drop at its ex-date. Calls on non-dividend payers with no borrow cost use closed-form Black-Scholes-Merton. A recombining Leisen-Reimer tree (odd steps, about 201) on spot minus the present value of dividends is acceptable for options with one dividend and under about 3 months, and is the fallback elsewhere; it prices below the cash-drop model.
2. Replace "Black-Scholes-Merton for European index options" with:
   > European index options (SPX, SPXW, XSP, NDX, NDXP, RUT, XEO) use Black-Scholes on the forward implied by put-call parity at each expiry, the settlement-time T (09:30 ET for AM-settled series, 16:00 ET for PM-settled), and the Treasury rate for that expiry. VIX options use Black-76 on the VIX future for that expiry.
3. Replace "Schwab doesn't publish its rate, dividend treatment, or day count, so its numbers can't be reproduced under a Shock" with:
   > Schwab names its models (Black-Scholes, Bjerksund-Stensland) but not its rate source, dividend treatment, variant or day count. We compute our own so that every Position and every Shock uses one set of inputs, including Hypothetical Trades that have no quote.
4. Add: **Shock P/L is model(shock) - model(base)**, where each contract's IV is solved so that model(base) equals its market mid. Where no IV exists (mid at or below intrinsic; deep ITM call just before an ex-date) flag the Position and carry the residual.
5. Add: **IV shift semantics**: say whether the IV Shift is sticky-strike (per-contract, current GLOSSARY wording) or tied to moneyness, and that large trending Shocks may need sticky-delta (Derman).
6. Replace the Consequences sentence with a unit-correct one:
   > Our IV will differ from thinkorswim's by 0.2 to 3 vol points on long-dated, high-vol, dividend-paying options and by up to about 25 cents of price at equal IV (no dividend, 60% vol, 2 years, ITM put) and up to about 75 cents (late dividend, ITM call) against a Bjerksund-Stensland 1993 proxy. This has not been measured against a live thinkorswim Analyze screen.
7. Add an explicit input list: borrow rate (default 0, flagged for hard-to-borrow), dividend schedule source and projection rule, rate curve source, time convention.

## 6. Sources

Opened and read by me ("Read"), then "not opened" or "seen only as cited".

### Read

| Source | URL | What I used it for |
| --- | --- | --- |
| Leisen & Reimer, "Binomial Models for Option Valuation: Examining and Improving Convergence", SFB 303 Discussion Paper B-309 (Univ. of Bonn, Mar 1995; the working-paper version of AMF 3(4):319-346, 1996). PDF was LZW-compressed; I decoded the text stream myself, so some formulas are garbled. | https://www.wiwi.uni-bonn.de/sfb303/papers/1995/b/bonnsfb309.pdf ; abstract page https://www.wiwi.uni-bonn.de/sfb303/papers/abstracts/bonnsfb309.html | Order of convergence, odd steps, American order one, no dividends |
| QuantLib source (lballabio, master, fetched 2026-10-23): `binomialengine.hpp`, `binomialtree.cpp`, `fdblackscholesvanillaengine.hpp/.cpp`, `cashdividendeuropeanengine.hpp`, `bjerksundstenslandengine.hpp`, `baroneadesiwhaleyengine.hpp`, `analyticdividendeuropeanengine.hpp` | https://github.com/lballabio/QuantLib | What each engine supports; BS version 1993; LR odd-step rule; tree-greek caveat |
| QuantLib.js docs for `FdDividendEngineMerton73` | https://quantlib.js.org/docs/classes/_ql_pricingengines_vanilla_fddividendengine_.fddividendenginemerton73.html | Statement that Haug, Haug & Lewis show Merton-73 underprices calls |
| Healy, "The Pricing of Vanilla Options with Cash Dividends as a Classic Vanilla Basket Option Problem", arXiv:2106.12971 (2021) | https://arxiv.org/abs/2106.12971 | Piecewise lognormal (cash-drop) model; negative prices; liquidator/survivor policies; HHL citation (Wilmott 2003, 9:37-47) |
| Cosma, Galluccio, Pederzoli, Scaillet, "Early exercise decision in American options with dividends, stochastic volatility and jumps", arXiv:1612.03031 (2016) | https://arxiv.org/abs/1612.03031 | Escrowed bias; cash dividends not recombining; wrong dividend model gives wrong exercise decision |
| Derman, "Regimes of Volatility", Goldman Sachs Quantitative Strategies Research Notes (Jan 1999). Hosted copy (course reading list). | https://hpirotte.ulb.be/INGESTriskmgt/readings/Derman%20(1999)%20-%20Volatility%20regimes.pdf | Sticky-strike / sticky-delta / sticky-implied-tree |
| Cboe SPX options specifications | https://www.cboe.com/tradable-products/sp-500/spx-options/spx-specifications | SPX European, AM, opening prices, T+1 cash; SPXW 4:00 pm |
| Cboe XSP, VIX/VIXW, OEX, XEO, MRUT specifications | https://www.cboe.com/tradable-products/sp-500/xsp-options/specifications ; https://www.cboe.com/tradable-products/vix/vix-options/specifications ; https://www.cboe.com/tradable-products/sp-100/sp-100-index-options/oex-specifications ; https://www.cboe.com/tradable-products/sp-100/sp-100-index-options/xeo-specifications ; https://www.cboe.com/tradable-products/ftse-russell/mini-russell-2000-index-options/mrut-specifications | Exercise style, settlement value, last trading day, VIX futures use in margin, +/-20% |
| Cboe Russell 2000 (RUT) product page | https://www.cboe.com/tradable-products/ftse-russell/russell-2000-index-options | "European-Style Exercise", "AM or PM Settlement" (no spec table on the page) |
| Cboe VIX Methodology | https://cdn.cboe.com/resources/vix/VIX_Methodology.pdf | Parity-implied forward; Treasury rate per maturity; minutes/525,600 |
| Nasdaq PHLX rule filing, SEC Release 34-98644 (2023), p.m.-settled Nasdaq-100 options | https://www.sec.gov/rules/sro/phlx/2023/34-98644.pdf | NDX/NDXP European style; a.m. vs p.m. |
| FINRA Regulatory Notice 07-11 (portfolio margin) | https://www.finra.org/rules-guidance/notices/07-11 | Shock ranges, 10 valuation points, IV varied |
| thinkorswim Learning Center: glossary "O", `OptionPrice`, `GetYield`, `GetInterestRate`, `ImpVolatility`, `TheoreticalOptionPrice`, `OptionTheta`, Setup | https://toslc.thinkorswim.com/center/Glossary/O ; https://toslc.thinkorswim.com/center/reference/thinkScript/Functions/Option-Related/OptionPrice ; https://toslc.thinkorswim.com/center/reference/thinkScript/Functions/Others/GetYield ; https://toslc.thinkorswim.com/center/reference/thinkScript/Functions/Others/GetInterestRate ; https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/G-L/ImpVolatility ; https://toslc.thinkorswim.com/center/howToTos/thinkManual/Getting-Started/thinkorswim-Setup | Named models; single yield and global rate; volatility modes |
| Repo files: `docs/adr/0001-own-pricing-model.md`, `GLOSSARY.md`, `docs/schwab/observations.md`, `docs/schwab/external-market-data.md`, `.scratch/.../06-...md`, `.../14-...md` | local | ADR text, Schwab captures, planned CLI |
| Earlier internal research `docs/research/pricing-models-and-inputs.md` on branch `research/pricing-models-and-inputs` (commit 84eae1f, never merged) | local git | Starting point; I re-checked what I could and did not rely on its numbers |

### Secondary (labelled)

- schwab-py client docs, https://schwab-py.readthedocs.io/en/latest/client.html : `get_option_chain` ANALYTICAL strategy parameters. No dividend parameter listed; no response-field definitions.
- docs.rs `schwab_api` option-chain model, https://docs.rs/schwab_api/latest/src/schwab_api/model/market_data/option_chain.rs.html : field names only, no descriptions.

### Not opened (host unreachable, login-gated, paywalled, or HTTP 403)

| Source | Status |
| --- | --- |
| Haug, Haug & Lewis (2003), "Back to Basics: a new approach to the discrete dividend problem", Wilmott 2003(9):37-47 | Preprint host (nccr-finrisk.uzh.ch) did not resolve. Claims about it come from QuantLib docs, Healy, and the earlier internal note. |
| Vellekoop & Nieuwenhuis (2006), AMF 13(3):265-284 | Abstract only (Twente portal, RePEc); full-text PDF returned 403. Method described via Cosma et al. |
| Black & Scholes (1973) JPE 81(3); Merton (1973) Bell J. 4(1); Cox, Ross & Rubinstein (1979) JFE 7(3); Barone-Adesi & Whaley (1987) JF 42(2); Bjerksund & Stensland (1993, 2002 NHH DP 2002:9); Longstaff & Schwartz (2001) RFS 14(1); Broadie & Detemple (1996) RFS 9(4) | Not opened. Bibliographic details are from memory. Merton's "never exercise a non-dividend call early" is textbook, not read here. |
| OCC product specifications, Characteristics and Risks (ch. III on dividends), cash-dividend adjustment guidance, STANS | HTTP 403 from OCC hosts. Rule "no adjustment for ordinary cash dividends" is **Cited** from the earlier internal note only. |
| Schwab developer portal login | The first attempt on 2026-10-24 failed on an expired session; the "Documentation" tabs were read after reconnecting (section 7.4). |
| FINRA Rule 4210(g) current text; Cboe Rule 12.4; Cboe/NDX fact sheets | Not opened. |
| thinkorswim Analyze-tab help on Option Theoreticals | Not found. |

### Claims I could not source

- Schwab's rate source and tenor, Bjerksund-Stensland 1993 vs 2002, day count, and whether `theoreticalOptionValue` uses contract IV or a smoothed IV. The OpenAPI specs (section 7) define none of these: `interestRate`, `volatility`, `theoreticalVolatility` and `daysToExpiration` have a type and no description.
- Which dividend model, if any, the listed market quotes.
- Whether thinkorswim models discrete dividends anywhere.
- The "ten times faster" LR claim (not in the working paper).
- Sizes of the volatility shocks in OCC STANS and FINRA 4210(g).
- Real-time performance of a PDE solver in the browser (not measured).

## 7. Schwab OpenAPI specifications (primary, read 2026-10-24)

Source: the Schwab Developer Portal, product "Trader API - Individual", read from a logged-in browser tab. The portal serves each specification as JSON; I saved the `specification` field of each response (nothing else) into the repo:

- [market-data-production.openapi.json](../schwab/api-specs/market-data-production.openapi.json): "Market Data" 1.0.0, OAS 3, source file `TraderApi-MDIS-03-21-2024(4).json`. 10 paths, 57 schemas.
- [trader-api-production.openapi.json](../schwab/api-specs/trader-api-production.openapi.json): "Trader API - Account Access and User Preferences", OAS 3.0.1, source file `TraderApi-Prod_05-11-2024.yaml`. 10 paths, 84 schemas.

The portal response also carried credential-like fields (`appKey`, `appSecret`). I did not save them; the saved files contain neither.

The prose "Documentation" tab of each API is saved too: [market-data-documentation.md](../schwab/api-specs/market-data-documentation.md) (the Schwab Streamer API guide, 34 tables) and [trader-api-documentation.md](../schwab/api-specs/trader-api-documentation.md) (OAuth flow and order samples). Their pricing-relevant content is in section 7.4.

### 7.1 What the spec defines and what it leaves out

| Question | What the spec says | Consequence for the ADR |
| --- | --- | --- |
| Which model produces `delta`, `gamma`, `theta`, `vega`, `rho`, `theoreticalOptionValue`? | Fields are typed `number` with examples. `QuoteOption.theoreticalOptionValue`: "Theoretical option Value". No model name anywhere (0 matches for binomial, Black-Scholes). The model names come from thinkorswim docs (section 2, row 14). | The ADR's "doesn't publish" is true of the API spec. It is not true of the thinkorswim documentation. |
| What do `interestRate`, `volatility`, `theoreticalVolatility`, `daysToExpiration` mean? | `OptionChain.interestRate`, `OptionChain.volatility`, `OptionContract.volatility`, `OptionContract.theoreticalVolatility`: `type: number, format: double`, no description. `OptionContract.daysToExpiration`: `number`, no description. 0 matches for "day count". | Rate source, tenor, and day count are undocumented, as the ADR says. Observed units (percent, e.g. `4.043`) come from our own captures (`observations.md`), not the spec. |
| Is there a dividend input or output on the option chain? | No. `OptionChain` has no dividend field, and `OptionContract` has none. The `dividendYield` we observed at the chain root in captures is **not in the spec**. | Do not build on `dividendYield` as a documented field. Take dividends from `/quotes` fundamentals instead (next row). |
| Can the app get dividend inputs for its own model? | Yes. `Fundamental` has `divAmount`, `divYield`, `divExDate`, `nextDivExDate`, `divPayAmount`, `divPayDate`, `nextDivPayDate`, `divFreq` (`DivFreq`: 1 annual, 2 semi-annual, 4 quarterly, ...). `FundamentalInst` has `dividendAmount`, `dividendYield`, `dividendDate`, `nextDividendDate`, `dividendFreq`, `divGrowthRate3Year`. | Supports the ADR's "discrete dividends" with an ex-date and amount, for the next dividend. Later dividends still have to be projected (section 5). Whether `divYield` is percent or fraction is not stated; `observations.md` inferred percent. |
| Can the app tell American from European per contract? | Yes. `ReferenceOption.exerciseType` is the `ExerciseType` enum `A`/`E` ("option contract exercise type America or European"). `ReferenceOption` also has `settlementType` (`A` = AM, `P` = PM: "option contract settlement type AM or PM"), `deliverables`, `multiplier`, `lastTradingDay`, `expirationType` (`M`, `Q`, `S`, `W`). `OptionContract` carries `settlementType`, `expirationType`, `isIndexOption`, `multiplier`, `optionDeliverablesList`. | Choose the model from the per-contract `exerciseType`, not from "index vs equity". Use `settlementType` to set the expiry clock and `deliverables` to detect non-standard contracts. `exerciseType` is on the reference block of `/quotes`; the chain contract schema has no `exerciseType` field (verify against a live chain). |
| Is there a what-if calculator? | Yes. `GET /chains` parameter `strategy`: "Default is SINGLE. ANALYTICAL allows the use of volatility, underlyingPrice, interestRate, and daysToExpiration params to calculate theoretical values." Each of those four parameters is described as "... to use in calculations. Applies only to ANALYTICAL strategy chains". The response echoes `volatility`, `underlyingPrice`, `interestRate`, `daysToExpiration` at the chain root. | Schwab can reprice a chain under a Shock to spot, vol, rate and time. It cannot take a dividend or a per-contract IV override, so it cannot reproduce a per-contract IV surface shift. This is a **possible cross-check source** for the ADR's "Schwab values kept as a cross-check", at one API call per scenario, which is why it does not replace an own model. **Tested 2026-10-24 (SPY, Saturday snapshot; verdict and script on branch `prototype/schwab-analytical-chain`, `tools/schwab/prototype/ANALYTICAL_CHAIN_VERDICT.md`):** overrides work only when the request covers one expiration, are silently ignored otherwise, bypass `strike`/`strikeCount`, and make every contract's IV one flat number. The theoretical looks American-style with a continuous yield near 0.98%. |
| Is there anything on borrow cost? | Not in either REST spec. **It is in the Streamer documentation** (7.4): `LEVELONE_EQUITIES` field 47 "Hard To Borrow Rate" (double, "valid range = -99,999.999 to +99,999.999", no unit stated), plus field 46 "Hard to Borrow Quantity", field 48 "Hard to Borrow" (flag) and field 49 "shortable". | Borrow cost can be fed to the pricer for equities, but only over the WebSocket stream, and the unit (percent? basis points?) is not stated. Correct the earlier statement in section 5 that no Schwab field carries it. |
| Position-side data | Trader API `AccountOption`: `optionDeliverables`, `putCall`, `optionMultiplier`, `type`, `underlyingSymbol`. No `exerciseType`, `expiration`, `strikePrice` in the schema as listed (those come from the symbol or from market data). | The position feed gives the OCC symbol; look up exercise style and settlement through market data, not the position. |

### 7.2 Effect on the verdicts in section 2

- **Row 14** ("Schwab doesn't publish its rate, dividend treatment, or day count"): **upgrade to Confirmed for the API specification**, with the caveat that thinkorswim documentation names the models. The spec has no dividend input or output on the chain, no rate-source text, no day-count text.
- **Row 15** ("can't be reproduced under a Shock"): still **Unsupported as worded**, now with a second counter-example. Schwab's own ANALYTICAL strategy shows Schwab itself treats spot, vol, rate and time as the Shock variables. The real reason to own the model is that the ANALYTICAL call is remote, per-chain, has no dividend or per-contract IV input, and does not apply to Hypothetical Trades or Simulated Portfolios.
- **Issue 14 and the ADR**: the spec confirms Schwab's chain `volatility` is a per-contract number with no definition. Feeding it into our model (issue 14) mixes Schwab's unknown model assumptions into ours.

### 7.3 Open items for a human

- Decide whether the app will use the Streamer (WebSocket) for `Hard To Borrow Rate`; the REST API does not expose it. Check the unit against a hard-to-borrow ticker.
- Re-run the ANALYTICAL prototype during market hours (the first run was a Saturday snapshot) and on an index (SPX/XSP). In the first run, Schwab's no-override `theoreticalOptionValue` could not be reproduced from its displayed IV, rate and days (about $0.95 low on a 27-day SPY call).
- Add `ReferenceOption.exerciseType` to the model-dispatch rule and confirm whether `/chains` rows expose it (the earlier note says our captures show `exerciseType` on chain rows; the spec schema for `OptionContract` does not list it).

### 7.4 What the two "Documentation" tabs add

Read 2026-10-24 after the portal session was renewed.

| Page | Pricing-relevant content | What it does not say |
| --- | --- | --- |
| Market Data Production: "Schwab Streamer API" ([saved](../schwab/api-specs/market-data-documentation.md)) | `LEVELONE_OPTIONS` fields: 10 Volatility ("Option Risk/Volatility Measurement/Implied"; "Volatility is reset to 0 at 3:30am ET"), 27 Days to Expiration (int), 28-32 Delta, Gamma, Theta, Vega, Rho, 34 Theoretical Option Value, 35 Underlying Price, 43 Settlement Type, 47 Implied Yield. `LEVELONE_EQUITIES` fields: 22 Annual Dividend Amount, 23 Dividend Yield, 26 Dividend Date, 46 Hard to Borrow Quantity, 47 Hard To Borrow Rate, 48 Hard to Borrow, 49 shortable. | Description column is empty for Delta, Gamma, Theta, Vega, Rho, Theoretical Option Value and Implied Yield. No model, rate, dividend treatment, day count or unit is stated for any of them. |
| Accounts and Trading Production ([saved](../schwab/api-specs/trader-api-documentation.md)) | OAuth three-legged flow, token lifetimes (the page says a refresh token expires after 7 days), order samples. Options symbology: "Underlying Symbol (6 characters including spaces) \| Expiration (6 characters) \| Call/Put (1 character) \| Strike Price (5+3=8 characters)". | Nothing on valuation, Greeks, or exercise style. |

Effects on the verdicts:

- **Row 14 stands.** Neither Documentation tab defines the model, rate or day count behind Schwab's IV, Greeks or theoretical values. The portal documents *that* the numbers exist, not *how* they are made.
- **One operational detail for the cross-check.** Streamer option `Volatility` is reset to 0 at 3:30am ET, so a cross-check that reads it before the first quote of the day will see zeros, not a model difference. Treat 0 as missing.
- **Order entry is out of scope** for this ADR (see ADR 0004, no order-placing code); the order samples were saved only because they are on the same page.
