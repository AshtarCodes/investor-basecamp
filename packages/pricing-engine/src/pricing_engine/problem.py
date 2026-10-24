"""One fully resolved pricing problem."""

import math
from dataclasses import dataclass, replace

from pricing_engine.models import Numerics


@dataclass(frozen=True)
class Problem:
    """Everything the model needs, in years from the valuation moment.

    `dividends` holds `(years from now, cash per share)` for each dividend that falls inside
    the remaining life. `carry_yield` is the continuous yield plus the borrow rate.
    """

    right: int
    american: bool
    strike: float
    spot: float
    forward: float | None
    sigma: float
    rate: float
    carry_yield: float
    dividends: tuple[tuple[float, float], ...]
    life: float
    numerics: Numerics

    def with_spot(self, spot: float) -> "Problem":
        """A bumped spot. An explicit forward moves with it, holding the carry fixed."""
        forward = None if self.forward is None else self.forward * spot / self.spot
        return replace(self, spot=spot, forward=forward)

    def advance(self, years: float) -> "Problem":
        """The same problem `years` later: less life left, and dividends already paid dropped."""
        remaining = tuple((t - years, d) for t, d in self.dividends if t - years > 0)
        return replace(self, life=self.life - years, dividends=remaining)

    @property
    def intrinsic(self) -> float:
        return max(self.right * (self.spot - self.strike), 0.0)

    def present_value_of_dividends(self) -> float:
        return sum(d * math.exp(-self.rate * t) for t, d in self.dividends)

    def european_forward(self) -> float:
        """The explicit forward, else spot less the dividends' present value, grown at the carry."""
        if self.forward is not None:
            return self.forward
        escrowed = self.spot - self.present_value_of_dividends()
        return escrowed * math.exp((self.rate - self.carry_yield) * self.life)
