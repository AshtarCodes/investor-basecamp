# Scenarios

Per-stock baselines and assumptions for what-if runs of `pnpm schwab option price` (buy decisions on LEAPS and LEAP spreads). One folder per stock:

| File | What it holds |
| --- | --- |
| `<TICKER>/observations.md` | Dated facts measured from data: price regimes, volatility, how the stock behaves against the VIX, what the tool showed. Append new dated sections; do not rewrite history. |
| `<TICKER>/iv-rules.md` | The proposed implied-volatility rules for scenarios, versioned. Rules change as evidence arrives; each rule says what it rests on and what would change it. |
| `<TICKER>/thesis.md` | The owner's own bear/base/bull valuation view, versioned and reviewed quarterly. A view, not measured data; future discussions of the stock start from it. |
| `<TICKER>/data/` | The raw series the observations come from, so a number can be checked. |
| `<TICKER>/analysis/` | Scripts that regenerate the observations from `data/` (standard library only). |

Conventions
- Every P/L quoted in a scenario also states its percent return and the cost basis it is a percent of.
- Prices come from the Schwab API (`/pricehistory`, `schwab option price`); an observation names its source and date.
- A rule is an assumption until `observations.md` has data for it. Say which.

Stocks: [IREN](iren/observations.md)
