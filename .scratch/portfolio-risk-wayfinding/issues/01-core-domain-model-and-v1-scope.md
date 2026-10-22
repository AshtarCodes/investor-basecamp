# Core domain model and v1 scope

Type: grilling
Status: resolved

## Question

What are the Portfolios, Positions, Scenarios, and Loss Thresholds in v1, where do holdings come from, and what is v1 deliberately leaving out?

## Answer

Settled across three grilling rounds on 2026-10-17. Terms are defined in `GLOSSARY.md`.

**Who and what**

- Single user (you), behind Better Auth sign-in, with every row scoped by user id.
- Broker is Schwab. Several Accounts are supported; Scenarios run per Portfolio.
- Instruments in v1: equities, ETFs, and equity and index options. You hold no futures, futures options, or mutual funds. Any asset type the API reports that v1 can't price is listed on the Portfolio page, never silently dropped.

**Where holdings come from**

- Accounts sync from the Schwab Trader API: on demand, and automatically on open when the last sync is older than 15 minutes. A sync writes a new Snapshot only when holdings change (quantity or Total Cost); otherwise it updates "last synced at". Snapshot history is kept.
- Screenshot import stays as an alternate source, but it only ever creates a Simulated Portfolio or replaces one's Positions, after a review-and-edit step. It never writes into an Account. Extraction is an OpenAI vision model ("GPT-6 Luna"), returning structured JSON with cross-checks. Ships in v1.
- Simulated Portfolios start empty, as a copy of another Portfolio, or from a screenshot. A copy is independent from then on. Each has its own cash. A Position added by hand defaults its Total Cost to the current mark times quantity times multiplier, so its P/L starts at zero; you can edit it.
- Hypothetical Trades exist only in Simulated Portfolios. There is no temporary overlay on an Account.

**Metrics**

- Per Position: instrument, quantity, Total Cost, market value, total P/L (market value − Total Cost), greeks for options, IV, HV, beta.
- Grouped by Underlying with subtotals. Strategy detection is on the roadmap, not v1.
- Net Liquidation Value and cash come from Schwab balances for Accounts, and from the screenshot (editable at review) or user entry for Simulated Portfolios.
- IV, greeks, and HV are computed by our own pricing model, so Scenario repricing stays consistent. Schwab's values are a cross-check.

**Scenarios**

- Deterministic grids: SPY move (percent) by IV shift (vol points), plus days forward. No Monte Carlo in v1.
- Beta-weighted to SPY, with a per-Underlying override.
- A Scenario belongs to one Portfolio. Copying a Portfolio copies its Scenarios; any single Scenario can be copied to another Portfolio.
- A Compare view runs one Scenario on two Portfolios and shows both grids and the difference. This is how you judge a hedge: copy the Account to a Simulated Portfolio, add the Hypothetical Trade, compare.

**Loss Thresholds**

- A risk budget, not an exit rule: you act on it before the market moves (size, hedge, trim).
- Optional per Portfolio (dollars or percent of Net Liquidation Value) and optional per Underlying. Never per Leg, because one Leg of a hedged spread would breach constantly.
- Checked against every Shock of every Scenario the Portfolio owns. Breaching Shocks are highlighted, and the Portfolio page shows worst Scenario loss against the budget.

**When Schwab disconnects**

- The refresh token lasts 7 days. After it lapses the app shows the last Snapshot and market data with a "data as of" banner and a Reconnect button. Scenarios still run on the frozen inputs, labeled with that time.

**Roadmap (beyond v1)**

- v2: an agentic flow that analyzes historical data and proposes hold, add, and trim rules you tune with a prompt.
- Strategy detection; Monte Carlo and VaR; correlated shocks and volatility skew; a combined view across Accounts; futures, futures options, and mutual funds.
