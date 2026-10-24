# Engine inputs: Treasury rate and dividend schedule

Type: task
Status: ready-for-agent

Blocked by: [16](16-pricing-engine-package.md) (needs the package scaffold and the inputs model)

## Goal

Add the two input builders the engine and the CLI need so every price names a rate and a dividend treatment: a Treasury.gov rate for an expiry, and a dated dividend schedule projected from Schwab's dividend fields. Both live in `packages/pricing-engine/`. Only the Treasury module touches the network.

## Rate

- Fetch the Treasury.gov daily par yield curve XML for the month (`https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month=YYYYMM`), keyless. Use the latest published date, so a weekend or holiday run uses the last trading day, and fall back to the previous month's file when the current month has no entries yet.
- Convert each bond-equivalent par yield to a continuous rate with `2·ln(1 + y/2)`. Interpolate linearly on tenor in years, with flat extrapolation outside the quoted tenors.
- Return the rate with provenance: `{ "value": ..., "from": "treasury-gov", "curveDate": "YYYY-MM-DD" }`.
- Failure (network, parse, empty month) returns an error the caller can turn into a fallback. The caller passes the fallback rate (Schwab's chain `interestRate`, in percent) and the result is flagged `from: "schwab-chain-fallback"`.
- Cache a fetched month in memory, and optionally on disk at a path the caller supplies, for a day.

## Dividends

A pure function from `nextDivExDate`, `divPayAmount`, `divFreq` and the expiry (all as Schwab's `fundamental` block reports them; see [docs/schwab/observations.md](../../../docs/schwab/observations.md)) to a dated cash dividend list plus the name of the projection rule.

| Quote | Result |
| --- | --- |
| `divFreq` 4 and a next ex-date | Every 3 months from `nextDivExDate` through the expiry, each `divPayAmount`. Rule: `quarterly-from-next-ex-date`. |
| `divFreq` 0 and `divYield` above 0 (SATA's case) | No schedule. The result says `needs-continuous-yield`; the caller passes `divYield` (percent) as the continuous yield, with a warning. |
| All dividend fields zero | Empty schedule, rule `none`. |
| Next ex-date after the expiry | Empty schedule, rule `none-before-expiry`. |

Other frequencies (1, 2, 12) are out of scope until a held name needs them; return `unsupported-frequency` rather than guess.

## Acceptance

- Rate at an exact quoted tenor equals the converted yield to 1e-9. Using the saved 2026-10-23 curve (1 month 4.11, 3 months 4.22, 6 months 4.30, 1 year 4.44), the 3-month rate is `2·ln(1.0211)`.
- Rate between tenors is linear, and flat outside them (a 2-week expiry uses the 1-month rate).
- The fixture is a saved copy of the 2026-10 XML; no test needs the network. A separate test covers the empty-month fallback with a fixture whose month has no entries.
- SPY-shaped quote (`divFreq` 4, ex-date 2026-12-18, pay amount 1.88883) and an expiry of 2027-06-30 gives three dated dividends: 2026-12-18, 2027-03-18 and 2027-06-18.
- SATA-shaped quote returns `needs-continuous-yield`; IREN-shaped (all zero) returns `none`.
- An American put priced with the SPY-shaped schedule is worth more than the same put with no dividends.

## Out of scope

- Mapping Schwab payloads into these arguments (done by the callers: [14](14-schwab-option-price-cli.md) and the app); discrete dividends other than quarterly; borrow rates (an input in [16](16-pricing-engine-package.md), defaulting to 0).
