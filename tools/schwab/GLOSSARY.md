# Schwab CLI

Command-line helpers for Schwab market data and ad hoc option math. Vocabulary here is for one-off contract repricing and P/L what-ifs, not the portfolio **Scenario** grid in [Investor Basecamp](../../GLOSSARY.md). **Mark**, **Mark-implied IV**, **Settlement instant** and **Remaining life** are shared with the app and defined there.

## Option pricing

**Entry**:
The per-share option premium used as the baseline when net P/L is shown — often a fill you specify, or the current **Mark** when you are quoting a contract you do not hold.
_Avoid_: Cost basis (when meaning Position **Total Cost**), average price

**Valuation instant**:
The moment fair value is measured in a theoretical price run — live runs use now unless inputs are supplied for an offline point in time.
_Avoid_: As-of (flag name)

**Exit instant**:
The moment you assume the option is sold before expiration; remaining life runs from here to settlement.
_Avoid_: Exit date (when time-of-day matters), as-of (flag name)

**Terminal spot**:
The underlying price assumed at contract expiration when payoff is intrinsic only (hold to expiry).
_Avoid_: Expected spot (flag name), terminal price

**Exit spot**:
The underlying price assumed at the **exit instant** when modeling a pre-expiry sale.
_Avoid_: Expected spot (flag name), spot at exit

**Theoretical value**:
Fair option value from our pricing model at the **valuation instant**, with no P/L baseline required.
_Avoid_: Mark, Schwab theoretical

**Expiry payoff**:
Intrinsic value per share at expiration given a **terminal spot**.
_Avoid_: Payoff mode, hold value

**Pre-expiry sale**:
Selling the option at the **exit instant**, with the underlying at **exit spot**; its value is the **Sale proceeds**.
_Avoid_: Sell mode, early exit

**Sale proceeds**:
Our modeled option value per share at the **exit instant**, given **exit spot**.
_Avoid_: Sale price, exit value

**Net P/L**:
An **Expiry payoff** or **Sale proceeds** minus **Entry**, per share.
_Avoid_: Profit, return

**Schwab IV**:
The volatility Schwab reports for a contract on the option chain. It is shown beside our numbers as a cross-check and never fed into our model, which uses **Mark-implied IV**.
_Avoid_: Contract IV, implied vol (unqualified)
