"""The worker, through its only interface: JSON lines on stdin and stdout of a spawned process."""

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from support import bsm, priced, request, src, years
from worker_client import Worker, batch_message, price_message

import pricing_engine.worker as worker_module
from pricing_engine.pool import Pool
from pricing_engine.protocol import Failure
from pricing_engine.worker import DEFAULT_WORKERS

NUMERICS = {"time_steps": 50, "spot_steps": 100}  # the batch's default, for single-price twins


@pytest.fixture(scope="module")
def worker() -> Iterator[Worker]:
    spawned = Worker("--workers", "2")
    yield spawned
    spawned.close()


def test_the_worker_says_ready_then_prices_a_request(worker):
    assert worker.ready["type"] == "ready"
    assert worker.ready["protocol"] == 1
    assert worker.ready["workers"] == 2
    assert isinstance(worker.ready["pid"], int)

    reply = worker.send(price_message("first", request(sigma=0.3)))

    assert reply["id"] == "first"
    assert reply["ok"] is True
    expected = bsm("call", 100.0, 100.0, years(days=91, hours=6), 0.04, 0.3)
    assert reply["result"]["price"] == pytest.approx(expected, abs=1e-6)
    assert reply["result"]["inputs"]["spot"] == {"value": 100.0, "from": "test fixture"}


def served_after(worker: Worker) -> bool:
    """Whether the worker still answers a good request with the right price."""
    reply = worker.send(price_message("after", request(sigma=0.3)))
    return reply["id"] == "after" and reply["ok"] is True


def test_a_malformed_line_is_an_invalid_json_error_with_no_id(worker):
    reply = worker.send_raw("{not json")
    assert reply["id"] is None
    assert reply["ok"] is False
    assert reply["error"]["code"] == "invalid_json"
    assert served_after(worker)


def test_a_line_nested_too_deep_for_json_is_an_invalid_json_error_and_the_worker_serves_on(worker):
    depth = 200_000  # the C scanner copes with 3,000 levels; 200,000 raises RecursionError
    reply = worker.send_raw("[" * depth + "]" * depth)
    assert reply["id"] is None
    assert reply["ok"] is False
    assert reply["error"]["code"] == "invalid_json"
    assert served_after(worker)


def test_json_that_is_not_an_object_is_an_invalid_request(worker):
    reply = worker.send_raw("[1, 2, 3]")
    assert (reply["id"], reply["error"]["code"]) == (None, "invalid_request")
    assert served_after(worker)


def test_an_unknown_request_type_echoes_the_id(worker):
    reply = worker.send({"id": "q7", "type": "teleport"})
    assert reply["id"] == "q7"
    assert reply["error"]["code"] == "unknown_type"
    assert "teleport" in reply["error"]["message"]
    assert served_after(worker)


def test_a_request_with_no_type_is_invalid_not_unknown(worker):
    reply = worker.send({"id": "q8"})
    assert (reply["id"], reply["error"]["code"]) == ("q8", "invalid_request")


def test_a_validation_failure_names_the_field_and_echoes_the_id(worker):
    message = price_message("bad", request(sigma=0.3))
    message["contract"]["strike"] = -5
    reply = worker.send(message)
    assert reply["id"] == "bad"
    assert reply["error"]["code"] == "invalid_request"
    assert "contract.strike" in reply["error"]["message"]
    assert served_after(worker)


def test_a_validation_error_raised_by_the_engine_is_internal_not_the_callers_fault(
    monkeypatch, capsys
):
    """A unit test of `handle`: no request makes `price()` raise a ValidationError, so the test
    patches it, which a spawned process cannot do without a hook like the `NOISY` one."""

    def broken(message):
        raise ValidationError.from_exception_data("PriceResult", [])

    monkeypatch.setattr(worker_module, "price", broken)
    line = json.dumps(price_message("engine", request(sigma=0.3)))

    reply = worker_module.handle(line, Pool(1))

    assert isinstance(reply, Failure) and reply.id == "engine"
    assert reply.error.code == "internal"
    logged = capsys.readouterr().err
    assert "ValidationError" in logged and "'engine'" in logged  # the log names the request


