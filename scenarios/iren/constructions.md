# IREN position constructions against the thesis cases

**Version 0.1, 2026-10-26.** Tests stock, LEAP calls and LEAP call spreads against the bear/base/bull cases in [thesis.md](thesis.md). It is analysis of the owner's view, not a forecast. Rerun it when the thesis is updated (quarterly) or the quotes move a lot.

This run holds every position to the thesis year-end. The version that sells early on a rally, with no cash and no downside rows, is [constructions-early-sale.md](constructions-early-sale.md).

## How it was run

- **Prices.** Every price is a live `pnpm schwab option price` call (no offline runs). Quotes: [`data/leap-quotes-2026-10-26.json`](data/leap-quotes-2026-10-26.json) (spot $25.81, ask for longs, bid for shorts, Mark-implied IV, delta). Exit values: [`data/leap-exit-values-2026-10-26.json`](data/leap-exit-values-2026-10-26.json), 224 `--mode sell` runs from [`analysis/construction_grid.py`](analysis/construction_grid.py). The tables come from [`analysis/construction_report.py`](analysis/construction_report.py).
- **Exits.** 2027-12-31 and 2028-12-29 (the thesis year-ends) at the six thesis spots ($32/$103/$230 and $46/$164/$343), plus a stress set of flat, -30% and -50% from $25.81 (the measured range in [iv-rules.md](iv-rules.md), Rule 4). The stress rows are not part of the thesis and carry no weight.
- **IV.** Rule 2 (shifted by the spot move) is shown; Rule 1 (flat) was also run. Cell values differ (up to about 10 points on downside rows, about 30 on the 25/75 spread's EV), but the rankings and every conclusion below are the same under both.
- **Contracts.** Jan 2028 and Jan 2029 only. Jun 2028 was left out because its quotes are too wide to price fairly (for example the $75 call is 4.65 bid, 5.40 ask). Jan 2028 options have 3 weeks left at the 2027 year-end and have expired by the 2028 one, so only Jan 2029 reaches both.
- **Returns** are on the capital in the sleeve; a construction is capital weights, the rest cash at 0%. EV uses the owner's weights (30/50/20 for 2027, 35/45/20 for 2028). "Delta x" is entry delta times spot over cost, summed by weight: the stock-equivalent exposure per dollar of capital.

## Sleeves (Rule 2 IV)

| Sleeve | Cost | Delta x | 2027: bear / base / bull | 2027 flat / -30% / -50% | 2028: bear / base / bull | 2028 flat / -30% / -50% |
| --- | --- | --- | --- | --- | --- | --- |
| Stock | 25.81 | 1.00 | +24% / +299% / +791% | 0% / -30% / -50% | +78% / +535% / +1,229% | 0% / -30% / -50% |
| Jan 2029 $15 | 18.95 | 1.21 | +7% / +369% / +1,038% | -20% / -50% / -70% | +64% / +686% / +1,631% | -43% / -80% / -96% |
| Jan 2029 $25 (ATM) | 14.80 | 1.38 | -2% / +439% / +1,294% | -29% / -58% / -77% | +42% / +840% / +2,049% | -81% / -98% / -100% |
| Jan 2029 $40 | 11.35 | 1.53 | -18% / +493% / +1,593% | -43% / -67% / -83% | -37% / +993% / +2,571% | -99% / -100% / -100% |
| Jan 2029 $60 | 8.50 | 1.68 | -37% / +526% / +1,948% | -57% / -75% / -88% | -96% / +1,125% / +3,231% | -100% each |
| Jan 2029 $90 | 5.95 | 1.84 | -56% / +529% / +2,404% | -70% / -82% / -92% | -100% / +1,148% / +4,156% | -100% each |
| Jan 2029 25/75 spread | 8.20 | 0.98 | +33% / +330% / +450% | -3% / -43% / -66% | +157% / +508% / +508% | -66% / -97% / -100% |
| Jan 2029 40/90 spread | 5.75 | 1.12 | +15% / +420% / +652% | -19% / -54% / -75% | +25% / +767% / +767% | -99% / -100% / -100% |
| Jan 2028 $40 (2027 only) | 7.70 | 1.90 | -92% / +720% / +2,369% | -99% / -100% / -100% | n/a | n/a |
| Jan 2028 40/75 spread (2027 only; the held spread, at today's ask/bid) | 4.25 | 1.49 | -86% / +715% / +721% | -98% / -100% / -100% | n/a | n/a |

## Constructions, as sized (Rule 2 IV)

Each row is 2027 / 2028. All rows are fully invested except 9.

| Construction | Bear | Base | Bull | EV | Flat | -30% | -50% | Delta x |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 All stock | 24 / 78 | 299 / 535 | 791 / 1,229 | 315 / 514 | 0 / 0 | -30 / -30 | -50 / -50 | 1.00 |
| 2 All ATM LEAP | -2 / 42 | 439 / 840 | 1,294 / 2,049 | 478 / 802 | -29 / -81 | -58 / -98 | -77 / -100 | 1.38 |
| 3 All $60 LEAP | -37 / -96 | 526 / 1,125 | 1,948 / 3,231 | 642 / 1,119 | -57 / -100 | -75 / -100 | -88 / -100 | 1.68 |
| 4 All 25/75 spreads | 33 / 157 | 330 / 508 | 450 / 508 | 265 / 385 | -3 / -66 | -43 / -97 | -66 / -100 | 0.98 |
| 5 30 stock / 30 ATM / 20 40-90 spread / 10 $60 (the sketch) | 6 / 32 | 358 / 678 | 951 / 1,460 | 371 / 608 | -18 / -54 | -45 / -68 | -62 / -75 | 1.11 |
| 6 as 5, spread 25/75 | 10 / 58 | 340 / 627 | 910 / 1,408 | 355 / 584 | -15 / -47 | -42 / -68 | -60 / -75 | 1.08 |
| 7 50 stock / 25 ATM / 15 25-75 spread / 10 $60 | 13 / 64 | 362 / 666 | 981 / 1,526 | 381 / 627 | -14 / -40 | -43 / -64 | -63 / -75 | 1.16 |
| 8 80 stock / 20 $60 | 12 / 43 | 345 / 653 | 1,023 / 1,629 | 380 / 635 | -11 / -20 | -39 / -44 | -58 / -60 | 1.14 |
| 9 60 $15 LEAP / 20 25-75 spread / 10 $60 / 10 cash | 7 / 60 | 340 / 626 | 908 / 1,403 | 354 / 583 | -18 / -49 | -46 / -77 | -64 / -87 | 1.09 |
| 10 50 stock / 50 $90 | -16 / -11 | 414 / 842 | 1,597 / 2,693 | 522 / 913 | -35 / -50 | -56 / -65 | -71 / -75 | 1.42 |

## What it shows

1. **No call structure protects the downside; only cash does.** Compare at equal stock-equivalent delta (each construction scaled to 1.0x with the rest in cash). At every downside row (flat, -30%, -50%, both years) the option constructions lose as much as or more than stock, except far-OTM calls at -50%, which are within 3 points (-52% vs -50%). Calls add upside and cost carry; they do not add safety.
2. **The thesis bear case does not need protection; the thesis failing does.** The bear case is $32 and $46, above today's $25.81, so even the stock returns +24% and +78% in it. The loss risk sits outside the three cases, in the stress columns, and that is where the choice of sleeves matters. The EV column ranks leverage first by construction, because no weighted case loses.
3. **Spreads capped below the base case give back the thesis.** Base and bull spots ($103 to $343) are past $75 and $90, so a 25/75 spread tops out at +330% (2027) and +508% (2028) while stock returns +299% and +535% in the base. Per unit of delta, the 25/75 spread's EV is 270% against the stock's 315% in 2027 and 392% against 514% in 2028. Spreads help only in the bear (+33% and +157%) and only because they are cheap, and they lose more than stock when the stock does not rise (-43% at -30% in 2027, -97% in 2028). The Jan 2029 chain stops at a $90 strike, so a short strike above the base case ($103 and up) is not available for that expiry.
4. **The sketch (30/30/20/10) is beaten by a simpler mix.** Construction 8 (80 stock / 20 Jan 2029 $60) has a higher EV (380 / 635 against 371 / 608), a better bear (12 / 43 against 6 / 32) and shallower losses at flat, -30% and -50% in both years. The sketch is better only in the base case (358 / 678 against 345 / 653), at about the same delta (1.11 against 1.14). The ATM and spread sleeves cost bear return and add downside without adding to EV.
5. **Time is the cost of options here.** If the stock is flat at the year-end, the ATM LEAP loses 29% (2027) and 81% (2028); the stock loses nothing. At the 2028 year-end the Jan 2029 options have 3 weeks left, so a thesis that has not arrived by then is close to a total loss on any strike at or above spot. The holder would roll or cut before that, which this test does not model.
6. **What fits the three goals** (use the base case, some bull exposure, margin of safety). Search over 5% steps of stock, Jan 2029 $15, $25, $60, $90 calls, the 25/75 and 40/90 spreads and cash, at 1.0x entry delta, requiring both thesis bears to return at least 0% and bounding the loss if the stock is flat at the year-end:

   | Flat loss no worse than | Best mix | Avg EV (2027 and 2028) | Flat | -30% | -50% | Bear 2027 / 2028 |
   | --- | --- | --- | --- | --- | --- | --- |
   | 0% | 100 stock | 415% | 0% | -30% | -50% | 24 / 78 |
   | -10% | 85 stock / 10 $60 / 5 cash | 440% | -10% | -35% | -53% | 17 / 57 |
   | -20% | 65 stock / 20 $90 / 15 cash | 474% | -20% | -39% | -53% | 4 / 31 |
   | -30% | 50 stock / 25 $60 / 5 $90 / 20 cash | 478% | -30% | -45% | -55% | 0 / 10 |

   The structure is mostly stock, a small OTM LEAP sleeve (10 to 25%) and cash. Each step buys 25 to 35 points of average EV and gives up 4 to 6 points at -30%. Beyond a -20% flat loss the EV gain is 4 points. The solver chose 5% steps; the exact weights are not meaningful, the shape is.

## Caveats

- Year-end exits only; path, early exits, rolls and assignment are not modeled. The 2028 downside columns are the hold-to-date case.
- Entry at the ask and bid; exit at the model value, so no exit slippage is deducted. Half the quoted spread is 1 to 4% of premium on the liquid Jan 2028 strikes and more on thinly traded Jan 2029 ones.
- Mark-implied IV is noisy for deep ITM strikes with wide quotes (the Jan 2029 $15 solves to 107% against about 93% at $40). It barely moves exit values on those strikes.
- Delta x uses entry deltas; an OTM call's delta falls as the stock falls, so the equal-delta view flatters far-OTM sleeves at -30% and -50%.
- Spot is $25.81 here against $26.49 in the first version of [thesis.md](thesis.md), so the implied thesis returns differ slightly.
- No tax, financing, margin or position-size limit is modeled. Puts and collars were not tested.

## Changes

- 0.1, 2026-10-26: first run, 10 constructions and a mix search against thesis v1.0.
