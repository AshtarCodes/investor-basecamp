# IREN position constructions, sold early on a rally

**Version 0.2, 2026-10-26.** The second run of the construction test in [constructions.md](constructions.md) (which holds everything to the thesis year-end). It changes four things at the owner's request: options are sold in June or November instead of held, the downside stress rows are dropped, no cash is allowed, and capital is limited, so return per dollar and cost per contract matter. It is analysis of the owner's view in [thesis.md](thesis.md), not a forecast.

## How it was run

- **Prices.** Every price is a live `pnpm schwab option price` call, no offline runs: [`data/early-sale-quotes-2026-10-26.json`](data/early-sale-quotes-2026-10-26.json) (spot $25.36, ask for longs, bid for shorts) and [`data/early-sale-exit-values-2026-10-26.json`](data/early-sale-exit-values-2026-10-26.json) (252 runs from [`analysis/early_sale_grid.py`](analysis/early_sale_grid.py)). Tables come from [`analysis/early_sale_report.py`](analysis/early_sale_report.py). The first run used spot $25.81, so the two documents differ slightly.
- **Two programmes.** 27: Jan 2028 options sold 2027-06-30 or 2027-11-30. 28: Jan 2029 options sold 2028-06-30 or 2028-11-30. "Scale" sells half of each sleeve in each month. Stock is sold on the same dates.
- **Spot on the sale date.** The thesis gives year-end spots only, so the sale-date spot is an assumption, in two forms. *Interp*: the spot moves along a geometric path from $25.36 to the 2027 case value, then to the 2028 case value, by calendar days (for the bear case, June 2027 is $29, November $31.5). *Front*: the rally has already arrived, so the spot is the full year-end case value on the sale date.
- **Held spreads.** "Held" means a spread is held to its expiry (2028-01-21 or 2029-01-19) and pays its intrinsic value at the year-end case spot. In constructions with spreads, "sold" and "held" differ only in the spread sleeve; the stock and outright calls are always sold early.
- **IV.** Rule 2 is shown; Rule 1 (flat) was run on the interp path and moves construction EVs by up to about 13 points in either programme, and changes no ordering.
- **Cases.** Thesis bear, base and bull only, weighted 30/50/20 (2027) and 35/45/20 (2028). No downside stress is run, and the flat-stock case is dropped with it. No cash is allowed: every mix sums to 100%.
- **Returns** are on the capital in the sleeve, entry at the ask and bid, exit at the model value with no slippage.

## Sleeves

Cost is for one contract (x100). Delta/$ is stock-equivalent exposure per dollar. "Sold" is the scale-out return; "EV" is on the thesis weights.

**Programme 28: Jan 2029 options, sold in 2028**

| Sleeve | $/contract | Delta/$ | Sold, interp: bear / base / bull | EV interp / front | Held to Jan 2029: bear / base / bull |
| --- | --- | --- | --- | --- | --- |
| Stock | 2,536 | 1.00 | +64% / +468% / +1,109% | 455% / 525% | n/a |
| $15 call | 1,885 | 1.19 | +44% / +586% / +1,448% | 569% / 663% | n/a |
| $25 call | 1,470 | 1.37 | +25% / +712% / +1,818% | 693% / 813% | n/a |
| $40 call | 1,110 | 1.51 | -26% / +844% / +2,307% | 832% / 988% | n/a |
| $90 call | 580 | 1.82 | -89% / +926% / +3,663% | 1,118% / 1,386% | n/a |
| 25/75 spread | 855 | 0.93 | +101% / +451% / +474% | 333% / 351% | +146% / +485% / +485% |
| 40/90 spread | 585 | 1.07 | +31% / +673% / +737% | 461% / 490% | +3% / +755% / +755% |
| 25/90 spread | 945 | 1.01 | +88% / +534% / +574% | 386% / 408% | +122% / +588% / +588% |
| 40/75 spread | 495 | 0.94 | +42% / +555% / +594% | 383% / 407% | +21% / +607% / +607% |