def test_an_unsupported_root_is_a_model_error(worker):
    valuation = datetime(2026, 10, 26, 14, 0, tzinfo=UTC)
    reply = worker.send(price_message("ndx", request(root="NDX", valuation=valuation)))
    assert reply["id"] == "ndx"
    assert reply["error"]["code"] == "model_error"
    assert "NDX" in reply["error"]["message"]
    assert served_after(worker)


def test_blank_lines_are_ignored(worker):
    worker.write("")
    worker.write("   ")
    assert served_after(worker)


def test_a_mark_below_intrinsic_is_a_result_with_the_residual_not_an_error(worker):
    # American put, spot 90, strike 100: intrinsic is 10, and the Mark is 5.
    below = request(
        right="put", exercise="american", spot=90.0, strike=100.0, sigma=None, mark=src(5.0)
    )

    reply = worker.send(price_message("illiquid", below))

    assert reply["ok"] is True
    result = reply["result"]
    assert result["price"] is None
    assert result["iv"]["reason"] == "at_or_below_intrinsic"
    assert result["iv"]["residual"] is not None and result["iv"]["residual"] < 0
    assert "no_iv" in result["flags"]


# A European call is priced in closed form, so a batch of them can be checked against `bsm`.
CALL_LIFE = years(days=91, hours=6)


def mark_of(sigma: float) -> float:
    return bsm("call", 100.0, 100.0, CALL_LIFE, 0.04, sigma)


def european_call_batch(shocks: list[dict[str, float]], mode: str = "absolute", sigma=0.3):
    base = request(sigma=None, mark=src(mark_of(sigma)))
    return batch_message("grid", [(base, shocks)], mode)


def shock(spot_move=0.0, iv_shift=0.0, days_forward=0.0) -> dict[str, float]:
    return {"spot_move": spot_move, "iv_shift": iv_shift, "days_forward": days_forward}


def test_a_batch_prices_each_shock_and_a_zero_shock_reproduces_the_mark(worker):
    reply = worker.send(european_call_batch([shock(), shock(spot_move=0.05)]))

    assert reply["id"] == "grid" and reply["ok"] is True
    (contract,) = reply["result"]["contracts"]
    assert contract["ok"] is True
    assert contract["iv"]["value"] == pytest.approx(0.3, abs=1e-7)
    zero, up = contract["prices"]
    assert zero == pytest.approx(mark_of(0.3), abs=1e-6)
    assert up == pytest.approx(bsm("call", 105.0, 100.0, CALL_LIFE, 0.04, 0.3), abs=1e-6)
    assert contract["shock_flags"] == []


def test_the_iv_shift_moves_the_contracts_own_iv_by_points_or_by_percent(worker):
    absolute = worker.send(european_call_batch([shock(iv_shift=0.05)], "absolute"))
    proportional = worker.send(european_call_batch([shock(iv_shift=0.5)], "proportional"))

    (a,) = absolute["result"]["contracts"][0]["prices"]
    (b,) = proportional["result"]["contracts"][0]["prices"]
    assert a == pytest.approx(bsm("call", 100.0, 100.0, CALL_LIFE, 0.04, 0.35), abs=1e-6)
    assert b == pytest.approx(bsm("call", 100.0, 100.0, CALL_LIFE, 0.04, 0.45), abs=1e-6)


@pytest.mark.parametrize("mode, shift", [("absolute", -0.5), ("proportional", -0.99)])
def test_a_shifted_iv_never_goes_below_one_vol_point(worker, mode, shift):
    reply = worker.send(european_call_batch([shock(iv_shift=shift)], mode))
    (amount,) = reply["result"]["contracts"][0]["prices"]
    assert amount == pytest.approx(bsm("call", 100.0, 100.0, CALL_LIFE, 0.04, 0.01), abs=1e-6)


def test_days_forward_shortens_the_remaining_life_in_calendar_days(worker):
    reply = worker.send(european_call_batch([shock(days_forward=30)]))
    (amount,) = reply["result"]["contracts"][0]["prices"]
    expected = bsm("call", 100.0, 100.0, years(days=61, hours=6), 0.04, 0.3)
    assert amount == pytest.approx(expected, abs=1e-6)


