# IREN observations

Recorded 2026-10-26. Newest sections go at the bottom.

## 2026-10-26: one year of IREN against the VIX

**Data.** Schwab `/pricehistory`, daily closes for `IREN` and `$VIX`, 2025-10-23 to 2026-10-23 (252 common trading days), in [`data/daily-closes-2025-10-23_2026-10-23.csv`](data/daily-closes-2025-10-23_2026-10-23.csv). It stops at the 10-23 close: on 10-26 IREN was 26.485 (+6.34%) and the VIX 17.86 (-8.17%). Regenerate every number below with `python3 scenarios/iren/analysis/legs_vs_vix.py`.

**Method.** A leg ends when IREN reverses 25% from its extreme close (a rule, not an eyeball call). The VIX is averaged over each leg's days.

| Leg | IREN | Move | Days | Avg VIX | VIX start to end |
| --- | --- | --- | --- | --- | --- |
| 2025-10-23 to 11-05 | 55.9 to 76.4 | +37% | 9 | 17.1 | 17.3 to 18.0 |
| 2025-11-05 to 12-17 | 76.4 to 33.8 | -56% | 29 | 18.5 | 18.0 to 17.6 |
| 2025-12-17 to 2026-01-28 | 33.8 to 62.9 | +86% | 27 | 15.5 | 17.6 to 16.4 |
| 2026-01-28 to 03-30 | 62.9 to 31.6 | -50% | 42 | 22.1 | 16.4 to 30.6 |
| 2026-03-30 to 05-27 | 31.6 to 67.8 | +115% | 40 | 19.2 | 30.6 to 16.3 |
| 2026-05-27 to 07-29 | 67.8 to 29.3 | -57% | 43 | 17.5 | 16.3 to 20.7 |
| 2026-07-29 to 09-22 | 29.3 to 48.5 | +66% | 38 | 15.7 | 20.7 to 14.2 |
| 2026-09-22 to 10-23 | 48.5 to 24.9 | -49% | 23 | 16.3 | 14.2 to 19.5 |

**Findings**
- Day-weighted average VIX is **17.0 in rally legs and 18.9 in tank legs**. The full-year average is 18.0. The level separates them by about 2 points, so it is a weak signal.
- Direction matters more than level. Rallies mostly run while the VIX falls or sits low (Dec-Jan 15.5, Jul-Sep 15.7, Mar-May from 30.6 down to 16.3). IREN's daily return has a correlation of -0.42 with the VIX's daily change, which explains about 18% of its daily variance.
- Two of the four tanks happened at a calm VIX: May-Jul averaged 17.5 and Sep-Oct 16.3, so these were IREN-specific selloffs. Only Jan-Mar (-50%) was a fear-driven decline (VIX 16.4 to 30.6).
- Days beyond +/-5%: the VIX averaged 17.6 on the 57 up days and 19.1 on the 56 down days.
- IREN's 20-trading-day forward return by starting VIX: below 16 averaged -0.6% (up in 52% of 65 cases), 16 to 20 averaged -4.7% (up in 37% of 123), 20 to 25 averaged -0.6% (38% of 29), 25 or higher averaged +16.8% (73% of 15). The 25+ bucket is one episode (March); do not lean on it.
- The user's named windows: late March (Iran-war fear) VIX averaged 24.9 with a peak of 31.05; April 10 to June 1 IREN rose 66% at an average VIX of 17.7, ending at 16.05 (the 06-01 close; the chart reads about 15.5); June 1 to now IREN fell 62% at an average VIX of 16.6.

**Realized volatility** (log returns, annualized): full year 106%, last 60 days 82%, last 30 days 73%, last 10 days 94%. By leg it ran 100% to 114%, except the latest leg at 71%. Worst day -17.4%, best +30.5%; 39 of 251 days moved more than 10%. Legs averaged about 70% in absolute move over about 31 trading days, so a scenario range of -50% to +100% is inside what happened.

**Caveats.** One year, one stock, 8 legs. A different reversal threshold gives different legs. The VIX is the market's fear gauge, not IREN's own implied volatility: **no IREN implied-volatility history is available from the API**, so how IREN's IV moved with its price is not measured here (see the open questions).

## 2026-10-26: what the tool showed on the Jan 2028 and Jan 2029 calls

Live quotes, `schwab option price`, about 10:45 to 11:40 ET. IV is the Mark-implied IV (solved from the Mark with our model, the one the tool uses); "API IV" is Schwab's `volatility` field, never fed into our model.

| Contract | Our IV | TOS screen IV | API IV | Our value at API IV vs Schwab `ANALYTICAL` |
| --- | --- | --- | --- | --- |
| Jan 2028 $40 call | 92.9% to 94.1% (moves with the quote) | 93.00% | 97.9% to 98.9% | 8.117 vs 8.113 |
| Jan 2028 $75 call | 91.2% | n/a | 93.6% | 3.805 vs 3.801 |
| Jan 2029 $40 call | 88.1% | 89.46% | 95.7% | 11.712 vs 11.708 |

