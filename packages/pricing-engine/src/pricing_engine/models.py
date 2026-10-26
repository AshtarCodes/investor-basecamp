"""Request and result models. Their JSON Schema (`schema/`) is the contract with the server."""

from datetime import date
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=True, allow_inf_nan=False
    )


class Sourced(Model):
    """A number and where it came from. Every input to a price names its source."""

    value: float
    from_: str = Field(alias="from", min_length=1)


def default_zero() -> Sourced:
    return Sourced(value=0.0, from_="default")


class CashDividend(Model):
    """A cash dividend per share. It drops the spot at 09:30 America/New_York on `ex_date`."""

    ex_date: date
    amount: float = Field(gt=0)
    from_: str = Field(alias="from", min_length=1)


class Contract(Model):
    root: str
    expiry: date
    strike: float = Field(gt=0)
    right: Literal["call", "put"]
    exercise: Literal["american", "european"]


class Numerics(Model):
    """Numerical settings. The defaults suit a single price; use 50 by 100 for a Shock grid."""

    time_steps: int = Field(default=100, ge=10)
    spot_steps: int = Field(default=200, ge=10)
    clock_days: int = Field(default=3650, ge=365)
    tree_steps: int = Field(default=101, ge=3)

    @field_validator("tree_steps")
    @classmethod
    def tree_steps_is_odd(cls, steps: int) -> int:
        if steps % 2 == 0:
            raise ValueError("a Leisen-Reimer tree needs an odd step count")
        return steps


class PriceRequest(Model):
    """Price one contract at a valuation moment, or solve its Mark-implied IV and price at that.

    Give `volatility` to price at a known σ, or `mark` to solve the Mark-implied IV.
    """

    contract: Contract
    valuation: AwareDatetime
    spot: Sourced
    rate: Sourced
    volatility: Sourced | None = None
    mark: Sourced | None = None
    continuous_yield: Sourced = Field(default_factory=default_zero)
    borrow_rate: Sourced = Field(default_factory=default_zero)
    hard_to_borrow: bool = False
    dividends: list[CashDividend] = Field(default_factory=list)
    forward: Sourced | None = None
    greeks: bool = False
    cross_check: bool = False
    numerics: Numerics = Field(default_factory=Numerics)

    @model_validator(mode="after")
    def check_consistency(self) -> Self:
        if (self.volatility is None) == (self.mark is None):
            raise ValueError("give exactly one of volatility and mark")
        if self.spot.value <= 0:
            raise ValueError("spot must be positive")
        if self.volatility is not None and self.volatility.value <= 0:
            raise ValueError("volatility must be positive")
        if self.mark is not None and self.mark.value < 0:
            raise ValueError("mark must not be negative")
        if self.forward is not None:
            if self.contract.exercise != "european":
                raise ValueError("an explicit forward is only for European contracts")
            if self.forward.value <= 0:
                raise ValueError("forward must be positive")
        if self.cross_check and self.contract.exercise != "american":
            raise ValueError("the Leisen-Reimer cross-check is only for American contracts")
        return self


class Greeks(Model):
    """Bump-and-reprice sensitivities: vega per vol point, theta per day, rho per rate point."""

    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


class ImpliedVolatility(Model):
    """The Mark-implied IV as a decimal, or why there is none.

    `residual` is the Mark minus the model value at the lowest σ bound; it is set only when
    there is no IV, and ADR 0001 carries it unchanged under Shocks.
    """

    value: float | None
    reason: Literal["at_or_below_intrinsic", "no_bracket"] | None = None
    residual: float | None = None


class CrossCheck(Model):
    model: Literal["leisen_reimer"]
    steps: int
    price: float
    difference: float


Flag = Literal["hard_to_borrow", "no_iv", "dividend_not_in_life", "expired"]

PricingModel = Literal[
    "black_scholes_merton",
    "black_76",
    "american_closed_form",
    "american_fd_cash_drop",
    "intrinsic",
]


class PricedInputs(Model):
    """The request's inputs, echoed with their provenance. `volatility` is the σ priced at."""

    spot: Sourced
    rate: Sourced
    volatility: Sourced | None
    continuous_yield: Sourced
    borrow_rate: Sourced
    dividends: list[CashDividend]
    forward: Sourced | None


class PriceResult(Model):
    """A price and the inputs that produced it. `price` is null when there is no Mark-implied IV."""

    price: float | None
    model: PricingModel
    inputs: PricedInputs
    iv: ImpliedVolatility | None
    greeks: Greeks | None
    cross_check: CrossCheck | None
    settlement_instant: AwareDatetime
    remaining_life_years: float
    flags: list[Flag]
