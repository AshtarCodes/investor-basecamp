# Engine worker (`pricing-worker`)

Type: task
Status: resolved

Blocked by: [16](16-pricing-engine-package.md) (the worker serves the engine's schema)

## Goal

Add the long-lived process the server spawns so QuantLib is imported once, not per request ([ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md)). The server code that spawns it does not exist yet and is not part of this ticket; nothing consumes the worker until the app has server functions.

## Scope

- A `pricing-worker` entry point in `packages/pricing-engine/` that reads one JSON request per line on stdin and writes one JSON response per line on stdout. Requests and responses use the schema exported by [16](16-pricing-engine-package.md), plus a request id that the response echoes.
- Structured errors: validation failures, model failures and unexpected exceptions each return an error object with a code, a message and the request id, and never kill the worker. Diagnostics go to stderr, never stdout.
- A warm-up on start (import QuantLib, build and price one throwaway option) and a ready line when done.
- A batch request type that prices many contracts over a Shock grid in one message, so the server does not send 5,000 lines for one grid. See "Decisions" for what the worker owns.
- A process pool, 4 processes by default, with the size easy to change (see "Decisions"). The worker owns the pool; a request is never split mid-contract.
- Restart behavior: the worker exits cleanly on stdin close and on SIGTERM, and a documented rule says what the caller should do when it dies mid-request (retry once).
- A runnable spec in the package `AGENTS.md`: how to start the worker by hand and send a request.

## Acceptance

- Round trip of a single price through a spawned subprocess, measured and recorded in the package `AGENTS.md`; the first request after the ready line is under 50 ms for a 100 by 200 grid price.
- A 50-Position by 100-Shock batch completes in under 1 s on this laptop through the worker, including the pool.
- A malformed line, an unknown request type, a validation failure and an unsupported root (NDX) each return a structured error and leave the worker serving the next line. A Mark at or below intrinsic is not an error: it returns `price: null`, `iv.reason` and the residual, in a single price and in a batch.
- stdin close and SIGTERM both end the process with exit code 0 within a second.
- Tests spawn the real worker as a subprocess; no test needs the network.

## Out of scope

- The TS client and the server function that spawn it; authentication (the worker is a local child process, not a network service); the Treasury fetch ([17](17-engine-rate-and-dividend-inputs.md)), which callers run and pass in.

## Decisions

Settled by grilling on 2026-10-25.

**Shock semantics live in the worker.** The caller does not expand the grid into 5,000 `PriceRequest`s. A batch carries, per contract, one base `PriceRequest` with a Mark, plus a list of Shocks (a spot move, an IV Shift and days forward) and one IV Shift mode for the batch (absolute points or proportional). The worker:

- solves the Mark-implied IV once per contract, at the same `Numerics` the Shocks use (default 50 by 100), so a zero Shock reproduces the Mark exactly;
- applies the spot move to spot, the IV Shift to that contract's own IV (floored at 1 vol point), and days forward to the valuation moment in calendar days;
- values a contract that expires inside the horizon at intrinsic at the shocked price, flagged;
- carries the residual unchanged when there is no IV ([ADR 0001](../../../docs/adr/0001-own-pricing-model.md)), which replaces [07](07-how-should-shocks-behave.md)'s fall back to Schwab's IV.

It returns per-share prices. Quantity, the ×100 multiplier, beta-weighting, Shock P/L and Loss Thresholds stay with the caller. The result is a dense array of prices per contract, with the flags sparse by Shock index.

**Mark at or below intrinsic is a result, not an error.** That is what `price()` already does and what ADR 0001 relies on; one illiquid option must not sink a batch.

**One request at a time, in order.** The worker reads a line, handles it fully, writes one line, then reads the next. A single `price` runs in the main process, already warm. Only a `batch` fans out to the pool, one contract per task. The id is still echoed so the caller can detect a desync.

**Envelope.**

- A request is `{"id", "type": "price" | "batch", ...}`, a discriminated union exported as `schema/worker-request.schema.json` and `schema/worker-response.schema.json`, under the existing `schema` script and staleness test.
- A response is `{"id", "ok": true, "result"}` or `{"id", "ok": false, "error": {"code", "message"}}`. A line with no readable id gets `id: null`.
- Error codes: `invalid_json`, `invalid_request` (pydantic validation, with the field path in the message), `unknown_type`, `model_error` (for example `UnknownRootError`) and `internal`.
- In a batch, a contract that fails gets a per-contract error object and the rest of the batch still returns. Only a batch-level failure uses the top-level error.

**Pool failure.** If a pool process dies (a QuantLib crash, an OOM kill), the worker rebuilds and re-warms the pool, answers the request in flight with `internal`, and keeps serving. It does not retry internally, since a contract that crashes QuantLib will do so again. The caller's retry once covers a dead pool and a dead worker alike.

**Ready line and warm-up.** The ready line `{"type":"ready","pid":…,"workers":N,"protocol":1}` is printed only after the main process and every pool process have priced the throwaway option, so the first batch pays no import cost. The protocol channel is its own file descriptor and fd 1 is redirected to stderr, so a stray `print` or QuantLib C++ output cannot corrupt a response line.

**Pool size: 4, warmed eagerly, easy to change.** Measured on this Mac (10 performance and 4 efficiency cores) with a warm pool and the 50 by 100 grid, without IV solves:

| Pool size | Warm-up | Resident memory | Grid |
| --- | --- | --- | --- |
| 4 | 0.27 s | about 440 MB | 0.176 s |
| 8 | 0.30 s | about 880 MB | 0.092 s |
| 14 | 0.41 s | about 1.5 GB | 0.075 s |

Each process costs about 110 MB and an idle one uses no CPU. Past 8 the grid barely speeds up. Four fits the 1 s bar with room and keeps the worker near 550 MB. The size is one constant, `DEFAULT_WORKERS = 4`, overridden by the `PRICING_WORKERS` environment variable, which a `--workers N` flag overrides in turn. An invalid value is an error on stderr before the ready line (exit code 2). The ready line reports the size in use. The package `AGENTS.md` documents the knob next to this table, re-measured through the real worker with IV solves.

**Tests.** They spawn `sys.executable -m pricing_engine.worker`, plus one smoke test of the `pricing-worker` console script. Check whether `uv run` forwards SIGTERM and returns exit code 0, since ADR 0007 has the server spawn it that way, and record the answer in `AGENTS.md`.

## Answer

Added `worker.py`, `batch.py`, `pool.py`, `protocol.py` and `errors.py` to `packages/pricing-engine/`, the `pricing-worker` console script, and `schema/worker-request.schema.json` and `schema/worker-response.schema.json`. The decisions above were built as written. `AGENTS.md` in the package holds the runnable spec, the pool-size knob and the measurements. Tests spawn the real worker (`tests/test_worker.py`); `bench/worker.py` is the timing script.

Through the spawned worker, with the Mark-implied IV solved for every Position, on this Mac (14 cores) at the default 4 processes: the ready line took 0.58 s, the first 100 by 200 price 11 ms against the 50 ms bar, and a 50 Position by 100 Shock batch 0.21 s against the 1 s bar. The table for other pool sizes is in the package `AGENTS.md`, next to the knob. `uv run --project packages/pricing-engine pricing-worker` forwards SIGTERM: the process exits with code 0 in under 0.1 s and takes the pool with it, and closing stdin does the same. The two timing bars are checked by `bench/worker.py`, not by a test.

Choices the grilling left open:

- **Batch shape:** each contract is `{"request", "shocks"}`, because the caller beta-weights the spot move per Underlying. A batch-level `numerics` (default 50 by 100) replaces each request's own. A batch request must carry a Mark and no `greeks` or `cross_check`.
- **Units:** `spot_move` is a fraction of spot (greater than -1, finite), `iv_shift` is a finite decimal (0.02 is 2 vol points) or a fraction of the IV in proportional mode, and `days_forward` is calendar days (0 to 36,500, fractions allowed). A request id is a string or an integer, never coerced from a boolean or a float. An explicit forward moves with spot.
- **Residual carry:** with no IV, a Shock's price is the model value at the 1 vol point floor plus the residual, so a zero Shock is worth the Mark. The IV Shift is ignored, the price is never below zero, and a Shock past expiry is plain intrinsic with no residual.
- **Result shape:** `prices` is dense, `shock_flags` lists only the flagged Shocks (`expired`), and `flags` carries the base price's flags such as `no_iv`.
- **Pool start:** a barrier in each process's initializer forces all N processes to start before the ready line, since the executor starts them on demand.
- **Timings include the wire:** each batch time runs from writing the request line to reading the response line.
- **Left to the server ticket:** a worker whose parent dies without closing stdin is not detected here; the server owns the child's lifetime.