def test_a_contract_that_expires_inside_the_horizon_is_intrinsic_and_flagged(worker):
    shocks = [shock(spot_move=0.05, days_forward=100), shock(spot_move=0.05, days_forward=30)]
    reply = worker.send(european_call_batch(shocks))
    contract = reply["result"]["contracts"][0]
    assert contract["prices"][0] == pytest.approx(5.0, abs=1e-9)  # 105 against a 100 strike
    assert contract["shock_flags"] == [{"shock": 0, "flags": ["expired"]}]


AMERICAN_PUT = dict(
    right="put", exercise="american", spot=100.0, strike=105.0, rate=0.042,
    expiry=date(2027, 4, 16), life={"days": 172, "hours": 10},
    dividends=[{"ex_date": date(2026, 12, 18), "amount": 0.8, "from": "test fixture"}],
)  # fmt: skip


def test_a_shock_equals_a_single_price_at_the_shocked_inputs_and_the_solved_iv(worker):
    """The batch is the single price at the shocked spot, valuation and σ (a dividend drops out)."""
    mark = worker.send(
        price_message("mark", request(**AMERICAN_PUT, sigma=0.34, numerics=NUMERICS))
    )
    base = request(**AMERICAN_PUT, sigma=None, mark=src(mark["result"]["price"]))
    forward_days = 120  # past the 18 December ex-date, which then no longer counts
    grid = worker.send(batch_message("g", [(base, [shock(-0.1, 0.03, forward_days)])]))
    (batched,) = grid["result"]["contracts"][0]["prices"]

    shocked = request(
        **{**AMERICAN_PUT, "spot": 90.0, "sigma": 0.37, "numerics": NUMERICS,
           "valuation": base.valuation.replace() + timedelta(days=forward_days)},
    )  # fmt: skip
    single = worker.send(price_message("single", shocked))
    assert batched == pytest.approx(single["result"]["price"], abs=1e-6)
    assert "dividend_not_in_life" in single["result"]["flags"]


def american_put_batch(shocks: list[dict[str, float]], **overrides):
    fixture = {**AMERICAN_PUT, **overrides}
    mark = priced(request(**fixture, sigma=0.34, numerics=NUMERICS))
    return batch_message("flags", [(request(**fixture, sigma=None, mark=src(mark)), shocks)])


def test_a_shock_that_passes_the_ex_date_is_flagged_dividend_not_in_life(worker):
    reply = worker.send(american_put_batch([shock(days_forward=0), shock(days_forward=120)]))
    contract = reply["result"]["contracts"][0]
    assert contract["flags"] == []
    assert contract["shock_flags"] == [{"shock": 1, "flags": ["dividend_not_in_life"]}]


def test_a_flag_the_base_already_carries_is_not_repeated_on_its_shocks(worker):
    spent = [{"ex_date": date(2026, 10, 1), "amount": 0.8, "from": "test fixture"}]
    reply = worker.send(american_put_batch([shock(), shock(days_forward=120)], dividends=spent))
    contract = reply["result"]["contracts"][0]
    assert contract["flags"] == ["dividend_not_in_life"]
    assert contract["shock_flags"] == []


BELOW_INTRINSIC = dict(right="put", exercise="american", spot=90.0, strike=100.0)  # intrinsic 10


def test_with_no_iv_every_shock_carries_the_residual_and_ignores_the_iv_shift(worker):
    below = request(**BELOW_INTRINSIC, sigma=None, mark=src(5.0))
    shocks = [shock(), shock(iv_shift=0.2), shock(spot_move=0.5)]
    reply = worker.send(batch_message("residual", [(below, shocks)]))
    contract = reply["result"]["contracts"][0]
    assert contract["iv"]["value"] is None
    assert contract["iv"]["reason"] == "at_or_below_intrinsic"
    at_lowest_sigma = priced(request(**{**BELOW_INTRINSIC, "sigma": 0.01, "numerics": NUMERICS}))
    assert contract["iv"]["residual"] == pytest.approx(5.0 - at_lowest_sigma, abs=1e-9)
    assert "no_iv" in contract["flags"]
    at_base, shifted, rallied = contract["prices"]
    assert at_base == pytest.approx(5.0, abs=1e-6)  # the Mark, so a zero Shock is worth the Mark
    assert shifted == pytest.approx(at_base, abs=1e-12)
    assert 0.0 <= rallied < at_base  # a rally cheapens a put, and a price is never negative


