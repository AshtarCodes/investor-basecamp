"""A warm process pool for batches: QuantLib imported and exercised in every process up front."""

import multiprocessing
import os
import sys
import threading
import traceback
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from datetime import UTC, date, datetime
from multiprocessing.connection import wait
from multiprocessing.synchronize import Barrier
from typing import Any

from pricing_engine.batch import (
    SHOCK_NUMERICS,
    BatchContract,
    FailedContract,
    IvShiftMode,
    PricedContract,
    Shock,
    price_contract,
)
from pricing_engine.errors import WorkerError, error_of
from pricing_engine.models import Numerics, PriceRequest

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


def report(error: Exception, context: str) -> WorkerError:
    """`error_of`, and an `internal` one also gets a traceback on stderr, naming what failed."""
    failure = error_of(error)
    if failure.code == "internal":
        print(f"internal error in {context}", file=sys.stderr)
        traceback.print_exception(error)
    return failure


def price_contract_safely(
    contract: BatchContract, mode: IvShiftMode, numerics: Numerics
) -> PricedContract | FailedContract:
    """`price_contract`, with a contract that fails reported as an error so the batch survives."""
    try:
        return price_contract(contract, mode, numerics)
    except Exception as error:
        details = contract.request.contract
        context = f"contract {details.root} {details.expiry} {details.strike} {details.right}"
        return FailedContract(error=report(error, context))


def exit_with_parent() -> None:
    """Exit when the worker does, however it died, so a SIGKILLed worker leaves no pool behind."""
    parent = multiprocessing.parent_process()
    assert parent is not None
    wait([parent.sentinel])
    os._exit(1)


def init_pool_process(barrier: Barrier) -> None:
    """Runs once in each pool process. The barrier holds every process here until all N exist."""
    threading.Thread(target=exit_with_parent, daemon=True).start()
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

        Starts the pool first if an earlier rebuild failed and left it stopped. A pool process that
        died between requests breaks the executor, and the first `submit` says so before any task of
        this request has run. That cannot be this request's fault, so the pool is rebuilt and the
        jobs submitted once more. A break after a task was submitted is raised as it is: that task
        may be the cause, and the caller's retry rule covers it.
        """
        if self.executor is None:
            self.start()
        assert self.executor is not None
        futures: list[Future[T]] = []
        try:
            for job in jobs:
                futures.append(self.executor.submit(function, *job))
        except BrokenProcessPool:
            if futures:
                raise
            self.rebuild()
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
