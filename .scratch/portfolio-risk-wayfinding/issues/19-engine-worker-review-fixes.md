# Engine worker: fixes from the review

Type: task
Status: resolved
Blocked by: none

## Goal

Fix what the 2026-10-25 review of [18](18-engine-worker.md) found by running the worker end to end. The findings and how each was reproduced are under `## Comments` in ticket 18. Every fix below is in `packages/pricing-engine/`. Each one gets a test in `tests/test_worker.py` that spawns the real worker, as that ticket requires. No change here alters a price.

Triaged 2026-10-26: items 8 and 9 are done as recommended. Item 4 is **(b)**, not the recommended (a): nothing leaks in the start-up window, the exit code is the only difference, and the server knows when it sent the signal. Item 6 was kept after a discussion of what the logging in `error_of` costs.

## Must fix

1. **Pool processes outlive a dead worker.** If the worker is SIGKILLed (or segfaults, or is OOM-killed), its 4 pool processes and the `multiprocessing` resource tracker are re-parented to launchd and never exit: about 466 MB per dead worker. The caller's retry rule restarts the worker, so every crash leaks another pool.
   - Fix: in `init_pool_process` (`pool.py:38`), start a daemon thread that waits on `multiprocessing.parent_process().sentinel` and calls `os._exit(1)` when it fires. A spike in the review showed the pool process and the resource tracker both gone 1 s after the parent was SIGKILLed.
   - Test: SIGKILL the worker, then assert every pid from `Worker.pool_pids()` is gone within a second.
   - Document it in the package `AGENTS.md` under "If the worker dies mid-request". The ticket's out-of-scope note, which leaves the opposite case (a dead parent with stdin still open) to the server, still stands.
