# Compute IV and greeks with our own pricing model

Schwab returns IV, greeks, and theoretical values for every contract, but we compute our own. Scenarios reprice every Position under Shocks, and that only makes sense if the base values and the shocked values come from the same model with the same inputs, including Hypothetical Trades that have no quote. Schwab names its models (Black-Scholes for European-style options, Bjerksund-Stensland for American-style) in the thinkorswim documentation, but not its rate source, dividend treatment, variant, or day count, and its API specification defines none of those fields. We use our own so every Position and every Shock runs on one set of inputs.

## Models

The model is chosen per contract from Schwab's `exerciseType`, not from whether the Underlying is an index.

American options use a lattice or finite-difference solver in which each dividend is a cash drop at its ex-date. Calls on non-dividend payers with no borrow cost use closed-form Black-Scholes-Merton, because early exercise is never optimal. A recombining Leisen-Reimer tree (odd step count, about 201) on spot minus the present value of dividends is acceptable for an option with one dividend and under about 3 months to expiry, and is the fallback elsewhere. It prices below the cash-drop model.

European index options (SPX, SPXW, XSP, NDX, NDXP, RUT, XEO) use Black-Scholes on the forward implied by put-call parity at each expiry, not spot with a continuous yield. Time to expiry runs to the settlement time: 09:30 ET for AM-settled series, 16:00 ET for PM-settled. The rate is the Treasury rate for that expiry. VIX options use Black-76 on the VIX future for that expiry.

## Inputs

Every price names its inputs: a borrow rate (default 0, flagged for hard-to-borrow equities), a dividend schedule with its source and projection rule, a rate curve with its source, and a time convention. Dividends beyond the next one are projected, and the projection rule is part of the input.

## Shock P/L

Shock P/L is model(shock) minus model(base). Each contract's IV is solved so that model(base) equals its market mid. Where no IV exists (the mid is at or below intrinsic, or a deep in-the-money call sits just before an ex-date), the Position is flagged and the residual is carried unchanged.

An IV Shift is sticky-strike: it moves each contract's own IV, as the glossary defines it. Large trending Shocks may need a sticky-delta shift, where the shift follows moneyness.

## Consequences

Our IV and greeks differ from what thinkorswim shows. The expected gap is 0.2 to 3 vol points of IV on long-dated, high-volatility, dividend-paying options, and up to about 25 cents of price at equal IV (no dividend, 60% volatility, 2 years, in-the-money put) or about 75 cents (late dividend, in-the-money call) against a Bjerksund-Stensland 1993 proxy for Schwab. That estimate is our own computation and has not been measured against a live thinkorswim screen. Schwab's values are kept as a cross-check with a tolerance, not as the source of truth. Don't "fix" the difference by switching to Schwab's values, and don't feed Schwab's IV into our model.

## Assumptions

These are not stated as fact. The behavior beside them is kept because it is safe either way.

- The listed market quotes a cash-drop dividend model. No primary source we read says which dividend model the market uses.
- Schwab's `volatility` and `theoreticalOptionValue` come from the models thinkorswim names. The API specification does not say so.

Evidence and sources: `docs/research/pricing-model-adr-0001-fact-check.md`.