def test_a_failing_contract_gets_its_own_error_and_the_rest_of_the_batch_prices(worker):
    valuation = datetime(2026, 10, 26, 14, 0, tzinfo=UTC)
    unsupported = request(root="NDX", valuation=valuation, sigma=None, mark=src(5.0))
    good = request(sigma=None, mark=src(mark_of(0.3)))
    reply = worker.send(batch_message("mixed", [(unsupported, [shock()]), (good, [shock()])]))

    assert reply["ok"] is True
    bad, fine = reply["result"]["contracts"]
    assert bad["ok"] is False and bad["error"]["code"] == "model_error"
    assert fine["ok"] is True and fine["prices"][0] == pytest.approx(mark_of(0.3), abs=1e-6)


def test_a_batch_returns_one_entry_per_contract_in_order_with_dense_prices(worker):
    contracts = [
        (request(sigma=None, mark=src(mark_of(0.2 + 0.05 * i))), [shock()] * (i + 1))
        for i in range(5)
    ]
    reply = worker.send(batch_message("many", contracts))
    ivs = [c["iv"]["value"] for c in reply["result"]["contracts"]]
    counts = [len(c["prices"]) for c in reply["result"]["contracts"]]
    assert ivs == pytest.approx([0.2, 0.25, 0.3, 0.35, 0.4], abs=1e-6)
    assert counts == [1, 2, 3, 4, 5]


def test_a_batch_priced_from_a_volatility_is_an_invalid_request_naming_the_field(worker):
    message = batch_message("v", [(request(sigma=0.3), [shock()])])
    reply = worker.send(message)
    assert reply["id"] == "v"
    assert reply["error"]["code"] == "invalid_request"
    assert "contracts.0" in reply["error"]["message"]


def test_a_shock_that_would_take_spot_to_zero_is_invalid(worker):
    reply = worker.send(european_call_batch([shock(spot_move=-1.0)]))
    assert reply["error"]["code"] == "invalid_request"
    assert "spot_move" in reply["error"]["message"]


def test_the_pool_has_one_warm_process_per_worker_when_the_ready_line_arrives(worker):
    assert len(worker.pool_pids()) == 2


def test_the_pool_size_comes_from_the_flag_then_the_environment_then_the_default():
    flagged = Worker("--workers", "1", env={"PRICING_WORKERS": "3"})
    from_env = Worker(env={"PRICING_WORKERS": "3"})
    default = Worker()
    try:
        assert flagged.ready["workers"] == 1 and len(flagged.pool_pids()) == 1
        assert from_env.ready["workers"] == 3 and len(from_env.pool_pids()) == 3
        assert default.ready["workers"] == DEFAULT_WORKERS
    finally:
        for spawned in (flagged, from_env, default):
            spawned.close()


@pytest.mark.parametrize(
    "args, env",
    [
        (["--workers", "0"], {}),
        (["--workers", "many"], {}),
        ([], {"PRICING_WORKERS": "0"}),
        ([], {"PRICING_WORKERS": "four"}),
    ],
)
def test_an_invalid_pool_size_exits_with_code_2_and_a_message_before_any_ready_line(args, env):
    done = subprocess.run(
        [sys.executable, "-m", "pricing_engine.worker", *args],
        input="", capture_output=True, text=True, env={**os.environ, **env}, timeout=60,
    )  # fmt: skip
    assert done.returncode == 2
    assert done.stdout == ""
    assert "workers" in done.stderr.lower()


def test_closing_stdin_ends_the_worker_with_code_0_within_a_second():
    spawned = Worker("--workers", "2")
    started = time.perf_counter()
    assert spawned.close() == 0
    assert time.perf_counter() - started < 1.0
    assert spawned.pool_pids() == []


