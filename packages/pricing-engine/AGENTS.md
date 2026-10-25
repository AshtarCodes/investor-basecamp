# Pricing engine

A standalone `uv` project: QuantLib and pydantic v2, Python 3.13. [ADR 0001](../../docs/adr/0001-own-pricing-model.md) sets the model and [ADR 0007](../../docs/adr/0007-pricing-engine-is-a-python-worker.md) sets where it runs. Only `treasury.py` (the network, and an optional disk cache) and the worker (`worker.py` and `pool.py`: stdin, stdout, stderr and child processes) do I/O; everything else is pure. Use the terms in `GLOSSARY.md`: Mark, Mark-implied IV, Settlement instant, Remaining life.

## Tooling

- Ruff lints and formats, pytest tests, and **ty** type checks. ty was chosen because it ships from the same vendor as Ruff and `uv`, runs in milliseconds, and reads `pyproject.toml`. QuantLib has no type hints, so ty covers our code only.
- `package.json` only wraps `uv run`: `lint`, `format`, `format:check`, `typecheck`, `test`, `schema`, `bench`. Run them as `pnpm --filter pricing-engine <script>`. pnpm manages no Python dependencies; add them with `uv add`.
- Lefthook runs Ruff on staged `*.py` at commit, and ty and pytest at push.

## Shape

- `price(PriceRequest) -> PriceResult` in `pricer.py` is the one entry point. It prices at a known σ, or solves the Mark-implied IV from a Mark and prices at that. `settlement_instant`, `parity_forward`, `parse_curve`, `TreasuryCurves` and `project_dividends` are the other public names.
- `treasury.py` and `dividends.py` build the rate and dividend inputs; the callers (the CLI and the app) map Schwab payloads into their arguments. `TreasuryCurves.rate` returns a `RateQuote` (a `Sourced` rate plus the curve date): the Treasury.gov par curve as continuous rates, linear in tenor and flat past the ends, or the caller's Schwab-chain fallback flagged `schwab-chain-fallback`. `project_dividends` returns a rule name and the cash dividends. A stale quarterly `nextDivExDate` rolls forward, `divFreq` 0 with a yield asks the caller for a continuous yield (SATA pays daily), and other frequencies are `unsupported-frequency`.
- `models.py` holds the pydantic request and result models. Every numeric input (spot, rate, σ, Mark, yield, borrow rate, forward) is a `Sourced` value, a number with a `from` provenance string, and each cash dividend carries its own `from`. The result echoes them.
- `schema/*.json` is the committed JSON Schema the server generates its TypeScript types from. After changing `models.py`, `batch.py`, `protocol.py` or `errors.py` run `pnpm --filter pricing-engine schema`; a test fails while the committed files are stale.
- `batch.py` prices a contract over a list of Shocks, `protocol.py` holds the worker's request and response lines, `pool.py` the warm process pool, and `worker.py` the loop. See "The worker".
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

## The worker

`pricing-worker` (`worker.py`) is the process the server spawns, as `uv run --project packages/pricing-engine pricing-worker` ([ADR 0007](../../docs/adr/0007-pricing-engine-is-a-python-worker.md)). It reads one JSON request per line on stdin and writes one JSON response per line on stdout, handling one request at a time, in order. Diagnostics go to stderr. The protocol has its own file descriptor and fd 1 points at stderr, so a stray `print` or QuantLib's C++ output cannot corrupt a response line.

**Try it by hand.** The first line out is `{"type":"ready","pid":…,"workers":4,"protocol":1}`, printed once this process and every pool process have priced a throwaway option (about 0.6 s). Then paste a request:

```sh
uv run pricing-worker --workers 2
{"id":"1","type":"price","contract":{"root":"SPY","expiry":"2026-12-18","strike":100,"right":"call","exercise":"european"},"valuation":"2026-10-26T14:00:00Z","spot":{"value":100,"from":"by hand"},"rate":{"value":0.04,"from":"by hand"},"volatility":{"value":0.3,"from":"by hand"}}
```

Ctrl-D (stdin close) or SIGTERM ends it with exit code 0. `uv run` forwards SIGTERM to the worker, which exits in under 0.1 s and takes the pool with it.

**Requests.** `schema/worker-request.schema.json` and `schema/worker-response.schema.json` are the contract, a discriminated union on `type`. Every request has an `id`, a string or an integer (not a boolean or a float, which are refused), that the response echoes.

- `price` is a `PriceRequest` with `id` and `type` beside its fields. It runs in the worker's own process and answers with a `PriceResult`.
- `batch` is `{id, type, iv_shift_mode, numerics?, contracts: [{request, shocks: [{spot_move, iv_shift, days_forward}]}]}`. Each `request` carries a Mark (not a volatility). The contracts fan out to the pool, one contract per task, and the answer is `{contracts: [...]}` in the same order. `numerics` defaults to 50 by 100 and replaces each request's own.

**What a batch does** (ADR 0001, ticket 07). The Mark-implied IV is solved once per contract, at the batch's `numerics`, so a zero Shock reproduces the Mark. Then each Shock moves spot by the `spot_move` fraction (an explicit forward moves with it), shifts the contract's own IV (`iv_shift` is a decimal in vol points in `absolute` mode, a fraction of the IV in `proportional` mode, floored at 1 vol point), and moves the valuation forward `days_forward` calendar days. A contract that expires inside the horizon is intrinsic at the shocked price and flagged `expired`. Where there is no IV, a Shock is the model value at the 1 vol point floor plus the residual (so a zero Shock is worth the Mark), the IV Shift is ignored, and the price is not below zero. A Shock past expiry is plain intrinsic, with no residual. `spot_move` must be above -1, and `iv_shift` and `spot_move` finite; `days_forward` is 0 to 36,500. Prices are per share: quantity, the 100 multiplier, beta weighting, Shock P/L and Loss Thresholds stay with the caller.

