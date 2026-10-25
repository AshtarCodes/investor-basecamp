"""A client that spawns the real pricing worker and talks JSON lines to it."""

import json
import os
import queue
import subprocess
import sys
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import IO, Any

from pricing_engine import PriceRequest

TIMEOUT_SECONDS = 60.0


def without_pool_size(environ: Mapping[str, str]) -> dict[str, str]:
    """The environment minus PRICING_WORKERS, so a test sees the default unless it sets one."""
    return {name: value for name, value in environ.items() if name != "PRICING_WORKERS"}


def price_message(id: str | int, req: PriceRequest) -> dict[str, Any]:
    """A `price` request line for a `PriceRequest`."""
    return {"id": id, "type": "price", **req.model_dump(mode="json", by_alias=True)}


def batch_message(
    id: str | int,
    contracts: list[tuple[PriceRequest, list[dict[str, float]]]],
    mode: str = "absolute",
) -> dict[str, Any]:
    """A `batch` request line: each contract is a base request with a Mark, and its Shocks."""
    return {
        "id": id,
        "type": "batch",
        "iv_shift_mode": mode,
        "contracts": [
            {"request": req.model_dump(mode="json", by_alias=True), "shocks": shocks}
            for req, shocks in contracts
        ],
    }


class Worker:
    """A spawned `python -m pricing_engine.worker`; `ready` is its first stdout line."""

    def __init__(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        command: list[str] | None = None,
        stderr_to: Path | None = None,
    ) -> None:
        self.stderr: IO[str] | None = None
        if stderr_to is not None:
            self.stderr = open(stderr_to, "w")  # noqa: SIM115 (closed in cleanup)
        self.process = subprocess.Popen(
            [*(command or [sys.executable, "-m", "pricing_engine.worker"]), *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr or subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env={**without_pool_size(os.environ), **(env or {})},
        )
        assert self.process.stdout is not None
        self.lines: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self.pump, args=(self.process.stdout,), daemon=True).start()
        self.ready: dict[str, Any] = self.read()

    def pump(self, stdout: Any) -> None:
        for line in stdout:
            self.lines.put(line)
        self.lines.put(None)

    def read(self, timeout: float = TIMEOUT_SECONDS) -> dict[str, Any]:
        line = self.lines.get(timeout=timeout)
        assert line is not None, "the worker closed stdout"
        return json.loads(line)

    def write(self, text: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(text + "\n")
        self.process.stdin.flush()

    def send_raw(self, text: str) -> dict[str, Any]:
        self.write(text)
        return self.read()

    def send(self, message: dict[str, Any]) -> dict[str, Any]:
        return self.send_raw(json.dumps(message))

    def pool_pids(self) -> list[int]:
        """Pids of the pool processes: children of the worker that `spawn` started."""
        children = subprocess.run(
            ["ps", "-A", "-o", "pid=,ppid=,command="], capture_output=True, text=True, check=True
        ).stdout.splitlines()
        pids = []
        for row in children:
            pid, ppid, command = row.split(None, 2)
            if int(ppid) == self.process.pid and "multiprocessing.spawn" in command:
                pids.append(int(pid))
        return pids

    def close(self) -> int:
        """Close stdin and wait for the exit code."""
        assert self.process.stdin is not None
        if not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            return self.process.wait(timeout=TIMEOUT_SECONDS)
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()
        if self.process.stdout:
            self.process.stdout.close()
        if self.stderr:
            self.stderr.close()
