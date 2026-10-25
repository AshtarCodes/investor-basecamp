"""The worker's JSON-lines envelope: what a request line and a response line look like."""

from typing import Literal

from pydantic import Field, StrictInt, StrictStr

from pricing_engine.batch import (
    SHOCK_NUMERICS,
    BatchContract,
    FailedContract,
    IvShiftMode,
    PricedContract,
)
from pricing_engine.errors import WorkerError
from pricing_engine.models import Model, Numerics, PriceRequest, PriceResult

PROTOCOL_VERSION = 1

RequestId = StrictStr | StrictInt  # strict, so `true` or `2.0` is refused, not echoed as 1 or 2


class PriceMessage(PriceRequest):
    """Price one contract: a `PriceRequest` with the request id and type beside its fields."""

    id: RequestId
    type: Literal["price"]


class BatchMessage(Model):
    """Price many contracts over their Shocks. `numerics` replaces each request's own numerics."""

    id: RequestId
    type: Literal["batch"]
    iv_shift_mode: IvShiftMode
    numerics: Numerics = Field(default=SHOCK_NUMERICS)
    contracts: list[BatchContract]


Request = PriceMessage | BatchMessage
# Request types the worker serves, for telling an unknown type from an invalid request.
REQUEST_TYPES: dict[str, type[PriceMessage] | type[BatchMessage]] = {
    "price": PriceMessage,
    "batch": BatchMessage,
}


class BatchResult(Model):
    """One entry per contract of the request, in order."""

    contracts: list[PricedContract | FailedContract]


class Success(Model):
    id: RequestId
    ok: Literal[True] = True
    result: PriceResult | BatchResult


class Failure(Model):
    """`id` is null when the line had no readable id."""

    id: RequestId | None
    ok: Literal[False] = False
    error: WorkerError


class Ready(Model):
    """The first line on stdout, printed once the worker can price without further start-up cost."""

    type: Literal["ready"] = "ready"
    pid: int
    workers: int
    protocol: Literal[1] = PROTOCOL_VERSION


Response = Ready | Success | Failure
