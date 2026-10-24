# The pricing engine is a standalone Python project, run by the server as a long-lived worker

[ADR 0001](0001-own-pricing-model.md) sets the model. This sets where it lives and runs. The engine is its own `uv` project in `packages/pricing-engine/`, built on QuantLib, with its own ruff, type checker and pytest setup. The `schwab` CLI imports it as a `uv` path dependency. The server starts it once as a worker process and sends it JSON lines, so QuantLib is imported once and not per request. Scenario values are already server-side functions ([ADR 0005](0005-scenario-controls-are-webmcp-tools.md)), so nothing prices in the browser. A TypeScript engine would have meant writing the cash-drop finite-difference solver ADR 0001 prefers, the IV solving, and the calibration work of issue 12 ourselves, and Python already has them.

Evidence is two spikes on this Mac (branch `prototype/quantlib-engine`). QuantLib 1.44 installs with `uv add` in 1.3 s and imports in 0.05 s warm. Its American finite-difference engine takes each dividend as a cash drop and matched Black-Scholes-Merton to a tenth of a cent on a call with no dividends. Mark-implied IV solved in 11 to 19 ms. The 50-Position by 100-Shock grid took 2.2 s single-threaded at a 100 by 200 grid, 0.8 s at 50 by 100 with no loss of accuracy, and 0.30 s in a 14-process pool.

## Layout

- `packages/pricing-engine/` is a standalone `uv` project with its own `pyproject.toml`, ruff, pytest and a type checker. The type checker is ty ([ticket 16](../../.scratch/portfolio-risk-wayfinding/issues/16-pricing-engine-package.md)). QuantLib ships without type hints, so the checker covers only our code.
- A thin `package.json` there wraps lint, format check, type check and test as scripts. The pnpm workspace (`packages:` in `pnpm-workspace.yaml`) lets `pnpm -r` and Lefthook run them. pnpm manages no Python dependencies.
- `tools/schwab` depends on the engine by path: `pricing-engine = { path = "../../packages/pricing-engine", editable = true }`.
- The TS server never imports Python. It spawns `uv run --project packages/pricing-engine pricing-worker`.
- Input and output are pydantic v2 models. Their JSON Schema is the contract, and the server generates its TS types from it.

## Time

QuantLib's dates are whole days, but ADR 0001 needs calendar minutes to the settlement instant (4:00 pm ET, or 9:30 am ET for AM-settled SPX). The engine uses a virtual clock: true time `[0, T]` is mapped onto 3,650 whole days, and σ, r and each dividend time are rescaled so that σ²T, rT and r/σ² are unchanged. European prices matched closed-form Black-Scholes-Merton at the exact T to 3e-14 from 3.5 hours to 2 years. American finite-difference prices landed within 0.04 cent of a 4,000-step tree at 400 by 800 and within 0.1 cent at 100 by 200. Prices stayed within 0.02 cent as the virtual clock grew tenfold.

## Considered Options

- **TypeScript engine, in the browser or on the server.** It works, but we would own the solver, and the browser was only an assumption of the first research pass.
- **Hybrid.** TypeScript pricing in the app and Python for the CLI would price the same Position twice with different code, which defeats ADR 0001.
- **A `uv` workspace with a root `pyproject.toml`.** One lockfile and one venv, but a Python file at the root of a TypeScript repo that editors may pick up as a Python project. With two Python projects, a path dependency is lighter and easy to swap.

## Consequences

- American options use the QuantLib finite-difference cash-drop model. The Leisen-Reimer tree on spot minus the present value of dividends stays as a cross-check and fallback. In the first spike it landed about 3 cents either side of the cash-drop price, depending on step count.
- Python and TypeScript have separate toolchains. Knip, Oxlint and Vitest do not see the engine. Knip handles the engine's `package.json` with no JS sources without extra config beyond `ignoreBinaries: ["uv"]`.
- **Open: the worker protocol.** The JSON round-trip, restart behavior, and worker pool size are unmeasured; [ticket 18](../../.scratch/portfolio-risk-wayfinding/issues/18-engine-worker.md) measures them.
- **Untested:** European index options on a put-call-parity forward, VIX options with Black-76, and Shocks that move the valuation date past a dividend.
