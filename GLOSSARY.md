# Investor Basecamp

A personal portfolio risk tool for Schwab accounts: see what you hold, and see how much you could lose if prices or implied volatility move.

## Holdings

**Account**:
One Schwab brokerage account. Its holdings come only from Schwab.
_Avoid_: Portfolio (for the broker account itself), brokerage

**Snapshot**:
An Account's complete holdings at one moment. A Position missing from a later Snapshot has been closed.
_Avoid_: Import, sync result

**Simulated Portfolio**:
A named, editable set of Positions and cash that no Account owns. It starts empty, as a copy of another Portfolio, or from a screenshot, and is independent of its source from then on.
_Avoid_: Paper portfolio, what-if portfolio, model portfolio

**Portfolio**:
Anything a Scenario runs against: an Account's current Snapshot, or a Simulated Portfolio.

**Position**:
A holding of one instrument with a signed quantity (negative when short) and a signed total cost.
_Avoid_: Holding, line, row

**Total Cost**:
The signed net cost of a Position: positive for a debit paid, negative for a credit received.
_Avoid_: Cost basis (when the sign convention matters)

**Underlying**:
The stock, ETF, or index that a Position's value depends on. An equity Position's Underlying is itself.

**Leg**:
One option Position considered as part of a multi-option structure on the same Underlying.

**Hypothetical Trade**:
A Position you don't actually hold. It exists only inside a Simulated Portfolio.
_Avoid_: What-if position, overlay

## Risk

**Scenario**:
A named set of modeled futures for one Portfolio, which owns it: a grid of SPY moves by IV shifts, plus a number of days forward.
_Avoid_: What-if, alternate history, stress test

**Shock**:
One cell of a Scenario: a single SPY move and IV Shift, applied together at the Scenario's days forward.
_Avoid_: Cell (in domain talk), case

**IV Shift**:
A Shock's change to each option contract's own implied volatility, in vol points or as a percent of that volatility. It is independent of the SPY move.
_Avoid_: Vol bump, vega shock

**Beta-weighted Move**:
An Underlying's price change under a Shock: its beta to SPY times the SPY move, unless the Scenario overrides that beta.

**Shock P/L**:
The change in a Portfolio's value under a Shock, measured from its current market value. Loss Thresholds are judged against it.
_Avoid_: Scenario return, projected P/L

**Loss Threshold**:
A risk budget: the largest loss you accept being exposed to under a Portfolio's Scenarios. It can be set for the Portfolio or for one Underlying, never for a single Leg, and it is not an exit rule.
_Avoid_: Stop-loss, limit, max loss

**Net Liquidation Value**:
A Portfolio's Cash plus the market value of its Positions.
_Avoid_: Account value, equity, balance

**Cash**:
The signed cash in a Portfolio. A positive amount is money on hand. A negative amount is margin owed.
_Avoid_: Balance, buying power

**Margin Cushion**:
How far Net Liquidation Value can fall, as a percent, before a margin call. The call is at today's Net Liquidation Value times one minus that percent. A Portfolio that is not borrowing has none.
_Avoid_: Margin percentage, equity percentage, buying power