**Programme 27: Jan 2028 options, sold in 2027**

| Sleeve | $/contract | Delta/$ | Sold, interp: bear / base / bull | EV interp / front | Held to Jan 2028: bear / base / bull |
| --- | --- | --- | --- | --- | --- |
| Stock | 2,536 | 1.00 | +19% / +195% / +464% | 196% / 322% | n/a |
| $15 call | 1,555 | 1.40 | +4% / +287% / +725% | 290% / 495% | n/a |
| $25 call | 1,140 | 1.62 | -21% / +345% / +939% | 354% / 631% | n/a |
| $40 call | 770 | 1.85 | -56% / +391% / +1,254% | 429% / 827% | n/a |
| $75 call | 350 | 2.23 | -85% / +319% / +2,036% | 541% / 1,287% | n/a |
| 25/75 spread | 842 | 1.27 | +1% / +328% / +419% | 248% / 314% | -17% / +494% / +494% |
| 40/75 spread | 472 | 1.37 | -40% / +390% / +526% | 288% / 383% | -100% / +642% / +642% |
| 40/100 spread | 565 | 1.50 | -45% / +458% / +728% | 361% / 515% | -100% / +962% / +962% |
| 40/140 spread | 657 | 1.63 | -50% / +454% / +963% | 405% / 624% | -100% / +859% / +1,422% |

## What it shows

1. **Spreads make a contract cheaper, not a dollar go further.** A spread costs $495 to $945 a contract against $1,110 to $1,885 for an outright Jan 2029 LEAP and $2,536 for 100 shares, so a small account can hold a position in whole contracts. Per dollar, spreads carry 0.93 to 1.07 of stock-equivalent exposure; outright LEAPs carry 1.37 to 1.82. On the thesis weights the outright calls lead: in programme 28 the $25 call has an EV of 693% against 461% sold or 491% held for the best spread (40/90), and 455% for the stock.
2. **A wide spread matches an ATM LEAP in the base case and gives up the bull tail.** The Jan 2029 40/90 spread returns +673% sold and +755% held in the base, against +712% for the $25 call. It does better in the bear (+31% sold against +25%) and costs $585 against $1,470 a contract. In the bull it returns +737% against +1,818%, and that bull weight of 20% is where most of the EV gap comes from. A spread therefore fits "base case first, bull as a bonus"; the bull exposure has to come from an outright OTM call.
3. **The 25/75 spread is the bear cushion.** In programme 28 it returns +101% sold and +146% held in the bear, above any other sleeve and the stock (+64%), because the $46 bear is far above the $25 long strike. It tops out at +451% sold and +485% held, about level with the stock's base case of +468%, so it only earns its place when the bear matters.
4. **Hold or sell a spread depends on how far in the money it is.** On the like-for-like front path (the stock is at the case value on the sale date), the 25/75 spread held is slightly better than sold (+485% against +464% base, +146% against +137% bear) because it is deep in the money and has no time value left to capture. The 40/90 spread sold is better in the bear (+70% against +3%) because the $46 bear is only just above the $40 strike, and slightly worse in the base and bull (+706% / +739% against +755%). EV is the same (490% against 491%). On the interp path holding looks far better for the Jan 2028 spreads (40/140: 684% against 405% EV), but that compares different spots: holding catches the rally going on to the year-end value, so it measures the cost of selling early, not a property of spreads.
5. **Programme 27 has almost no room for outright OTM calls.** The $32 bear is only just above the $25 and $40 strikes, so every Jan 2028 strike of $25 or more loses in the thesis bear at a November sale (the $25 call is -21% on the interp path). Held to expiry, the Jan 2028 40/xx spreads are -100% in the bear.
6. **Best fully invested mixes.** Search over 5% steps of stock, deep-ITM, ATM, mid-OTM and far-OTM calls, and the spreads, no cash, scale-out, by floor on the thesis-bear return:

   | Programme and path | Bear floor | EV | Mix |
   | --- | --- | --- | --- |
   | 28, interp | 0% | 781% | 70 $25 call / 25 $90 call / 5 25-75 spread |
   | 28, interp | +20% | 708% | 90 $25 call / 5 $15 call / 5 $90 call |
   | 28, interp | +40% | 621% | 80 $25 call / 20 25-75 spread |
   | 28, front | 0% | 1,031% | 55 $25 call / 10 $40 call / 35 $90 call |
   | 28, front | +40% | 856% | 80 $25 call / 5 $40 call / 10 $90 call / 5 25-75 spread |
   | 27, interp | 0% | 300% | 85 $15 call / 10 stock / 5 40-140 spread (held) |
   | 27, interp | +10% | 252% | 60 $15 call / 40 stock |
   | 27, front | 0% | 614% | 85 $15 call / 15 $75 call |

   Stock as a bear floor, an ATM LEAP core, a small far-OTM call for the bull, and the 25/75 spread when a bigger bear return is wanted. For the Jan 2028 programme the deep-ITM $15 call is the vehicle; the thesis bear leaves too little room for anything higher. The exact weights are not meaningful (the solver steps in 5%); the shape is.