- Our IV and our Greeks match TOS, not the API. The API's IV is 2 to 8 vol points above the IV of its own Mark and does not reproduce it. The model is not the cause: at the API IV our price is within half a cent of Schwab's own `ANALYTICAL` price.
- Mark-implied IV falls with maturity: about 93% (Jan 2028), 88% (Jan 2029), against a year of realized volatility of 106%. The IV paid on entry is below the year's realized and above the last month's (73%).
- The IV choice barely moves shock P/L. On the 2029 $40 call (88.1% vs the API's 95.7%) a 20% drop in spot costs $329 per contract on our IV and $345 on the API's (about 5% apart); on the held spread (below) the difference is $1 to $11 for spot moves of -40% to +50%.

## 2026-10-26: the held position under one scenario

Position per the TOS chain: long 2 Jan 2028 $40 calls at an average $7.04, short 2 Jan 2028 $75 calls at an average $3.27, a call debit spread. Net debit $754 (cost $1,408, credit $654). Risk is capped at the debit because the long call covers the short.

Scenario: exit 2027-04-26, IREN +50% (26.54 to 39.80), IV flat at each leg's Mark-implied level (93.5% and 90.8%).

| Leg | P/L | Percent |
| --- | --- | --- |
| Long 2 x $40 (12.82 at exit vs $7.04 paid) | +$1,156 | +82.1% of cost $1,408 |
| Short 2 x $75 (buyback 5.09 vs $3.27 received) | -$365 | -55.8% of the credit $654 |
| Net | +$791 | +105.0% of the net debit $754 |

Against today's Marks as the entry (net debit $850) the same sale is +$695, +81.8%. Holding both calls to expiry at 39.80 expires them worthless: -$754, -100%. The $40 call alone at 39.62 gave +$1,121, +79.6% of $1,408 (+64.8% against the Mark).

## 2026-10-26: volume against price and reversals

Data: daily candles from `pnpm schwab get /marketdata/v1/pricehistory?symbol=IREN&periodType=year&period=1&frequencyType=daily&frequency=1`, 252 days to 2026-10-23, saved in [`data/daily-ohlcv-2025-10-23_2026-10-23.csv`](data/daily-ohlcv-2025-10-23_2026-10-23.csv). Closes match the earlier closes file on every day. Run: `python3 scenarios/iren/analysis/volume_vs_price.py`. RVOL is a day's volume over the mean of the prior 20 days.

- **Volume follows the size of the move, not its direction.** Correlation of |daily return| with RVOL is +0.44; of signed return with RVOL is +0.05. Up days average 1.05x and down days 1.01x. Quiet days (-5% to +5%) run 0.9x; days beyond -10% run 1.56x and days beyond +10% run 1.29x. Big down days draw more volume than big up days.
- **Rally and tank legs trade the same volume.** Mean daily volume is 40.8M shares in the four rallies and 42.9M in the four tanks. Dollar volume falls from about $2.5B/day (Oct 2025) to about $1.7B/day (Oct 2026), so the share count held up because the price halved, not because interest rose.
- **Reversals do not show a volume climax.** RVOL on the day of a top averages 1.18x (range 0.8 to 1.6, three tops with data) and on a bottom 1.24x (0.8 to 1.6, three bottoms). The 3 days before a top average 1.23x on the first day and 0.98x on the next; nothing separates it from an ordinary day. Three bottoms and three tops is too few to call a pattern.
- **The one volume signature that repeats is clustered spikes, and they are not reversal signals.** Of the 10 highest-RVOL days (1.9x to 2.7x), 6 sit in two clusters (2026-05-07 to 05-11, 2026-10-14 to 10-15); the 5-day return after them ranged from -16% to +26% with no consistent sign.
- **The current tank is the heaviest.** The 2026-09-22 to 2026-10-23 leg (-49%, 23 days) averages 49.3M shares and 1.21x RVOL, the highest of any leg.

Caveats: 8 legs and 6 pivots, one stock, one year. The pivots are in hindsight (a 25% reversal confirms them days or weeks late), so volume at the pivot day was not knowable on the day. No intraday data.

## Open questions

- **IREN IV history.** Schwab gives no historical option IV. Starting a daily snapshot of the Mark-implied IV (and realized vol) at a few expiries would let us measure IV against spot, which the rules in [`iv-rules.md`](iv-rules.md) currently assume.
- **Earnings.** Earnings markers on the chart (the last was 2026-08-27 per Schwab's fundamentals) were not tested as IV events. A LEAP carries less event risk than a front month, but this is unmeasured.
- **Term structure under a move.** The tool holds each leg's IV flat in time; a down-sloping term structure (93% to 88%) would roll up the curve as time passes. Not modelled.
- **A different leg threshold** (15% or 35%) as a robustness check on the 17.0 vs 18.9 result.
