"""A warm process pool for batches: QuantLib imported and exercised in every process up front."""

import multiprocessing
import os
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, date, datetime
from multiprocessing.synchronize import Barrier
from typing import Any

from pricing_engine.batch import SHOCK_NUMERICS, BatchContract, Shock, price_contract
from pricing_engine.models import PriceRequest

START_TIMEOUT_SECONDS = 60.0


def warm_up() -> None:
    """Price a throwaway option with a Mark and a Shock, so start-up costs are paid up front."""
    request = PriceRequest.model_validate(
        {
            "contract": {
                "root": "SPY",
                "expiry": date(2026, 11, 20),
                "strike": 100.0,
                "right": "put",
                "exercise": "american",
            },
            "valuation": datetime(2026, 10, 26, 14, 0, tzinfo=UTC),
            "spot": {"value": 100.0, "from": "warm-up"},
            "rate": {"value": 0.042, "from": "warm-up"},
            "mark": {"value": 3.0, "from": "warm-up"},
        }
    )
    shock = Shock(spot_move=-0.05, iv_shift=0.02, days_forward=1)
    price_contract(BatchContract(request=request, shocks=[shock]), "absolute", SHOCK_NUMERICS)


def init_pool_process(barrier: Barrier) -> None:
    """Runs once in each pool process. The barrier holds every process here until all N exist."""
    warm_up()
    barrier.wait(START_TIMEOUT_SECONDS)


def process_id() -> int:
    return os.getpid()


class Pool:
    """`size` spawned processes, all warm once `start` returns."""

    def __init__(self, size: int) -> None:
        self.size = size
        self.executor: ProcessPoolExecutor | None = None

    def start(self) -> None:
        """Start the processes and wait until each has priced the throwaway option.

        The barrier is entered in each process's initializer, so no process finishes a task before
        all of them exist, and the executor (which starts processes on demand) must start `size`.
        """
        context = multiprocessing.get_context("spawn")
        barrier = context.Barrier(self.size)
        executor = ProcessPoolExecutor(
            self.size, mp_context=context, initializer=init_pool_process, initargs=(barrier,)
        )
        try:
            futures = [executor.submit(process_id) for _ in range(self.size)]
            for future in futures:
                future.result(timeout=START_TIMEOUT_SECONDS)
        except BaseException:
            self.executor = executor  # so `stop` reaches the processes already started
            self.stop()
            raise
        self.executor = executor

    def map[T](self, function: Callable[..., T], jobs: Sequence[tuple[Any, ...]]) -> list[T]:
        """Run `function(*job)` for each job, one job per task, in order.

        Starts the pool first if an earlier rebuild failed and left it stopped.
        """
        if self.executor is None:
            self.start()
        assert self.executor is not None
        futures = [self.executor.submit(function, *job) for job in jobs]
        return [future.result() for future in futures]

    def stop(self) -> None:
        """Stop the processes without waiting for work in flight."""
        executor, self.executor = self.executor, None
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)
        for child in multiprocessing.active_children():
            child.terminate()

    def rebuild(self) -> None:
        self.stop()
        self.start()
