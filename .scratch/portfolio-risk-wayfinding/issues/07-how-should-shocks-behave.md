# How should Shocks behave?

Type: grilling
Status: resolved
Blocked by: 06

## Question

Pin down exactly what a Scenario does to each Position:

- **IV shift:** the same vol points for every Underlying (+10 points on a 15-IV ETF and on an 80-IV stock), or scaled by each Underlying's own IV or beta?
- **Linking IV to price:** should Scenarios offer a preset where IV rises as SPY falls, or are the two axes always independent?
- **Days forward:** calendar or trading days. What happens to a Position that expires inside the horizon (settled at intrinsic value, then held as shares or cash)?
- **Beta:** the lookback window, how often it refreshes, what an index option (SPX, XSP, NDX) uses, and how an override is expressed (a different beta, or a fixed percent move).
- **Defaults:** the grid a new Scenario starts with (SPY moves, IV shifts, days forward), and whether a new Portfolio gets any starter Scenarios.

## Answer

Settled across two grilling rounds on 2026-10-18. Terms are defined in `GLOSSARY.md`. The default IV range and mode may be revised by [Can historical data calibrate and back-test Shocks?](12-can-historical-data-calibrate-shocks.md). Everything else here holds regardless of what that finds.

**What a Shock starts from**

- Every contract starts from its live Schwab mark, and our model backs out that contract's own IV. At the Shock with no moves and days forward 0, every Position is worth its current market value.
- If the model can't solve an IV from the mark (a mark below intrinsic, or a wide, stale market), it uses Schwab's IV for that contract and flags it. This is the only place a Schwab value goes into our pricing.
  - *2026-10-25: not what was built.* The worker ([18](18-engine-worker.md)) carries the residual instead, as [ADR 0001](../../../docs/adr/0001-own-pricing-model.md) says. The Schwab-IV fallback is kept below as an unimplemented option; see the 2026-10-25 comment.

**IV Shift**

- One axis of the grid. It's applied to each option contract's own IV and is independent of the SPY move. There's no linked "IV rises as SPY falls" preset; correlated moves are on the roadmap.
- The mode is a setting. **Absolute** (the default) adds vol points. **Proportional** scales each contract's IV by a percent and suits high-IV stock picks like IREN, CIFR, and ASST. Shifted IV never goes below 1 vol point. Column headers always show the unit ("+10 pts" or "+25%").

**Price moves**

- Beta-weighted Move = beta × SPY move, clamped at −99% and flagged when clamped.
- Beta is a regression of the Underlying's returns against SPY, from Schwab price history, recomputed once per trading day. Lookback is a setting with three presets: daily over 1 year (the default), weekly over 2 years, monthly over 5 years. Below the preset's minimum history (60 days, 52 weeks, or 36 months), fall back to the daily preset, then to 1.0, flagged.
- SPX and XSP have a beta of exactly 1.0. NDX, RUT, and other indexes are computed from their own history, with QQQ and IWM as proxies if Schwab doesn't serve index history.
- A beta override replaces one Underlying's beta inside one Scenario. It's never a fixed percent move and never set on a Portfolio.
- SPY is the only benchmark in v1. Bitcoin-driven risk on the miners is handled only by an override.

**Days forward**

- Calendar days. A Scenario has exactly one value; copy the Scenario to compare horizons. Counted from the market data's "as of" time, so frozen data after a Schwab disconnect stays consistent.
- An option expiring inside the horizon is valued at intrinsic at the shocked price, whether it's physically or cash-settled, and flagged "expires within horizon". Early assignment isn't modeled.
- Held fixed: the Treasury curve, each dividend's cash amount and ex-date, and the Portfolio's cash. A dividend going ex inside the horizon drops out of option pricing, but no dividend cash is credited or debited.

**Shock P/L**

- Measured from current market value by default. A setting (global or per Portfolio) shows it from Total Cost instead. That toggle only changes the display: Loss Thresholds are always checked against the change from current market value.

**Settings**

- Each setting declares which scopes it allows: global, per Portfolio, per Underlying. Beta lookback and IV shift mode allow all three. The P/L baseline allows global and per Portfolio only.
- A per-Underlying setting applies to that Underlying in every Portfolio. The most specific setting wins: Scenario beta override, then Underlying, then Portfolio, then global.
- Compare reads settings from the Portfolio that owns the Scenario, applies them to both sides, and shows a note saying so.

**Defaults**

- Grid: SPY −20, −15, −10, −7.5, −5, −2.5, 0, +2.5, +5, +10, +15% by IV −10, −5, 0, +5, +10, +20 points, at days forward 0 (66 Shocks). The default proportional axis is −50, −25, 0, +25, +50, +100%.
- At most 200 Shocks per Scenario, roughly 0.6 to 1.8 seconds for about 50 Positions by the pricing research's timings.
- A Portfolio created empty or from a screenshot gets one starter Scenario, "Market shock", with the default grid. An Account gets it on first sync. A copied Portfolio copies its source's Scenarios instead.

## Comments

**2026-10-18, grilling round 1 (in progress, not the answer):**

