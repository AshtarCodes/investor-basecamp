# IREN two-book constructions with a half-sale, a put hedge and a November 2027 debt payment: results

**Version 0.1, 2026-10-26.** Results of [plan-two-book-roundtrip.md](plan-two-book-roundtrip.md) (v0.3), run against [thesis.md](thesis.md) v1.0. It sits beside [constructions.md](constructions.md) and [constructions-early-sale.md](constructions-early-sale.md) and supersedes neither. It is analysis of the owner's view, not a forecast, and tax is not modelled.

## What was run

- **Prices.** 513 live `pnpm schwab option price` valuations (no offline runs) at spot $25.70: calls (Jan 2028 and Jan 2029) and puts (listed Jan 2028 and Jan 2029 strikes as proxies for the puts that will exist later). Quotes: [`data/roundtrip-quotes-2026-10-26.json`](data/roundtrip-quotes-2026-10-26.json). Values: [`data/roundtrip-exit-values-2026-10-26.json`](data/roundtrip-exit-values-2026-10-26.json). **Raw data is now kept:** every CLI response is in [`data/raw/roundtrip-cli-responses-2026-10-26.jsonl.gz`](data/raw/roundtrip-cli-responses-2026-10-26.jsonl.gz) and the full Schwab call-and-put chain (1,332 contracts) in [`data/raw/chain-calls-puts-2026-10-26.json.gz`](data/raw/chain-calls-puts-2026-10-26.json.gz). Code: [`roundtrip_grid.py`](analysis/roundtrip_grid.py), [`roundtrip_report.py`](analysis/roundtrip_report.py), [`overshoot_check.py`](analysis/overshoot_check.py).
- **Seven paths.** Straight bear, base and bull (to the 2027 and then the 2028 case value), and four round trips: up to $85 or $103 on 2027-06-30 or 2027-11-30, down to the 2027 bear ($32) by 2027-12-31, on to the 2028 bear ($46). Bear weight is 20% straight and 80% round trip, split evenly over the four. Case weights are the thesis's (30/50/20 for 2027, 35/45/20 for 2028).
- **Policies.** *Hold* (no trigger). *Sell half* at the trigger ($85 or $103, first of Jun 30 / Nov 30 2027 on which the path is at or above it). *Sell half plus puts* (50% or 100% of the remaining position's dollar value, at the money or about 15% below, paid from the proceeds). *Puts only* (same puts, paid by selling shares). No 2028 puts.
- **Debt.** On 2027-11-30, withdraw 10%, 25% or 50% of (wealth minus $10,000), from banked cash first, then calls (highest leverage first), then shares. Nothing is withdrawn on a path with no gain. 25% is shown unless stated.
- **Books.** Return book (outright calls that pass the test below), barbell book (25/75 spread held to expiry, a far-out call, a wide spread held), shares. $10,000 in whole contracts; shares take what is left. Return-book share 20% to 60%.
- **Programme 28** is Jan 2029 options, everything left sold half on 2028-06-30 and half on 2028-11-30. **Programme 27** is Jan 2028 options, everything left valued on 2027-12-31 (a change from the earlier early-sale runs, which sold in June or November, because the half-sale and debt events now sit in 2027).
- **Total return** is (final wealth plus debt paid) over $10,000, minus 1. **E** is its probability-weighted mean over the seven paths. **Bear** is the mean over the five bear paths.

## Does the stock round-trip? What two years of closes show

From the 25% reversal legs in the closes we hold ([`overshoot_check.py`](analysis/overshoot_check.py)):

- After the rally legs of +86% (to $62.94) and +115% (to $67.84), the stock fell 50% and 57% in 42 and 43 trading days, ending 6% and 7% below where the rally began. After the +1,212% leg peaked at $69.56 and pulled back 25%, a further +47% rally to $76.41 was followed by a -56% fall in 29 days.
- Over the 102 days that followed a +100% advance in 60 trading days, a drop of 50% or more from the high came within 60 days on 34 of them (a few overlapping episodes, so this is a count, not a rate), and a drop of 60% or more on none.
- The round-trip paths here fall from $85 to $32 (-62%) and from $103 to $32 (-69%), harsher than anything in the data, and in the November-peak paths they do it in 31 days. Treat those two (RT85N, RT103N) as stress paths.

## The 200-point test (calls versus the stock, base case, sold on the scale-out dates)

Steady path / already-there path, in points over the stock's return.

| Programme | $15 | $25 | $40 | far ($90 in 28, $75 in 27) |
| --- | --- | --- | --- | --- |
| 28: Jan 2029 | +125 / +154 fail | +252 / +310 pass | +383 / +485 pass | +464 / +697 pass |
| 27: Jan 2028 | +96 / +167 fail | +154 / +287 fail | +199 / +430 fail by 1 point | +126 / +569 fail |

No Jan 2028 call passes. The $40 misses by 1 point on the steady path, so the Jan 2028 results below admit it as a labelled near-miss. The test is easy for the outright Jan 2029 calls but hard for a whole portfolio (finding 1).

## Programme 28 (Jan 2029 options): policies on four builds

Total return incl. debt, 25% debt, put IV flat. Contracts are Jan 2029.

| Build | Policy | E | Bear | Base | Bull | Expected debt paid |
| --- | --- | --- | --- | --- | --- | --- |
| All shares (394) | Hold | +417% | +76% | +425% | +1,000% | $7,419 |
| **Return-heavy** 2 x $40 + 6 x $90 + 1 x 25/75 spread + 134 shares | Hold | +674% | +36% | +624% | +1,904% | $11,559 |
| | Sell half @ $85 | +570% | +119% | +577% | +1,342% | $10,301 |
| | Sell half @ $103 | +670% | +84% | +624% | +1,796% | $11,862 |
| | Sell half @ $85 + 50% ATM puts | +548% | +148% | +534% | +1,279% | $10,204 |
| | Sell half @ $85 + 100% ATM puts | +509% | +176% | +484% | +1,148% | $10,192 |
| | 50% ATM puts only @ $85 | +604% | +113% | +551% | +1,581% | $11,049 |
| **Balanced** 1 x $25 + 1 x $40 + 2 x 25/75 spread + 1 x $90 + 200 shares | Hold | +488% | +88% | +496% | +1,171% | $8,909 |
| | Sell half @ $85 | +413% | +164% | +447% | +772% | $7,928 |
| | Sell half @ $103 | +482% | +132% | +496% | +1,062% | $9,182 |
| | Sell half @ $85 + 50% ATM puts | +400% | +176% | +425% | +734% | $7,880 |
| | Sell half @ $85 + 100% ATM puts | +375% | +200% | +382% | +665% | $7,783 |
| | 50% ATM puts only @ $85 | +430% | +138% | +423% | +955% | $8,563 |
| **Barbell-heavy** 1 x $40 + 2 x $90 + 6 x 25/75 spread + 101 shares | Hold | +457% | +128% | +466% | +1,013% | $8,538 |
| | Sell half @ $85 | +418% | +146% | +494% | +720% | $7,893 |
| | 50% ATM puts only @ $85 | +397% | +174% | +393% | +798% | $8,192 |
| **Stock-heavy** 1 x $25 + 1 x 25/75 spread + 1 x $90 + 276 shares | Hold | +451% | +90% | +449% | +1,087% | $8,376 |
| | Sell half @ $85 | +424% | +124% | +449% | +892% | $7,733 |
| | 50% ATM puts only @ $85 | +391% | +137% | +376% | +872% | $8,030 |

Money and wealth by path for the first two builds, in dollars (debt paid on 2027-11-30 at 25% of the gain / final wealth):

| Path | Return-heavy, hold | Return-heavy, sell half @ $85 | Balanced, hold | Balanced, sell half @ $85 |
| --- | --- | --- | --- | --- |
| Straight bear | $0 / $9,651 | $0 / $9,651 | $262 / $15,152 | $262 / $15,152 |
| Straight base | $9,012 / $63,393 | $9,012 / $58,732 | $7,779 / $51,828 | $7,779 / $46,929 |
| Straight bull | $30,823 / $169,593 | $21,973 / $122,201 | $20,720 / $106,370 | $13,477 / $73,733 |
| Up to $85 in June, then down | $310 / $9,674 | $3,293 / $19,706 | $952 / $14,998 | $3,733 / $23,425 |
| Up to $85 in November, then down | $7,482 / $9,667 | $7,482 / $13,900 | $6,748 / $15,182 | $6,748 / $19,590 |
| Up to $103 in June, then down | $443 / $9,927 | $4,776 / $23,775 | $1,093 / $14,955 | $5,002 / $26,865 |
| Up to $103 in November, then down | $10,899 / $10,003 | $10,899 / $15,924 | $9,007 / $15,862 | $9,007 / $22,031 |

## Programme 27 (Jan 2028 options, near-miss $40 call admitted)

| Build | Policy | E | Bear | Base | Bull | Expected debt paid |
| --- | --- | --- | --- | --- | --- | --- |
| All shares | Hold | +313% | +43% | +294% | +767% | $7,585 |
| **Return-heavy** 7 x $40 + 2 x 25/75 spread + 2 x $75 + 87 shares | Hold | +628% | +7% | +555% | +1,740% | $15,198 |
| | Sell half @ $85 | +540% | +142% | +542% | +1,129% | $13,329 |
| | Sell half @ $85 + 50% ATM puts | +543% | +203% | +529% | +1,086% | $13,270 |
| | 50% ATM puts only @ $85 | +621% | +132% | +532% | +1,577% | $14,812 |
| **Stock-heavy** 3 x $40 + 1 x 25/75 spread + 1 x $75 + 253 shares | Hold | +452% | +45% | +402% | +1,190% | $10,928 |
| | Sell half @ $85 | +395% | +98% | +402% | +821% | $9,819 |
| | 50% ATM puts only @ $85 | +442% | +145% | +387% | +1,027% | $10,516 |

## Sensitivities

- **Put IV.** With the Rule 2 shift, E for 50% ATM puts only @ $85 on the return-heavy Jan 2029 build is +622% (flat +604%); with flat plus 10 points it is +592%. Across the three assumptions, expected return differs by up to about 30 points (return-heavy, sell half plus 50% ATM puts: +554% with Rule 2, +548% flat, +523% with flat plus 10) and by 20 or less on the puts-only rows; the order of the policies does not change.
- **Debt share.** At 10% the return-heavy hold build has E +702% and 50% gives +590% (25%: +674%); the half-sale rows move the same way. Larger debt shares lift the bear-mix return because the money leaves the account at a higher price.
- **Not run.** Flat IV for the calls (the earlier runs showed it moves expected returns by 13 points or less and changes no ranking); a $103 trigger evaluated between the two sale dates.

## What it shows

1. **Beating the stock by 200 points is easy for a call and hard for a portfolio.** Every Jan 2029 call except the $15 clears 200 points. The finished portfolio clears it only at the heaviest return-book weight: in the base case the return-heavy build (60% in $40 and $90 calls) returns +624% against the stock's +425%, +199 points; the balanced build gains +71, the barbell-heavy +41, the stock-heavy +24. The 200-point gap at the portfolio level costs bear return: +36% against the stock's +76% and, on the straight bear path, -3% against +60%.
2. **Selling half at $85 does what you described, at a price.** On the four round trips the return-heavy build goes from a range of 0% to +109% (hold) to +114% to +186% (sell half), and the balanced build from +59% to +149% to +163% to +219%. It costs the paths where the stock keeps rising, because $85 is reached on the way to $103 and $164: expected return falls 104 points (return-heavy) and 75 (balanced), the base case from +624% to +577%, the bull from +1,904% to +1,342%. Bear return rises 83 and 76 points.
3. **Puts and the half-sale cost about the same per point of bear return; neither dominates.** Return-heavy: puts only (50% ATM) keeps 34 more points of E than the half-sale alone (+604% against +570%) and gives up 6 points of bear return. Balanced: puts only keeps 17 more points of E and gives up 26 points of bear. Adding 50% ATM puts to the half-sale costs 22 and 13 points of E for 29 and 12 points of bear. The half-sale is certain; the puts depend on the model's pricing of puts you have not yet bought, at strikes not yet listed.
4. **The $103 trigger looks nearly free, but that is an artefact.** It is checked only on June 30 and November 30, so it cannot fire on the straight base path, which reaches $103 on December 31. It fires on the round trips peaking at $103 and on the straight bull. Do not read E +670% against +674% as the cost of selling half at $103.
5. **The debt rule gives you little money exactly when you may need it.** Because it takes a share of the gain, it pays $262 to $1,093 (balanced) or $0 to $443 (return-heavy) on the straight bear and the two June-peak round trips. It pays $6,700 to $20,700 (balanced build) on the straight base, the straight bull and the two November-peak round trips. If the debt is a fixed dollar amount, shares have to cover the difference on the weak paths, which the engine does not do (it withdraws the percentage only).
6. **Round trips peaking in November coincide with the debt date.** At $85 or $103 on 2027-11-30 the account is worth the most, and the debt withdrawal takes its share at that high price. That helps those two paths regardless of policy.
7. **Jan 2028 options (programme 27) show the same shape with less room.** No call passes the test strictly. Admitting the $40 near-miss, the return-heavy build holds at +628% with a bear of +7%; selling half at $85 takes the bear to +142% for -88 points of E; 50% ATM puts only keeps +621% and +132%.

## Caveats

- **Small lots.** The builds hold one to seven contracts per sleeve, and "sell half" rounds up, so a one-contract sleeve is sold whole. That strengthens the half-sale on small sleeves.
- **Paths are stylised.** Two knots and geometric interpolation; the date grid is only June 30 and November 30, 2027. Round-trip falls are harsher than the data (above).
- **Bear is not a loss case.** The thesis bear ($32, $46) is above today's $25.70, so a build with a positive bear return has not been tested against a fall below spot. The owner asked for no downside rows.
- **Puts are proxies.** Listed Jan 2028 and Jan 2029 strikes (the Jan 2029 chain stops at $90, 13% below $103). Cost is model value plus half of today's quoted spread, capped at 5%.
- **Banked cash earns nothing and is counted.** Half-sale proceeds fund puts and the debt first; the rest sits in wealth.
- **E is dominated by the bull path** (20% weight, up to +2,004% on the return-heavy build), so compare the Bear and Base columns as well.
- **Spot moved** from $25.81 in the first run, to $25.36, to $25.70 here; the documents differ slightly. Quotes are one snapshot, entry at the ask and bid, no exit slippage. Tax is not modelled.

## Changes

- 0.1, 2026-10-26: first results.
