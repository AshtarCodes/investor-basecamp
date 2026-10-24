# Pricing engine

A standalone `uv` project: QuantLib and pydantic v2, Python 3.13. [ADR 0001](../../docs/adr/0001-own-pricing-model.md) sets the model and [ADR 0007](../../docs/adr/0007-pricing-engine-is-a-python-worker.md) sets where it runs. Only `treasury.py` does I/O (the network, and an optional disk cache); everything else is pure. Use the terms in `GLOSSARY.md`: Mark, Mark-implied IV, Settlement instant, Remaining life.

## Tooling

- Ruff lints and formats, pytest tests, and **ty** type checks. ty was chosen because it ships from the same vendor as Ruff and `uv`, runs in milliseconds, and reads `pyproject.toml`. QuantLib has no type hints, so ty covers our code only.
- `package.json` only wraps `uv run`: `lint`, `format`, `format:check`, `typecheck`, `test`, `schema`, `bench`. Run them as `pnpm --filter pricing-engine <script>`. pnpm manages no Python dependencies; add them with `uv add`.
- Lefthook runs Ruff on staged `*.py` at commit, and ty and pytest at push.

## Shape

- `price(PriceRequest) -> PriceResult` in `pricer.py` is the one entry point. It prices at a known σ, or solves the Mark-implied IV from a Mark and prices at that. `settlement_instant`, `parity_forward`, `parse_curve`, `TreasuryCurves` and `project_dividends` are the other public names.
- `treasury.py` and `dividends.py` build the rate and dividend inputs; the callers (the CLI and the app) map Schwab payloads into their arguments. `TreasuryCurves.rate` returns a `RateQuote` (a `Sourced` rate plus the curve date): the Treasury.gov par curve as continuous rates, linear in tenor and flat past the ends, or the caller's Schwab-chain fallback flagged `schwab-chain-fallback`. `project_dividends` returns a rule name and the cash dividends. A stale quarterly `nextDivExDate` rolls forward, `divFreq` 0 with a yield asks the caller for a continuous yield (SATA pays daily), and other frequencies are `unsupported-frequency`.
- `models.py` holds the pydantic request and result models. Every numeric input (spot, rate, σ, Mark, yield, borrow rate, forward) is a `Sourced` value, a number with a `from` provenance string, and each cash dividend carries its own `from`. The result echoes them.
- `schema/*.json` is the committed JSON Schema the server generates its TypeScript types from. After changing `models.py` run `pnpm --filter pricing-engine schema`; a test fails while the committed files are stale.
- `problem.py` is one resolved problem in years from the valuation moment. `model.py` picks the model and values it. Greeks (`greeks.py`) and IV (`iv.py`) reprice through `model.value`, so they share its code path.

## Rules of the model

- Time is calendar seconds over a 365-day year, from the valuation moment to the Settlement instant, measured in UTC so daylight saving counts.
- European prices are closed-form at the exact fractional T. American finite-difference and tree prices run on a virtual clock (`clock.py`): true time maps onto `clock_days` whole QuantLib days, with σ, r, the yield and dividend days rescaled so σ²T, rT and r/σ² are unchanged. Do not use QuantLib's real calendar for intraday time.
- QuantLib's evaluation date is global. `american.py` sets it once to a fixed date; nothing else may change it.
- A cash dividend drops the spot at 09:30 America/New_York on its ex-date. One at or before the valuation moment, or at or after the Settlement instant, is ignored and flagged `dividend_not_in_life`.
- `settlement_instant` accepts SPX (09:30), SPXW and XSP (16:00), and any equity-shaped OCC root (16:00). Other index roots (NDX, RUT, VIX and so on) are errors until their settlement rules are modelled. Never default an unrecognised root.
- A call on a non-dividend payer with no borrow cost and a non-negative rate takes the closed form. Anything else American takes the finite-difference cash-drop model.
- An explicit forward moves with spot when spot is bumped (so delta is per share of spot); rho and theta hold it fixed, so rho moves only the discount factor.
- Units: vega per vol point, theta per calendar day, rho per percentage point of rate. σ and rates are decimals.

## Against Schwab's values

Do not expect our IV to equal Schwab's. On two long-dated IREN calls (no dividends) the Greeks agreed within about 1%, but Schwab's IV was 0.7 to 0.8 vol point higher for the same Mark, and the cause is unknown. Because every base value is solved from the Mark, this moves Shock P/L by only about 0.2% to 2% of the largest Shock P/L.

**Short-dated, low-priced options are noisier.** A gap of about a day is a large share of a 3 to 7 day life, and a few cents is a large share of a small Mark: on a 7-day put the gap was 56% of its Mark but about 2% of its worst Shock P/L. Treat per-contract IV and per-contract Shock P/L on those options as less reliable, and do not compare them to Schwab's figures to the cent. Dividend-paying American options are untested and expected to differ more. Evidence and method: `docs/research/pricing-engine-vs-schwab-iren.md`.

## Tests

Test at the public functions only, against independent oracles: Haug's tabulated values, a closed-form Black-Scholes-Merton written in `tests/support.py`, a 4,000-step CRR tree, and QuantLib's own engine values. No test uses the network: `TreasuryCurves` takes a fetch function and the tests pass saved Treasury.gov months from `tests/fixtures/`. `bench/grid.py` is the 50 Position by 100 Shock timing script, not a test.

## Treasury.gov

The XML feed is keyless but holds a request whose `User-Agent` is a stock client's (urllib's, curl's) for about 18 s, and answers one that names itself in 0.2 s. `fetch_month` sets its own.

## Docs

QuantLib-Python: https://quantlib-python-docs.readthedocs.io/
pydantic: https://pydantic.dev/docs/validation/latest/llms.txt
uv: https://docs.astral.sh/uv/llms.txt
ty: https://docs.astral.sh/ty/
Ruff: https://docs.astral.sh/ruff/
