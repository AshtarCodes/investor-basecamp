"""Benchmark: the real worker, spawned as the server will, on the ticket's two timing bars.

Run: `uv run python bench/worker.py [--workers N]` (not a unit test). It measures start-up to the
ready line, the first single price after it (bar: under 50 ms at 100 by 200), and a 50 Position by
100 Shock batch with the Mark-implied IV solved for every Position (bar: under 1 s).
"""

import json
import statistics
import subprocess
import sys
import time
from typing import Any

from grid import IV_SHIFTS, POSITIONS, SPOT_MOVES, VALUATION, position

from pricing_engine import PriceRequest, price

FIRST_PRICE_LIMIT_SECONDS = 0.050
BATCH_LIMIT_SECONDS = 1.0
RUNS = 5


def base_request(base: dict[str, Any]) -> dict[str, Any]:
    """A grid Position as a request with a Mark, the Mark being its model price at its σ."""
    body: dict[str, Any] = {
        "contract": base["contract"],
        "valuation": VALUATION,
        "spot": {"value": 100.0, "from": "bench"},
        "rate": {"value": 0.042, "from": "bench"},
        "dividends": base["dividends"],
    }
    mark = price(
        PriceRequest.model_validate(
            {**body, "volatility": {"value": base["volatility"], "from": "bench"}}
        )
    ).price
    return {**body, "mark": {"value": mark, "from": "bench"}}


def batch_line() -> str:
    shocks = [
        {"spot_move": move, "iv_shift": shift, "days_forward": 0}
        for move in SPOT_MOVES
        for shift in IV_SHIFTS
    ]
    contracts = [{"request": base_request(position(i)), "shocks": shocks} for i in range(POSITIONS)]
    message = {"id": "bench", "type": "batch", "iv_shift_mode": "absolute", "contracts": contracts}
    return json.dumps(message, default=str)


def memory_megabytes(pid: int) -> float:
    """Resident memory of the worker and its pool. `ps` counts shared pages once per process."""
    rows = subprocess.run(
        ["ps", "-A", "-o", "pid=,ppid=,rss="], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    total = sum(
        int(rss) for p, parent, rss in (row.split() for row in rows) if pid in (int(p), int(parent))
    )
    return total / 1024


def main() -> None:
    started = time.perf_counter()
    worker = subprocess.Popen(
        [sys.executable, "-m", "pricing_engine.worker", *sys.argv[1:]],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    stdin, stdout = worker.stdin, worker.stdout
    assert stdin is not None and stdout is not None
    ready = json.loads(stdout.readline())
    start_up = time.perf_counter() - started

    def send(line: str) -> tuple[dict[str, Any], float]:
        sent = time.perf_counter()
        stdin.write(line + "\n")
        stdin.flush()
        return json.loads(stdout.readline()), time.perf_counter() - sent

    # Default numerics, 100 by 200: the price a caller asks for one contract.
    first_line = json.dumps(
        {"id": "first", "type": "price", **base_request(position(1))}, default=str
    )
    reply, first = send(first_line)
    assert reply["ok"], reply
    line = batch_line()
    timings = []
    for _ in range(RUNS):
        reply, took = send(line)
        assert reply["ok"], reply
        assert all(c["ok"] and len(c["prices"]) == 100 for c in reply["result"]["contracts"])
        timings.append(took)
    megabytes = memory_megabytes(worker.pid)
    stdin.close()
    worker.wait(timeout=10)

    print(f"workers {ready['workers']}, start-up to ready line {start_up:.2f} s")
    print(f"first single price (100 by 200) {first * 1000:.1f} ms (limit 50 ms)")
    median, best, worst = statistics.median(timings), min(timings), max(timings)
    print(
        f"{POSITIONS} Positions x 100 Shocks with IV solves: median {median:.3f} s, "
        f"best {best:.3f} s, worst {worst:.3f} s (limit {BATCH_LIMIT_SECONDS:.1f} s)"
    )
    print(f"resident memory, worker and pool: about {megabytes:.0f} MB (ps overstates)")
    if first >= FIRST_PRICE_LIMIT_SECONDS or max(timings) >= BATCH_LIMIT_SECONDS:
        raise SystemExit("over the limit")


if __name__ == "__main__":
    main()