def test_sigterm_ends_the_worker_with_code_0_within_a_second_and_takes_the_pool_with_it():
    spawned = Worker("--workers", "2")
    pool = spawned.pool_pids()
    assert len(pool) == 2
    started = time.perf_counter()
    spawned.process.send_signal(signal.SIGTERM)
    code = spawned.process.wait(timeout=10)
    elapsed = time.perf_counter() - started
    spawned.cleanup()
    assert code == 0
    assert elapsed < 1.0
    time.sleep(0.3)
    assert all(not process_exists(pid) for pid in pool)


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def wait_until_gone(pids: list[int], seconds: float) -> list[int]:
    """The pids still alive after up to `seconds`."""
    deadline = time.perf_counter() + seconds
    alive = [pid for pid in pids if process_exists(pid)]
    while alive and time.perf_counter() < deadline:
        time.sleep(0.05)
        alive = [pid for pid in alive if process_exists(pid)]
    return alive


def test_a_sigkilled_worker_takes_its_pool_processes_with_it():
    spawned = Worker("--workers", "2")
    pool = spawned.pool_pids()  # read before the kill: afterwards they are not its children
    assert len(pool) == 2
    try:
        spawned.process.send_signal(signal.SIGKILL)
        spawned.process.wait(timeout=10)
        assert wait_until_gone(pool, seconds=2.0) == []
    finally:
        for pid in wait_until_gone(pool, seconds=0):
            os.kill(pid, signal.SIGKILL)
        spawned.cleanup()


def test_a_pool_process_that_dies_between_requests_is_replaced_and_the_next_batch_prices():
    spawned = Worker("--workers", "2")
    try:
        batch = european_call_batch([shock(), shock(spot_move=0.01)])
        assert spawned.send(batch)["ok"] is True
        before = spawned.pool_pids()
        os.kill(before[0], signal.SIGKILL)
        time.sleep(0.5)  # the executor notices a death asynchronously; no contract has run yet

        reply = spawned.send(batch)

        assert reply["ok"] is True and reply["id"] == "grid"
        after = spawned.pool_pids()
        assert len(after) == 2 and not set(after) & set(before)
        assert spawned.send(price_message("single", request(sigma=0.3)))["ok"] is True
    finally:
        spawned.close()


NOISY = """
import os, sys
import pricing_engine.worker as w
handle = w.handle
def noisy(line, pool):
    print("a stray print")
    os.write(1, b"raw bytes on fd 1\\n")
    return handle(line, pool)
w.handle = noisy
sys.argv = ["pricing-worker", "--workers", "1"]
w.main()
"""


def test_stray_output_on_stdout_cannot_corrupt_a_response_line(tmp_path):
    log = tmp_path / "stderr.txt"
    spawned = Worker(command=[sys.executable, "-c", NOISY], stderr_to=log)
    try:
        reply = spawned.send(price_message("quiet", request(sigma=0.3)))
        assert reply["id"] == "quiet" and reply["ok"] is True
    finally:
        spawned.close()
    assert "a stray print" in log.read_text()