- Agreed: IV shift is absolute vol points on each contract's own IV, floored at 1 point ("for now": the effect on high-IV stock picks like IREN, CIFR, and ASST is being examined). SPY move and IV shift stay independent. Days forward is calendar days, one value per Scenario, counted from the market data's "as of" time. Options expiring inside the horizon settle at intrinsic at the shocked price, flagged, with no early assignment. Rate curve, dividend schedule, and cash are held fixed, and no dividend cash is credited. SPX and XSP have beta 1.0; NDX and RUT are computed, with QQQ and IWM as proxies. A beta override is a beta, per Scenario per Underlying. Beta-weighted Moves are clamped at −99%, flagged. An unsolvable IV falls back to Schwab's IV, flagged.
- Agreed with a toggle: Scenario P/L is measured from current market value by default, with Total Cost as the alternative.
- Agreed with a setting: beta is a regression on 1 year of daily returns against SPY by default, recomputed daily, with beta 1.0 under 60 trading days. Weekly and monthly are the alternatives. Most settings can be scoped globally, per Portfolio, or per Underlying.

**2026-10-18, grilling round 2 (all agreed):**

- Compare reads its settings from the Portfolio that owns the Scenario and applies them to both sides, with a note. Per-Underlying settings apply to that Underlying in every Portfolio. The most specific setting wins: Scenario beta override, then Underlying, then Portfolio, then global. Each setting declares its allowed scopes; the P/L baseline is global or per Portfolio only.
- The P/L baseline toggle is display-only. Loss Thresholds are always checked against the change from current market value.
- Beta lookback presets: daily over 1 year (default), weekly over 2 years, monthly over 5 years. Minimum history is 60 days, 52 weeks, or 36 months. Below that, fall back to daily, then to 1.0, flagged.
- IV shift mode is a setting: absolute points (default) or proportional. The default proportional axis is −50, −25, 0, +25, +50, and +100%. Headers always show the unit.
- No benchmark other than SPY in v1. Bitcoin-driven risk is handled by a beta override; other benchmarks stay with correlated shocks on the roadmap.
- Default grid: SPY −20, −15, −10, −7.5, −5, −2.5, 0, +2.5, +5, +10, and +15% by IV −10, −5, 0, +5, +10, and +20 points, at days forward 0 (66 Shocks). Maximum 200 Shocks per Scenario.
- Starter Scenario "Market shock" for Portfolios created empty or from a screenshot, and for an Account on first sync. A copied Portfolio copies its source's Scenarios.
- Open: you asked whether the IV shifts are made up, and whether historical data (Schwab, or Massive, formerly Polygon.io) should ground them.

**2026-10-25, after building the worker ([18](18-engine-worker.md)), not part of the answer above:**

- **What changed.** Where the model can't solve an IV, the worker does not fall back to Schwab's IV. It prices each Shock at the model value at the 1 vol point floor plus the residual (the Mark minus that value), so a zero Shock is worth the Mark, and it ignores the IV Shift for that contract. The contract is flagged `no_iv`. This follows [ADR 0001](../../../docs/adr/0001-own-pricing-model.md) ("the residual is carried unchanged"; "don't feed Schwab's IV into our model").
- **The earlier reasoning, kept.** Ticket 07 states the rule and calls it "the only place a Schwab value goes into our pricing"; it gives no further reason. The apparent benefit (an inference, not recorded) is that a contract with no IV of its own still has a vega response under an IV Shift. The cost is that it feeds Schwab's IV into our model, which ADR 0001 says not to do, and ADR 0001 names the residual carry as the rule.
- **Unimplemented option: Schwab-IV fallback.** To try it, price the contract at Schwab's IV for the base and each Shock, flag it, and take Shock P/L as the difference. The worker would need Schwab's IV in the batch request, which today carries only a Mark. Nothing in the worker has this path.
- **Re-check later: what was built against what was proposed.** Do this once the server function exists and a real Portfolio is priced, and compare each point with Schwab's own Shock figures where Schwab has them. Dated findings go under this heading.
  - *Residual carry against the Schwab-IV option.* A Position with no IV shows no IV risk under the carry (the IV Shift is ignored), and a short-dated, wide-market contract may then understate how far its value moves under a Shock. Check how many Positions in a real Portfolio hit this and how far the two options differ in Shock P/L.
  - *Expired Shocks drop the residual.* A contract that expires inside the horizon is plain intrinsic, with no residual. The answer above says "intrinsic at the shocked price", which this follows, but ADR 0001 says the residual is carried "unchanged". Confirm which reading is intended.
  - *Dividend dropout.* The answer says a dividend going ex inside the horizon drops out of option pricing. The worker does this, but its only test is against its own single-price twin, and [ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md) still lists Shocks that move the valuation date past a dividend as untested against an independent oracle.
    - 2026-10-25, from the review of [18](18-engine-worker.md). An American call with a $2 dividend, at the same spot, is worth 5.41 at +21.0 days and 6.47 at +21.5 days, just past the ex-date. Holding spot while the dividend drops out makes the Shock P/L jump by about delta times the dividend. The batch also drops the Shock's `dividend_not_in_life` flag, which [19](19-engine-worker-review-fixes.md) item 9 fixes. Confirm that a days-forward Shock should hold spot at its cum-dividend level.
  - *Days forward from the "as of" time.* The worker moves the request's valuation forward by calendar days. Counting from the market data's "as of" time is the caller's job; check that the server passes that instant.
  - *Clamp at -99%.* The worker accepts a spot move above -1 and does not clamp or flag. The caller must clamp and flag the Beta-weighted Move. Check that it does.
  - *Flag names.* The answer says "expires within horizon". The worker's flag is `expired`, the same one a single price uses for a contract already past its Settlement instant. Check that the app shows the right wording.
  - *Shock grid accuracy.* Shocks run at 50 by 100 steps, not the 100 by 200 default. ADR 0007 measured it within 0.1 cent at 100 by 200 and no loss of accuracy at 50 by 100 on its spikes; re-check on deep in-the-money and high-IV American options.
