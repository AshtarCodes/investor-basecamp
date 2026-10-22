# Compute IV and greeks with our own pricing model

Schwab returns IV, greeks, and theoretical values for every contract, but we compute our own: a Leisen-Reimer tree with discrete dividends for American options, and Black-Scholes-Merton for European index options. Scenarios reprice every Position under Shocks, and that only makes sense if the base values and the shocked values come from the same model with the same inputs. Schwab doesn't publish its rate, dividend treatment, or day count, so its numbers can't be reproduced under a Shock.

## Consequences

Our IV and greeks differ from what thinkorswim shows, by tens of cents near ex-dividend dates and on long-dated, high-volatility options. Schwab's values are kept as a cross-check with a tolerance, not as the source of truth. Don't "fix" the difference by switching to Schwab's values.