def test_the_pricing_worker_console_script_serves_requests():
    script = Path(sys.executable).parent / "pricing-worker"
    spawned = Worker("--workers", "1", command=[str(script)])
    try:
        assert spawned.ready["workers"] == 1
        assert spawned.send(price_message("cli", request(sigma=0.3)))["ok"] is True
        assert spawned.close() == 0
    finally:
        spawned.cleanup()


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("field", ["spot_move", "iv_shift", "days_forward"])
def test_a_shock_that_is_not_a_finite_number_is_an_invalid_request(worker, field, bad):
    reply = worker.send(european_call_batch([shock(**{field: bad})]))
    assert reply["error"]["code"] == "invalid_request"
    assert field in reply["error"]["message"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize(
    "path, field",
    [
        (("spot", "value"), "spot.value"),
        (("volatility", "value"), "volatility.value"),
        (("rate", "value"), "rate.value"),
    ],
)
def test_a_price_input_that_is_not_a_finite_number_is_an_invalid_request(worker, path, field, bad):
    message = price_message("nan", request(sigma=0.3))
    message[path[0]][path[1]] = bad  # set after building: the model no longer holds a NaN
    reply = worker.send(message)
    assert reply["ok"] is False and reply["id"] == "nan"
    assert reply["error"]["code"] == "invalid_request"
    assert field in reply["error"]["message"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_a_mark_that_is_not_a_finite_number_is_an_invalid_request_in_a_batch(worker, bad):
    message = european_call_batch([shock()])
    message["contracts"][0]["request"]["mark"]["value"] = bad
    reply = worker.send(message)
    assert reply["ok"] is False and reply["id"] == "grid"
    assert reply["error"]["code"] == "invalid_request"
    assert "contracts.0.request.mark.value" in reply["error"]["message"]


def test_a_shock_beyond_a_hundred_years_forward_is_an_invalid_request(worker):
    reply = worker.send(european_call_batch([shock(days_forward=1e12)]))
    assert reply["error"]["code"] == "invalid_request"
    assert "days_forward" in reply["error"]["message"]


@pytest.mark.parametrize("bad_id", [True, 2.0, None, [1], {"a": 1}])
def test_an_id_that_is_not_a_string_or_integer_is_refused_not_coerced(worker, bad_id):
    message = price_message("x", request(sigma=0.3))
    message["id"] = bad_id
    reply = worker.send(message)
    assert reply["ok"] is False and reply["id"] is None
    assert reply["error"]["code"] == "invalid_request"


def test_an_explicit_forward_moves_with_spot_in_a_shock(worker):
    forward = 101.0
    european = dict(forward=src(forward), life={"days": 91, "hours": 6})
    base = request(sigma=0.3, **european)
    mark = worker.send(price_message("mark", base))["result"]["price"]
    from_mark = request(sigma=None, mark=src(mark), **european)
    batched = worker.send(batch_message("fwd", [(from_mark, [shock(spot_move=0.1)])]))
    (amount,) = batched["result"]["contracts"][0]["prices"]

    moved = request(
        sigma=0.3, spot=110.0, forward=src(forward * 1.1), life={"days": 91, "hours": 6}
    )
    expected = worker.send(price_message("twin", moved))["result"]["price"]
    assert amount == pytest.approx(expected, abs=1e-6)


def big_batch(id: str) -> dict:
    """50 dividend-paying American puts by 100 Shocks: a 1-process pool needs over half a second."""
    shocks = [shock(0.01 * j - 0.5) for j in range(100)]
    contracts = []
    for i in range(50):
        fixture = {**AMERICAN_PUT, "strike": 90.0 + 0.5 * i, "numerics": NUMERICS}
        mark = priced(request(**fixture, sigma=0.3))
        contracts.append(
            (
                request(**{**AMERICAN_PUT, "strike": 90.0 + 0.5 * i}, sigma=None, mark=src(mark)),
                shocks,
            )
        )
    return batch_message(id, contracts)


def test_sigterm_in_the_middle_of_a_batch_still_exits_with_code_0_within_a_second():
    spawned = Worker("--workers", "1")
    spawned.write(json.dumps(big_batch("big")))
    time.sleep(0.1)
    started = time.perf_counter()
    spawned.process.send_signal(signal.SIGTERM)
    code = spawned.process.wait(timeout=10)
    elapsed = time.perf_counter() - started
    spawned.cleanup()
    assert code == 0
    assert elapsed < 1.0
    time.sleep(0.3)
    assert spawned.pool_pids() == []


def test_a_pool_process_killed_in_the_middle_of_a_batch_fails_that_batch_and_the_pool_recovers():
    spawned = Worker("--workers", "1")
    try:
        (victim,) = spawned.pool_pids()
        spawned.write(json.dumps(big_batch("doomed")))
        time.sleep(0.15)  # the only pool process is now pricing the batch
        os.kill(victim, signal.SIGKILL)

        failed = spawned.read()
        assert failed["id"] == "doomed"
        assert failed["ok"] is False and failed["error"]["code"] == "internal"

        (replacement,) = spawned.pool_pids()
        assert replacement != victim
        retried = spawned.send(european_call_batch([shock(spot_move=0.05)]))
        assert retried["ok"] is True
        (amount,) = retried["result"]["contracts"][0]["prices"]
        assert amount == pytest.approx(bsm("call", 105.0, 100.0, CALL_LIFE, 0.04, 0.3), abs=1e-6)
    finally:
        spawned.close()
