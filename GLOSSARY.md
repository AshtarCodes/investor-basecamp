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

**Sleeve**:
A group of identical contracts bought together: a number of one call, or a number of one spread, which is two Legs. Shares and cash are not Sleeves.
_Avoid_: Leg (for a whole spread), line, position group

**Build**:
A set of Sleeves plus shares bought with a starting budget, compared on Price Paths. Whatever the Sleeves don't use goes into shares.
_Avoid_: Construction, mix, portfolio

**Hypothetical Trade**:
A Position you don't actually hold. It exists only inside a Simulated Portfolio.
_Avoid_: What-if position, overlay

## Risk

**Price Path**:
A named, assumed course for the Underlying's price: a series of dated prices, each with an Action. It has a weight that sets how much it counts toward an expected result.
_Avoid_: Scenario (that is the SPY-by-IV grid), path

**Action**:
What happens to the options on a Price Path's date: hold, sell a percent and keep the money as cash, or sell a percent and put the money into shares.
_Avoid_: Trade, rule, policy

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

## Pricing

**Mark**:
Schwab's quoted current price for an option contract, per share: the midpoint of its bid and ask.
_Avoid_: Theoretical value, last price

**Quote Set**:
The Marks, bids, asks and Underlying price for a group of option contracts, all taken at one moment, named by when it was taken. Values compared side by side come from one Quote Set.
_Avoid_: Snapshot (that is an Account's holdings), chain dump

**Mark-implied IV**:
The volatility at which our model reproduces a contract's Mark. Every Position's base value starts from it, so a Shock of zero reproduces market value.
_Avoid_: Contract IV, chain IV

**Settlement instant**:
The moment a contract stops trading and settles: 4:00 pm ET on expiration day for equity, ETF, SPXW and XSP options, and 9:30 am ET for AM-settled SPX.
_Avoid_: Expiry date, expiration (when time of day matters)

**Remaining life**:
Calendar time from a valuation moment through a contract's Settlement instant. Under a Shock it is today's remaining life minus the Scenario's days forward.
_Avoid_: DTE, time to expiry (when the instant is ambiguous)
