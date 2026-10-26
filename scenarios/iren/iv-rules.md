# IREN IV rules for scenarios

**Version 0.1, 2026-10-26.** Proposed, not tested. Rules change as evidence arrives; bump the version and add a line under "Changes" when one does.

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
- **Floor and cap.** The lowest realized volatility of any leg was 71% (the latest), and the year's was 106%; 60% to 130% brackets both.
- **Evidence status: assumption.** What would change it: a daily snapshot of IREN's Mark-implied IV against its spot over a few weeks (see the open questions in the observations), or a historical IV source.

## Rule 3: IV that does not follow the VIX level

Do not tie IREN's IV to the VIX level. Two of the four tank legs ran at a calm VIX (17.5 and 16.3), and the average VIX was only 2 points higher in tanks (18.9) than in rallies (17.0). A VIX move is informative about direction (see Rule 2), not about IREN's IV level.

- **Evidence status: measured, one year.** What would change it: a longer history or a different leg threshold giving a different gap.

## Rule 4: the spot range to test

Test a range, not a point: -50%, -30%, -15%, flat, +25%, +50%, +100% from the entry spot. Legs ran -57% to +115% in 1 to 2 months, and 39 of 251 days moved more than 10%.

- **Evidence status: measured, one year.**

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
| 3 | Measured, one year, 8 legs |
| 4 | Measured, one year |
| 5 | Convention; term structure unmeasured |

## Changes

- 0.1, 2026-10-26: first proposal, from one year of IREN and VIX daily closes and the Jan 2028 and Jan 2029 quotes in `observations.md`.
