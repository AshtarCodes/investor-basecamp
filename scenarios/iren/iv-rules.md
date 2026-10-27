# IREN IV rules for scenarios

**Version 0.2, 2026-10-26.** Proposed, not tested. Rules change as evidence arrives; bump the version and add a line under "Changes" when one does.

## What these rules are for

A scenario run (`sell --as-of <date> --expected-spot <S>`) needs an exit IV. The tool's default holds each contract's Mark-implied IV flat, which is the baseline. These rules say how to move the IV with the stock when stress-testing a buy decision. The evidence column says what each rule rests on; most rest on assumption, because there is no IREN IV history yet (see "Evidence status").

## Rule 0: the starting point

Start from the contract's own Mark-implied IV (`inputs.vol.value` in `schwab option price` output), never Schwab's API `volatility` field. It reproduces the Mark, matches TOS, and the API's IV sits 2 to 8 vol points above it. Today's values: Jan 2028 $40 about 93%, Jan 2029 $40 about 88%.

## Rule 1: flat IV (baseline, always run it)

IV shift 0 at every spot. This is what the tool does by default.

## Rule 2: IV moves against the stock (proposed)

Shift the IV, in vol points added to the starting IV, by the spot move to the exit:

| IREN spot move to exit | IV shift (vol points) |
| --- | --- |
| -40% or worse | +15 |
| -20% | +8 |
| 0% | 0 |
| +20% | -5 |
| +50% | -10 |
| +100% or more | -15 |

Interpolate linearly between rows. Hold the result between a floor of 60% and a cap of 130%.

- **Why this shape.** A stock that falls is usually priced for more fear, a stock that rallies for less. The one thing measured is the VIX link: IREN's daily return has a correlation of -0.42 with the VIX's change, and the fear-driven leg (Jan-Mar, VIX 16.4 to 30.6) was a -50% decline.
- **Why this size.** Not measured. The sizes are an assumption chosen to be larger than the 2-to-8-point gap between our IV and the API's, so the test is not trivially small, and smaller than the 71% to 114% range of realized volatility by leg.
- **Floor and cap.** The lowest realized volatility of any leg was 71% (the latest), and the year's was 106%; 60% to 130% brackets both. The year before (to 2025-10-22) had realized volatility of 98% to 102% over the full year and the last 10, 30 and 60 days, so the same bracket holds for it.
- **Beyond +100%.** The row stays at -15 for any rally past +100%, so at +200% the shift is still -15 (Jan 2028 $40: about 93% to 78%, above the floor).
- **Evidence status: assumption.** What would change it: a daily snapshot of IREN's Mark-implied IV against its spot over a few weeks (see the open questions in the observations), or a historical IV source.

## Rule 3: IV that does not follow the VIX level

Do not tie IREN's IV to the VIX level. Two of the four tank legs ran at a calm VIX (17.5 and 16.3), and the average VIX was only 2 points higher in tanks (18.9) than in rallies (17.0). A VIX move is informative about direction (see Rule 2), not about IREN's IV level.

- **Evidence status: measured, two years.** The year before (to 2025-10-22) gave the same sign: average VIX 18.5 in rally legs and 19.9 in tank legs, a 1.4-point gap against 1.9 in the 2026 year. What would change it: a different leg threshold giving a different gap.

## Rule 4: the spot range to test

Test a range, not a point: -50%, -30%, -15%, flat, +25%, +50%, +100%, +200% from the entry spot. In the 2026 year legs ran -57% to +115% in 1 to 2 months, and 39 of 251 days moved more than 10%. The +200% row is a tail case for exits of 3 months or more: in the 2025 year the stock rose +220% in 60 days off the April trough, +1212% in 130 days.

- **Evidence status: measured, two years.** The year before (2024-10-23 to 2025-10-22, see [observations](observations.md)) ran +61% in 7 days and +1212% in 130 days, so +100% was not an upper bound and the top is now +200%. The bottom is unchanged but is not a floor either: the deepest legs were -57% (2026 year) and -59.5% (April 2025), 37 trading days in the latter.

The thesis cases in [thesis.md](thesis.md) are separate from this measured range: they are the owner's view, and some of their targets (for example $103 to $343 per share against a $26.49 spot) sit past the +200% row. Run them as labeled thesis scenarios, not as part of this range.

## Rule 5: time

Test exits at 1 month, 3 months, 6 months and 1 year. Hold each contract's IV (after any Rule 2 shift) constant to the exit; the tool does not model the term structure rolling.

## How to run a rule with the tool today

The CLI has no `--iv-shift` flag (the engine supports one; a flag is not built). Use `--vol`:

1. Run `pnpm schwab option price --symbol '<OCC>'` and read `inputs.vol.value` (the Mark-implied IV, in percent).
2. Add the rule's shift and run `pnpm schwab option price --symbol '<OCC>' --mode sell --as-of <date> --expected-spot <S> --vol <IV + shift> --entry <your fill> --contracts <n>`.

`--vol` replaces the Mark-implied IV for that run, which is what a shifted-IV scenario wants. For a spread, run both legs at the same exit spot and date and net them (short leg P/L is the credit minus the buyback).

## Evidence status

| Rule | Basis |
| --- | --- |
| 0 | Measured (TOS match; model matches Schwab's own formula at the API IV) |
| 1 | Definition |
| 2 | Assumption, partly motivated by the measured VIX link |
| 3 | Measured, two years, 8 + 10 legs |
| 4 | Measured, two years |
| 5 | Convention; term structure unmeasured |

## Changes

- 0.2, 2026-10-26: Rule 4's top of range widened from +100% to +200% after the 2025 year (+61% in 7 days, +1212% in 130 days). Rule 3 and the Rule 2 floor/cap now note the 2025 year agrees. Rule 2's shifts are unchanged: still no IV history.
- 0.1, 2026-10-26: first proposal, from one year of IREN and VIX daily closes and the Jan 2028 and Jan 2029 quotes in `observations.md`.