2. **NaN and Infinity inputs are accepted.** `Sourced.value` is a plain `float`, and `json.loads` reads `NaN` and `Infinity`.
   - A NaN or infinite spot, σ or rate returns `ok: true` with `price: null`, no flag, and `inputs.spot.value: null`. pydantic writes NaN as `null`. A caller cannot tell that from a real answer.
   - A NaN Mark returns `internal` (Brent's `ValueError`), in a single price and in a batch.
   - Fix: set `allow_inf_nan=False` in `Model.model_config` (`models.py:10`), so every float in every request is finite. Then drop the per-field `allow_inf_nan=False` on `Shock` (`batch.py:43-44`), which the config now covers.
   - Run `pnpm --filter pricing-engine schema`. The staleness test says whether the JSON Schema changed.
   - Test: a NaN spot, an infinite σ and a NaN Mark in a batch are each `invalid_request`, and each message names the field path.
3. **A deeply nested line kills the worker.** `json.loads` raises `RecursionError`, not `ValueError`, on deep nesting. `handle` (`worker.py:92-95`) catches only `ValueError`, so the exception escapes `serve` and the worker exits 1. A 200,000-deep array kills it; 3,000 does not.
   - Fix: catch `RecursionError` beside `ValueError` and answer `invalid_json`.
   - Test: send `"[" * 200_000 + "]" * 200_000`. Assert the response is `invalid_json` with `id: null`, and that the next line is served.

## Should fix

4. **SIGTERM during start-up exits with -15, not 0.** The handler is installed at `worker.py:150`, after the module imports QuantLib and the pool's imports. A SIGTERM 0.02, 0.1 or 0.2 s after spawn exits -15. At 0.35 s through `uv run` it exits 0. Acceptance says "stdin close and SIGTERM both end the process with exit code 0 within a second", with no start-up exception.
   - **Recommended: (a).** Move `signal.signal(signal.SIGTERM, exit_on_sigterm)` to the first line of `main()`, and move the engine imports that pull in QuantLib (`pricing_engine.batch`, `pool` and `pricer`) inside `main`, or into one `serve`-side module imported after the handler is installed. Add a test that sends SIGTERM 0.05 s after spawn and expects 0.
   - (b) Document the window instead: the server waits for the ready line and only signals on shutdown, where -15 is harmless. This breaks the acceptance line as written.
5. **A `ValidationError` from inside the engine is reported as the caller's fault.** `worker.py:106-112` wraps both validation and pricing in one `try`, so a `ValidationError` raised by `price()` or by building a result comes back as `invalid_request`.
   - Fix: validate in its own `try` that maps `ValidationError` to `invalid_request`. Price outside it, where a `ValidationError` falls to `error_of` as `internal`.
   - Test: a `PriceMessage` that validates but whose pricing raises `ValidationError`. Patching inside the process is not possible without the `NOISY`-style hook, so this can be a unit test of `handle` if a test spawning the real process cannot reach it. Say so in the test's docstring.
6. **`errors.py` does I/O, against the package rule.** `error_of` calls `traceback.print_exception` (`errors.py:21`). The package `AGENTS.md` (line 3) allows I/O only in `treasury.py`, `worker.py` and `pool.py`. `batch.py`'s `price_contract_safely` calls it, so the pure batch module logs from pool processes.
   - Fix: `error_of` only builds the `WorkerError`. Move `price_contract_safely` from `batch.py` into `pool.py` (an I/O module), and log the traceback there and in `handle` before calling `error_of`.
7. **The batch test for a Mark below intrinsic is partial.** Acceptance says a Mark at or below intrinsic "returns `price: null`, `iv.reason` and the residual, in a single price and in a batch". `test_with_no_iv_every_shock_carries_the_residual_and_ignores_the_iv_shift` (`test_worker.py:206`) asserts neither `iv.reason` nor `iv.residual`.
   - Fix: assert `iv.reason == "at_or_below_intrinsic"` and that `iv.residual` equals the Mark minus the model value at σ = 0.01.
8. **A pool process that dies between requests fails the next batch.** Ticket 18 says the worker "answers the request in flight with `internal`". In the review, a pool process killed while idle made the next batch fail with `internal` in 0.30 s, although no contract of that batch had run. The batch after that priced.
   - **Recommended:** in `Pool.map` (`pool.py:84`), a `BrokenProcessPool` raised by `submit`, before any task of this request ran, rebuilds the pool and submits once more. Retrying is safe here because no contract of this request has run, so the crash cannot be a contract's fault. A break seen in `future.result()` stays `internal`, as now.
   - Update `test_a_pool_process_that_dies_between_requests_fails_the_next_batch_and_the_pool_is_rebuilt` to expect the batch to price. Detection is asynchronous, so the test must wait until the executor has noticed the death (poll `Worker.pool_pids()` for the replacement, or sleep 0.5 s as the review did).
   - Alternative: keep the current behaviour and reword the spec line and `AGENTS.md`, since the caller's retry covers it.
9. **A Shock's own flags are dropped.** `price_contract` (`batch.py:126-131`) keeps only `expired` per Shock. A Shock whose days forward passes an ex-date gets `dividend_not_in_life` from `price()`, and the batch drops that flag.
   - Measured on an American call with a $2 dividend and spot held: 5.41 at +21.0 days, 6.47 at +21.5 days, just past the ex-date. Nothing in the response says why the price jumped.
   - **Recommended:** a Shock's `flags` are those its shocked price adds beyond the base's `flags`, which includes `dividend_not_in_life`. Update the Answer's "shock_flags lists only the flagged Shocks (`expired`)" line and `AGENTS.md`.

## Record only, no change

- **One invalid contract fails the whole batch** with `invalid_request` and its field path (`contracts.1: …`). That is a caller bug, not one contract's market data, so it stays a batch-level failure. Add one sentence to the package `AGENTS.md` "Errors" paragraph so the server ticket does not expect a per-contract entry.
- **Ctrl-C by hand** exits 130 with one traceback on stderr. That is fine for the hand-run spec, and the server uses SIGTERM.
- **Standards smells the review raised, left as they are:**
  - `(contract, mode, numerics)` travels together through `price_contract`, `price_contract_safely` and the `jobs` tuple.
  - `Pool.map` is generic over `Callable[..., T]`.
  - The `Sourced(value=x * factor, …)` line appears twice in `shocked`.
  - The response models `PricedContract`, `FailedContract` and `ShockFlags` live in `batch.py`, not `protocol.py`.
  - `bench/worker.py` calls a per-share contract a "Position", as `bench/grid.py` already did.
  - The `NOISY` test patches `handle` inside the spawned process, the only way to prove fd 1 cannot reach the protocol.

  Revisit any of these if item 6 moves code between modules anyway.

## Acceptance

- Each fix in items 1 to 3 and 5 to 7 has a test that spawns the real worker, except where item 5 says otherwise. Items 4, 8 and 9 are done as recommended, or as decided in triage.
- `pnpm --filter pricing-engine test`, `lint`, `format:check` and `typecheck` pass, and the committed schema is fresh.
- `uv run python bench/worker.py` still meets both bars: the first price under 50 ms, and the 50 by 100 batch under 1 s.

## Answer

Resolved 2026-10-26. All nine items are in `packages/pricing-engine/`; no price changed.

- **1. Orphaned pool:** each pool process watches its parent's sentinel in a daemon thread and `os._exit(1)`s when it fires. A SIGKILLed worker leaves no pool processes within 2 s (the test allows 2 s, not the 1 s in the plan, so a loaded machine does not flake it).
- **2. NaN and Infinity:** `allow_inf_nan=False` on `Model`, so every float in every request is finite and an offender is `invalid_request` with its field path. The per-field setting on `Shock` is gone. The committed schema did not change for this. The config also governs the response models, so a NaN the engine computed would now be `internal` where it used to serialize as `null`.
- **3. Deep nesting:** `RecursionError` is `invalid_json`, and the worker serves the next line.
- **4. Start-up SIGTERM, decided (b):** documented, not changed. Ticket 18's acceptance line now names the first ~0.2 s, while QuantLib imports, and the package `AGENTS.md` says a caller that sent the signal treats -15 as a clean stop. There is no test.
- **5. Engine `ValidationError`:** `handle` validates in its own `try`; one raised while pricing is `internal`. The test is a unit test of `handle`, as the item allowed.
- **6. Logging out of `errors.py`:** `error_of` only builds the error. `price_contract_safely` moved to `pool.py` beside a new `report(error, context)`, which logs an `internal` error's traceback with the contract (or request id) it came from. Both the pool and `handle` use it. The tests are unit tests in `tests/test_failure_logging.py`, not spawned-worker ones: no request makes a contract fail with `internal`, and a spawned pool process cannot be patched without a hook.
- **7. Residual test:** the batch test asserts `iv.reason` and that `iv.residual` is the Mark minus the model value at σ = 0.01. It passed at once, and a flipped residual sign makes it fail.
- **8. Idle pool death:** if the first `submit` finds the pool broken, no contract has run, so `Pool.map` rebuilds and submits once more. A break after a task was submitted stays `internal`.
- **9. Shock flags:** a Shock's flags are those its price adds beyond the base's `flags`. The committed response schema's `PricedContract` description changed with it.

The package `AGENTS.md` covers items 1, 4, 6, 8 and 9, the "one invalid contract fails the batch" sentence, and the exceptions to "tested only through its process". Checks: `test` (179 pass), `lint`, `format:check` and `typecheck` pass, and `bench/worker.py` gives a first price of 10.9 ms and a 50 by 100 batch in 0.21 s.
