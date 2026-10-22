# Can historical data calibrate and back-test Shocks?

Type: research
Status: open
Blocked by: 05

## Question

The way a Shock works is decided in [How should Shocks behave?](07-how-should-shocks-behave.md). The size of its default IV range (−10 to +20 points) and its default mode (absolute) were judgment calls. Find out, from primary sources, whether real history can ground them:

- **Schwab Trader API:** does any endpoint return historical option quotes, chains, or IV, or only the Underlying's price bars? How far back do daily, weekly, and monthly bars go, and are they available for small caps (IREN, CIFR, ASST) and indexes (`$SPX`, `$NDX`, `$RUT`)? Beta's three lookback presets depend on this.
- **Massive (formerly Polygon.io):** which plans include historical options data (quotes, trades, daily bars, IV or greeks), how far back, coverage of small-cap option chains, price for one personal user, licensing terms for personal use, and rate limits.
- **Alternatives:** any other affordable source of historical option IV (for example Cboe DataShop or ORATS), briefly, with cost.
- **How IV actually moves:** what published evidence says about whether single-stock IV changes scale with the IV level (favoring proportional shifts) or stay roughly constant in points. Also typical IV changes for high-IV single stocks compared with ETFs on SPY drawdown days and around earnings.
- **Back-testing:** what inputs a back-test needs for each past day (option mark, Underlying price, rate, dividends), and which of the sources above supply them. A back-test runs a Shock on contracts as they were before a past move and compares the result with what they actually did.

The findings decide whether the default IV range and mode change, and whether v1 should gain a calibration or back-test feature. That feature would become its own decision ticket.
