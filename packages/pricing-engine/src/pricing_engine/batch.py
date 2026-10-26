"""Price many contracts over a Shock grid: the Shock semantics of ADR 0001 and ticket 07.

The caller sends, per contract, one base request with a Mark and a list of Shocks. The
Mark-implied IV is solved once per contract and every Shock reprices from it, so a zero Shock
reproduces the Mark. Prices are per share: quantity, the 100 multiplier, beta weighting and
Shock P/L stay with the caller.
"""

from datetime import timedelta
from typing import Literal, Self

from pydantic import Field, model_validator

from pricing_engine.errors import WorkerError
from pricing_engine.iv import SIGMA_MIN
from pricing_engine.models import (
    Flag,
    ImpliedVolatility,
    Model,
    Numerics,
    PriceRequest,
    Sourced,
)
from pricing_engine.pricer import price

IvShiftMode = Literal["absolute", "proportional"]

MAX_DAYS_FORWARD = 36_500  # a hundred years; far past any expiry, and well inside `timedelta`

# The grid used for a Shock grid: as accurate as 100 by 200 to a tenth of a cent, about 3x faster.
SHOCK_NUMERICS = Numerics(time_steps=50, spot_steps=100)


class Shock(Model):
    """One cell of a Scenario, for one contract's Underlying.

    `spot_move` is that Underlying's Beta-weighted Move, which the caller has already worked out,
    as a fraction of spot (-0.05 is down 5%). `iv_shift` is added to the contract's IV
    as a decimal (0.02 is 2 vol points) in `absolute` mode, or scales it (0.25 is +25%) in
    `proportional` mode. `days_forward` is calendar days.
    """

    spot_move: float = Field(gt=-1)
    iv_shift: float
    days_forward: float = Field(ge=0, le=MAX_DAYS_FORWARD)


class BatchContract(Model):
    """A base request with a Mark, and the Shocks to price it under."""

    request: PriceRequest
    shocks: list[Shock]

    @model_validator(mode="after")
    def check_request(self) -> Self:
        if self.request.mark is None:
            raise ValueError("a batch prices from a Mark: give mark, not volatility")
        if self.request.greeks or self.request.cross_check:
            raise ValueError("a batch returns prices only: greeks and cross_check are not allowed")
        return self


class ShockFlags(Model):
    """The flags on one Shock, by its index in the contract's `shocks`."""

    shock: int
    flags: list[Flag]


class PricedContract(Model):
    """`prices[i]` is the per-share price under `shocks[i]`; `shock_flags` lists only the Shocks
    whose price carries a flag the base's `flags` do not (`expired`, `dividend_not_in_life`).

    `iv` is the Mark-implied IV. With none (`iv.value` is null), every Shock keeps the model's value
    at the lowest σ plus the residual, ignores the IV Shift, and `flags` includes `no_iv`.
    """

    ok: Literal[True] = True
    iv: ImpliedVolatility
    flags: list[Flag]
    prices: list[float]
    shock_flags: list[ShockFlags]


class FailedContract(Model):
    ok: Literal[False] = False
    error: WorkerError


def shocked(
    request: PriceRequest, iv: ImpliedVolatility, shock: Shock, mode: IvShiftMode
) -> PriceRequest:
    """The request for one Shock: spot moved, σ shifted, valuation moved forward, no Mark."""
    if iv.value is None:
        sigma = SIGMA_MIN
    elif mode == "absolute":
        sigma = max(iv.value + shock.iv_shift, SIGMA_MIN)
    else:
        sigma = max(iv.value * (1 + shock.iv_shift), SIGMA_MIN)
    factor = 1 + shock.spot_move
    return request.model_copy(
        update={
            "valuation": request.valuation + timedelta(days=shock.days_forward),
            "spot": Sourced(value=request.spot.value * factor, **{"from": request.spot.from_}),
            "forward": None
            if request.forward is None
            else Sourced(value=request.forward.value * factor, **{"from": request.forward.from_}),
            "volatility": Sourced(value=sigma, **{"from": "shocked mark-implied IV"}),
            "mark": None,
        }
    )


def price_contract(
    contract: BatchContract, mode: IvShiftMode, numerics: Numerics
) -> PricedContract:
    """Solve the contract's Mark-implied IV once, then price it under each of its Shocks."""
    base_request = contract.request.model_copy(update={"numerics": numerics})
    base = price(base_request)
    assert base.iv is not None  # the request has a Mark
    prices: list[float] = []
    shock_flags: list[ShockFlags] = []
    for index, shock in enumerate(contract.shocks):
        result = price(shocked(base_request, base.iv, shock, mode))
        assert result.price is not None  # the shocked request has a σ
        amount = result.price
        expired = "expired" in result.flags
        if base.iv.residual is not None and not expired:
            amount = max(amount + base.iv.residual, 0.0)
        prices.append(amount)
        added = [flag for flag in result.flags if flag not in base.flags]
        if added:
            shock_flags.append(ShockFlags(shock=index, flags=added))
    return PricedContract(iv=base.iv, flags=base.flags, prices=prices, shock_flags=shock_flags)