7. **What replaces cash.** Cash was earlier the buffer. Without it, the buffer comes from structure: a deep-ITM or ATM LEAP in place of stock (the $15 and $25 calls keep a positive bear return in programme 28, +44% and +25%), the 25/75 spread (+101% to +146%), or stock itself (+64%).

## Sized for $10,000

Whole contracts at the ask (bid for the short leg), with stock shares at $25.36 taking what is left, so the whole $10,000 is deployed. This assumes new capital: the two held Jan 2028 40/75 spreads are not included. Code: [`analysis/sizing.py`](analysis/sizing.py). Results are P/L as a percent of the $10,000, scale-out sale, Rule 2 IV, shown as steady path / "already there" path. "Held" means the spread is held to expiry; everything else is sold in June and November.

Cost of one contract, Jan 2029: $15 call $1,885, $25 call $1,470, $40 call $1,110, $90 call $580, 25/75 spread $855, 40/90 spread $585. Open interest is 442 to 3,843 contracts on the strikes used, so a few contracts is not a liquidity problem, but the quotes are about 5% wide at $25 and 11% wide at $40 (bid to ask, on the snapshot) and the ask was used.

**Programme 28: Jan 2029 options, sold in 2028**

| Build | Bear | Base | Bull | EV |
| --- | --- | --- | --- | --- |
| A  394 shares | +64% / +81% | +467% / +546% | +1,108% / +1,252% | +454% / +525% |
| B  4 x $25 call + 162 shares | +41% / +64% | +611% / +723% | +1,525% / +1,729% | +594% / +694% |
| C  3 x $25 call + 4 x 25/75 spread (held) + 85 shares | +75% / +90% | +581% / +658% | +1,207% / +1,347% | +529% / +597% |
| D  3 x $25 call + 6 x 40/90 spread (sold) + 82 shares | +35% / +64% | +648% / +735% | +1,291% / +1,431% | +562% / +640% |
| E  as D, spreads held | +25% / +41% | +676% / +753% | +1,297% / +1,436% | +573% / +640% |
| F  8 x 40/90 spread (sold) + 2 x $90 call + 164 shares | +31% / +57% | +617% / +701% | +1,231% / +1,364% | +535% / +608% |
| G  2 x $25 call + 4 x 40/90 spread (sold) + 2 x 25/75 spread (held) + 3 x $90 call + 50 shares | +32% / +53% | +670% / +782% | +1,568% / +1,768% | +626% / +724% |
| Search, bear at least +40%: 1 x $40 call + 6 x $90 call + 6 x 25/75 spread (held) + 11 shares | +42% / +49% | +678% / +808% | +1,810% / +2,069% | +682% / +794% |
| Search, bear at least +20%: 2 x $25 call + 6 x $90 call + 3 x 25/75 spread (held) + 40 shares | +20% / +33% | +704% / +860% | +2,046% / +2,351% | +733% / +869% |
| Search, bear at least 0%: 1 x $40 call + 9 x $90 call + 4 x 25/75 spread (held) + 9 shares | +2% / +10% | +754% / +938% | +2,359% / +2,726% | +812% / +970% |