A contract's entry is `{ok: true, iv, flags, prices, shock_flags}` or `{ok: false, error}`. `prices[i]` is the price under `shocks[i]`; `shock_flags` lists only flagged Shocks, by index.

**Errors.** A response is `{id, ok: true, result}` or `{id, ok: false, error: {code, message}}`, with `id: null` when the line had no readable id. Codes: `invalid_json`, `invalid_request` (the message names the field path, such as `contracts.0`), `unknown_type`, `model_error` (an unsupported root such as NDX) and `internal`. None of them ends the worker. A Mark at or below intrinsic is a result, not an error: `price: null`, `iv.reason` and `iv.residual`, and in a batch the residual carry above. In a batch, a contract that fails gets its own error entry and the rest still price; only a batch-level failure uses the top-level error.

**If the worker dies mid-request, retry once.** The worker never retries on its own, because a contract that crashes QuantLib will do it again. If a pool process dies (a QuantLib crash, an OOM kill), the worker replaces the whole pool and answers the request in flight with `internal`; the next request is served. If the replacement itself fails, the worker keeps serving and starts the pool again on the next batch. A caller that gets `internal`, or finds the worker gone, restarts it if needed and retries the request once. A second failure is the request's fault.

### Pool size

The pool is `DEFAULT_WORKERS = 4` processes, started eagerly and kept warm. Set it with, in order of precedence, `--workers N`, the `PRICING_WORKERS` environment variable, then the constant in `worker.py`. A value that is not a positive integer exits with code 2 and a message on stderr before the ready line. The ready line reports the size in use.

Each process costs about 110 MB and an idle one uses no CPU. Measured on a 14-core Mac (10 performance and 4 efficiency cores) through the spawned worker with the Mark-implied IV solved for every contract, `uv run python bench/worker.py --workers N` (`pnpm --filter pricing-engine bench:worker`):

| Pool size | Ready line | First price (100 by 200) | 50 x 100 batch | Resident memory |
| --- | --- | --- | --- | --- |
| 2 | 0.55 s | 10.6 ms | 0.41 s | about 360 MB |
| 4 (default) | 0.58 s | 11.3 ms | 0.21 s | about 590 MB |
| 8 | 0.63 s | 10.5 ms | 0.12 s | about 1.0 GB |
| 14 | 0.78 s | 11.1 ms | 0.11 s | about 1.7 GB |

Past 8 the batch barely speeds up, so raise the size only if the batch bar (under 1 s for 50 Positions by 100 Shocks) is missed on slower hardware, and lower it on a small machine. `ps` overstates memory, since it counts shared pages in every process. The batch time runs from writing the request line to reading the response line.

## Against Schwab's values

Do not expect our IV to equal Schwab's. On two long-dated IREN calls (no dividends) the Greeks agreed within about 1%, but Schwab's IV was 0.7 to 0.8 vol point higher for the same Mark, and the cause is unknown. Because every base value is solved from the Mark, this moves Shock P/L by only about 0.2% to 2% of the largest Shock P/L.

**Short-dated, low-priced options are noisier.** A gap of about a day is a large share of a 3 to 7 day life, and a few cents is a large share of a small Mark: on a 7-day put the gap was 56% of its Mark but about 2% of its worst Shock P/L. Treat per-contract IV and per-contract Shock P/L on those options as less reliable, and do not compare them to Schwab's figures to the cent. Dividend-paying American options are untested and expected to differ more. Evidence and method: `docs/research/pricing-engine-vs-schwab-iren.md`.

## Tests

Test at the public functions only, against independent oracles: Haug's tabulated values, a closed-form Black-Scholes-Merton written in `tests/support.py`, a 4,000-step CRR tree, and QuantLib's own engine values. No test uses the network: `TreasuryCurves` takes a fetch function and the tests pass saved Treasury.gov months from `tests/fixtures/`. `bench/grid.py` is the 50 Position by 100 Shock timing script for `price()` in a bare pool, and `bench/worker.py` the same through the spawned worker; neither is a test.

The worker is tested only through its process: `tests/test_worker.py` spawns `python -m pricing_engine.worker` (and once the `pricing-worker` console script) with `tests/worker_client.py` and sends JSON lines. Batch prices are checked against `bsm` for European calls, and against a single `price` request at the shocked inputs (the engine as its own twin, not an independent oracle) for American ones and for a moved explicit forward. The two timing bars are checked by `bench/worker.py`, not by a test, since they depend on the machine.

## Treasury.gov

The XML feed is keyless but holds a request whose `User-Agent` is a stock client's (urllib's, curl's) for about 18 s, and answers one that names itself in 0.2 s. `fetch_month` sets its own.

## Docs

QuantLib-Python: https://quantlib-python-docs.readthedocs.io/
pydantic: https://pydantic.dev/docs/validation/latest/llms.txt
uv: https://docs.astral.sh/uv/llms.txt
ty: https://docs.astral.sh/ty/
Ruff: https://docs.astral.sh/ruff/
