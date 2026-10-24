# Pricing engine package (`packages/pricing-engine`)

Type: task
Status: ready-for-agent

Blocked by: none (builds on [06](06-pricing-inputs-and-models.md), [ADR 0001](../../../docs/adr/0001-own-pricing-model.md) and [ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md))

## Goal

Build the one pricing engine that the app's server and the `schwab` CLI ([14](14-schwab-option-price-cli.md)) both use, as a standalone Python project with its own tooling. Every price names its inputs; nothing in the engine reads the network except the Treasury module.

## Layout (from ADR 0007)

- `packages/pricing-engine/` is a standalone `uv` project: its own `pyproject.toml`, ruff (lint and format), pytest, and a type checker. **Choose the type checker here** (ty, pyright or mypy). QuantLib has no type hints, so it covers our code only.
- A thin `package.json` wraps `lint`, `format:check`, `typecheck` and `test` as scripts that run through `uv run`. Add `packages:` to `pnpm-workspace.yaml` so `pnpm -r` reaches it. pnpm manages no Python dependencies.
- Lefthook: ruff on staged `*.py` at commit; type check and pytest at push, beside the existing jobs. Check that Knip copes with a `package.json` that has no JS sources and fix its config if not.
- `tools/schwab` depends on the engine by path: `pricing-engine = { path = "../../packages/pricing-engine", editable = true }`. The CLI imports it directly; the server spawns `uv run --project packages/pricing-engine pricing-worker`.
- Add `packages/pricing-engine/AGENTS.md` and list it under "Read next" in the root `AGENTS.md`.
- Input and output are pydantic v2 models. Their JSON Schema is the contract, and the server generates its TS types from it.

## Scope

1. **Virtual clock.** Convert calendar minutes to the **Settlement instant** (4:00 pm ET; 9:30 am ET for AM-settled SPX) into a 3,650-day virtual clock and rescale σ, r and dividend times: `σ' = σ√(T/T_ql)`, `r' = r·T/T_ql`, dividend day = `round(t_d/T · N)`. Reference: `tools/schwab/prototype/quantlib-engine/spike_intraday.py` on branch `prototype/quantlib-engine`.
2. **European** pricing: Black-Scholes-Merton, and index options on the forward implied by put-call parity at each expiry ([ADR 0001](../../../docs/adr/0001-own-pricing-model.md)). VIX options (Black-76) are out of scope.
3. **American** pricing: QuantLib `FdBlackScholesVanillaEngine` with each dividend as a cash drop. A call on a non-dividend payer with no borrow cost uses the closed form. Default grid 100 by 200 for single prices; 50 by 100 is acceptable for the Shock grid. Include the Leisen–Reimer tree on spot minus the present value of dividends (odd step count, about 101 to 201) as a cross-check.
4. **Mark-implied IV** solved from a **Mark** through the model (Brent), with the no-IV flag when the mark is at or below intrinsic.
5. **Greeks:** delta, gamma, vega (per vol point), theta, rho. Use bump-and-reprice for all of them so they come from one code path, and test delta, gamma and theta against the engine's own values.
6. **Rate input:** Treasury.gov daily par curve (XML, keyless), interpolated to the expiry and converted to continuous compounding. Provenance `treasury-gov` with the curve date. On failure, fall back to a rate the caller passes in and flag it.
7. **Dividend schedule:** a pure function from `nextDivExDate`, `divPayAmount`, `divFreq` and the expiry to a list of dated cash dividends, projecting every 3 months when `divFreq` is 4 and naming the projection rule in its result. Callers do the Schwab field mapping.
8. **Worker:** `pricing-worker` reads JSON lines on stdin and writes one JSON line per request on stdout, with request ids, structured errors, and a warm-up on start. Decide and document the worker pool size and restart behavior from measurement.

## Acceptance

From the spikes (`tools/schwab/prototype/quantlib-engine/VERDICT.md`):

- Haug's Black-Scholes-Merton table value 2.1334 (S=60, K=65, T=0.25, r=8%, σ=30%) to four decimals.
- European prices equal closed-form Black-Scholes-Merton at the exact fractional T to 1e-9, for T from 3.5 hours to 2 years.
- American, no dividends, equals a 4,000-step CRR tree at the exact T within 0.1 cent at 100 by 200 and within 0.05 cent at 400 by 800, for T of 3.5 hours, 1.5 days and 30 days.
- American with two cash dividends is stable to 0.05 cent as the virtual clock grows from 730 to 36,500 days.
- Mark-implied IV recovers the generating σ to 1e-4 vol points on both fixtures (a 103% call and a dividend-paying in-the-money put).
- The 50-Position by 100-Shock grid completes in under 1 s on this laptop through the worker (benchmark, not a unit test).
- Offline: no test needs the network. The Treasury module is tested against a saved XML fixture.

## Out of scope

- Black-76 for VIX options; sticky-delta IV shifts; historical calibration ([12](12-can-historical-data-calibrate-shocks.md)); how the app schedules Shock grids; the CLI ([14](14-schwab-option-price-cli.md)).

## Open decisions

- Type checker (ty, pyright or mypy): implementer choice, record it in the package `AGENTS.md`.
- Worker pool size and restart behavior: from measurement.
- Untested in the spikes: European index options on a parity forward, and Shocks that move the valuation date past a dividend. Add fixtures for both.