**Programme 27: Jan 2028 options, sold in 2027**

| Build | Bear | Base | Bull | EV |
| --- | --- | --- | --- | --- |
| A  394 shares | +19% / +26% | +195% / +306% | +464% / +806% | +196% / +322% |
| B  6 x $15 call + 26 shares | +5% / +15% | +281% / +456% | +707% / +1,251% | +283% / +483% |
| C  4 x $15 call + 2 x 25/75 spread (held) + 82 shares | +4% / +12% | +302% / +438% | +630% / +1,050% | +278% / +432% |
| D  4 x $15 call + 4 x 40/100 spread (held) + 45 shares | -22% / -14% | +426% / +551% | +877% / +1,265% | +382% / +524% |
| Search, bear at least 0%: 6 x $15 call + 1 x 40/140 spread (sold) | +1% / +11% | +298% / +485% | +739% / +1,284% | +297% / +503% |

What the sizing shows:

1. **Build C beats the stock in every thesis case on both paths** (bear +75% against +64%, base +581% against +467%, bull +1,207% against +1,108% on the steady path). The 25/75 spreads carry the bear and the ATM calls carry the base and bull. It is the only mix of those tested that does not give up the bear for the upside.
2. **More leverage pays only if the bull comes.** G, and especially the search results, buy EV with far-OTM $90 calls (up to 9 contracts, over half the capital in the search's last row). Their bear contribution is a loss (-89% on the $90 call), so those mixes are barbells: the bear is held up by the held spreads and the bull is carried by the calls. The search rows sit exactly at their bear floor, which is a feature of the search, not a margin of safety; the thesis bear is above spot in any case.
3. **Spreads sold or held matters most for the 40/90.** Build E (held) has a better base than D (sold) by 28 points on the steady path but a worse bear (+25% against +35%), as in the sleeve results.
4. **Programme 27 is thin.** With $10,000 and the $32 bear barely above the strikes, the best Jan 2028 choice is deep-ITM calls (B), which lift the base case from +195% to +281% on the steady path and cost 14 points of bear. Holding a 40/xx spread to expiry (D) risks -22%.
5. **Build sizes are coarse.** The $90 call is $580 and the $25 call $1,470, so each contract is 6 to 15% of the capital. Small changes in the quotes change the counts.

## Caveats

- The sale-date spot is assumed. The thesis does not say when the rally happens; interp assumes it builds steadily to the year-end, front assumes it is already there. Real paths will land between them or outside.
- Under interp, November beats June on every sleeve, because the stock is still assumed to be rising. That says nothing about when to sell; it only measures what an earlier sale leaves behind under that path.
- The thesis bear is above today's spot, so the "bear" columns are not downside risk. The downside rows were dropped at the owner's request, which means nothing here measures what happens if the stock does not rise.
- Mixes at 5% steps assume fractional contracts. At small sizes the whole-contract counts decide what is possible (a 5% sleeve of a $10,000 account is $500, less than one spread).
- Entry at ask and bid, exit at model value, no slippage; the Jan 2029 chain fetched lists no strike above $90, so no spread there is capped above the base case; Jun 2028 and later expiries were not priced.

## Changes

- 0.2, 2026-10-26: added "Sized for $10,000" (whole contracts, shares take the remainder).
- 0.1, 2026-10-26: first run, against thesis v1.0.
