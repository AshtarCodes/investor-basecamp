"""The long-lived pricing worker: JSON lines on stdin, JSON lines on stdout (ADR 0007).

One request at a time, in order. A `price` runs in this process; a `batch` fans out to a warm
process pool, one contract per task. The ready line is printed once this process and every pool
process have priced a throwaway option. The protocol has its own file descriptor, and fd 1 is
pointed at stderr, so a stray print or QuantLib's C++ output cannot corrupt a response line.
Exit code 0 on stdin close and on SIGTERM; 2 on an invalid pool size.
"""

import argparse
import io
import json
import os
import signal
import sys
import traceback
from collections.abc import Mapping, Sequence
from concurrent.futures.process import BrokenProcessPool
from types import FrameType
from typing import TextIO

from pydantic import TypeAdapter, ValidationError

from pricing_engine.errors import ErrorCode, WorkerError
from pricing_engine.pool import Pool, price_contract_safely, report, warm_up
from pricing_engine.pricer import price
from pricing_engine.protocol import (
    REQUEST_TYPES,
    BatchMessage,
    BatchResult,
    Failure,
    PriceMessage,
    Ready,
    RequestId,
    Response,
    Success,
)

# Pool size when neither `--workers` nor PRICING_WORKERS says otherwise. Measured in AGENTS.md.
DEFAULT_WORKERS = 4
WORKERS_ENV = "PRICING_WORKERS"

response_adapter: TypeAdapter[Response] = TypeAdapter(Response)


def positive_int(text: str) -> int:
    count = int(text)
    if count < 1:
        raise ValueError(text)
    return count


def resolve_workers(argv: Sequence[str], environ: Mapping[str, str]) -> int:
    """The pool size: `--workers N`, else PRICING_WORKERS, else `DEFAULT_WORKERS`.

    An invalid value exits with code 2 and a message on stderr, before anything is started.
    """
    parser = argparse.ArgumentParser(prog="pricing-worker", description=__doc__)
    parser.add_argument("--workers", type=positive_int, help="pool size (default %(default)s)")
    parser.set_defaults(workers=None)
    flag = parser.parse_args(argv).workers
    if flag is not None:
        return flag
    if WORKERS_ENV in environ:
        try:
            return positive_int(environ[WORKERS_ENV])
        except ValueError:
            parser.error(f"{WORKERS_ENV} must be a positive integer, got {environ[WORKERS_ENV]!r}")
    return DEFAULT_WORKERS


def fail(request_id: RequestId | None, code: ErrorCode, message: str) -> Failure:
    return Failure(id=request_id, error=WorkerError(code=code, message=message))


def describe(error: ValidationError) -> str:
    """Each problem as `field.path: reason`, so the caller can find the field."""
    return "; ".join(
        f"{'.'.join(str(part) for part in problem['loc']) or 'request'}: {problem['msg']}"
        for problem in error.errors()
    )


def run_batch(message: BatchMessage, pool: Pool) -> BatchResult:
    jobs = [(contract, message.iv_shift_mode, message.numerics) for contract in message.contracts]
    return BatchResult(contracts=pool.map(price_contract_safely, jobs))


def handle(line: str, pool: Pool) -> Response:
    """The response to one request line. Never raises: every failure is a `Failure`."""
    try:
        raw = json.loads(line)
    except (ValueError, RecursionError) as error:  # RecursionError: a line nested far too deep
        return fail(None, "invalid_json", str(error))
    if not isinstance(raw, dict):
        return fail(None, "invalid_request", "a request is a JSON object")
    request_id = raw.get("id")
    if isinstance(request_id, bool) or not isinstance(request_id, str | int):
        request_id = None
    kind = raw.get("type")
    if kind is None:
        return fail(request_id, "invalid_request", "type: field required")
    if not isinstance(kind, str) or kind not in REQUEST_TYPES:
        return fail(request_id, "unknown_type", f"unknown request type {kind!r}")
    try:
        message = REQUEST_TYPES[kind].model_validate(raw)
    except ValidationError as error:
        return fail(request_id, "invalid_request", describe(error))
    try:
        if isinstance(message, PriceMessage):
            return Success(id=message.id, result=price(message))
        return Success(id=message.id, result=run_batch(message, pool))
    except BrokenProcessPool as error:
        # A pool process died (a QuantLib crash, an OOM kill). Replace the pool and report this
        # request as failed; the caller retries once. Retrying here would repeat a crash.
        traceback.print_exc()
        try:
            pool.rebuild()
        except Exception:
            traceback.print_exc()  # the next batch starts the pool again
        return fail(request_id, "internal", f"the pricing pool died: {error}")
    except Exception as error:
        return Failure(id=request_id, error=report(error, f"request {request_id!r}"))


def write(out: TextIO, response: Response) -> None:
    out.write(response_adapter.dump_json(response, by_alias=True).decode() + "\n")
    out.flush()


def exit_on_sigterm(signum: int, frame: FrameType | None) -> None:
    raise SystemExit(0)


def serve(stdin: TextIO, out: TextIO, pool: Pool) -> None:
    write(out, Ready(pid=os.getpid(), workers=pool.size))
    while line := stdin.readline():
        if line.strip():
            write(out, handle(line, pool))


def main() -> None:
    workers = resolve_workers(sys.argv[1:], os.environ)
    # Keep the real stdout for protocol lines, then point fd 1 (and sys.stdout) at stderr.
    out = os.fdopen(os.dup(1), "w", encoding="utf-8")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    assert isinstance(sys.stdin, io.TextIOWrapper)
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    signal.signal(signal.SIGTERM, exit_on_sigterm)
    pool = Pool(workers)
    try:
        warm_up()
        pool.start()
        serve(sys.stdin, out, pool)
    finally:
        pool.stop()


if __name__ == "__main__":
    main()
