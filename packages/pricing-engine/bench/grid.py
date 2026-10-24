"""Benchmark: 50 Positions by 100 Shocks through a process pool (not a unit test).

Run: `pnpm --filter pricing-engine bench` or `uv run python bench/grid.py`.
The ticket's bar is under 1 s for the grid on the dev laptop, with the pool already started
(the worker of ticket 18 holds its pool open) and the Shock grid at 50 by 100.
"""

import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, date, datetime
from typing import Any

from pricing_engine import PriceRequest, price

POSITIONS = 50
SPOT_MOVES = [-0.20, -0.15, -0.10, -0.07, -0.05, -0.03, -0.01, 0.0, 0.01, 0.03,
              0.05, 0.07, 0.10, 0.15, 0.20, 0.25, -0.25, -0.30, 0.30, -0.02]  # fmt: skip
IV_SHIFTS = [-0.04, -0.02, 0.0, 0.02, 0.04]  # five of these by twenty moves is 100 Shocks
VALUATION = datetime(2026, 10, 26, 14, 0, tzinfo=UTC)
GRID = {"time_steps": 50, "spot_steps": 100}
LIMIT_SECONDS = 1.0


def position(i: int) -> dict[str, Any]:
    """A mix of American puts and calls with a dividend or two, and some European index options."""
    european = i % 10 == 9
    return {
        "contract": {
            "root": "SPXW" if european else "SPY",
            "expiry": date(2026, 11, 20) if i % 3 else date(2027, 3, 19),
            "strike": 90.0 + 2.0 * (i % 15),
            "right": "put" if i % 2 else "call",
            "exercise": "european" if european else "american",
        },
        "dividends": []
        if european or i % 4 == 0
        else [
            {"ex_date": date(2026, 11, 20), "amount": 0.8, "from": "bench"},
            {"ex_date": date(2027, 2, 19), "amount": 0.8, "from": "bench"},
        ],
        "volatility": 0.25 + 0.01 * (i % 20),
    }


def shocked_request(base: dict[str, Any], move: float, shift: float) -> PriceRequest:
    return PriceRequest.model_validate(
        {
            "contract": base["contract"],
            "valuation": VALUATION,
            "spot": {"value": 100.0 * (1 + move), "from": "bench"},
            "rate": {"value": 0.042, "from": "bench"},
            "volatility": {"value": base["volatility"] + shift, "from": "bench"},
            "dividends": base["dividends"],
            "numerics": GRID,
        }
    )


def reprice(base: dict[str, Any]) -> float:
    """All 100 Shocks of one Position; returns the sum so the work cannot be optimised away."""
    return sum(
        price(shocked_request(base, move, shift)).price or 0.0
        for move in SPOT_MOVES
        for shift in IV_SHIFTS
    )


def warm(_: int) -> int:
    return os.getpid()  # the import of pricing_engine (and QuantLib) happened loading this module


def main() -> None:
    workers = os.cpu_count() or 1
    positions = [position(i) for i in range(POSITIONS)]
    started = time.perf_counter()
    with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn")) as pool:
        list(pool.map(warm, range(workers * 4)))
        started_grid = time.perf_counter()
        totals = list(pool.map(reprice, positions))
        grid_seconds = time.perf_counter() - started_grid
    print(f"workers {workers}, pool start {started_grid - started:.2f} s")
    shocks = len(SPOT_MOVES) * len(IV_SHIFTS)
    print(f"{POSITIONS} Positions x {shocks} Shocks = {POSITIONS * shocks} prices")
    print(f"grid {grid_seconds:.3f} s (limit {LIMIT_SECONDS:.1f} s), checksum {sum(totals):.4f}")
    if grid_seconds >= LIMIT_SECONDS:
        raise SystemExit("over the limit")


if __name__ == "__main__":
    main()
