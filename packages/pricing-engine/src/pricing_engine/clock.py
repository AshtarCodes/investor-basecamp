"""Calendar time, and the virtual clock that lets QuantLib's whole-day dates carry it.

Time convention (ADR 0001): calendar time over a 365-day year, from the valuation moment to
the Settlement instant. QuantLib's dates are whole days, so a finite-difference or tree price
maps true time `[0, T]` onto `N` whole days and rescales the inputs so that σ²T, rT and r/σ²
are unchanged.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime

SECONDS_PER_YEAR = 365 * 86_400
QL_DAYS_PER_YEAR = 365.0


def years_between(start: datetime, end: datetime) -> float:
    """Elapsed calendar years. Both instants are converted to UTC, so daylight saving counts."""
    return (end.astimezone(UTC) - start.astimezone(UTC)).total_seconds() / SECONDS_PER_YEAR


@dataclass(frozen=True)
class VirtualClock:
    """Maps a true life of `life` years onto `days` whole QuantLib days."""

    life: float
    days: int

    @property
    def scale(self) -> float:
        """True years per QuantLib year, `T / T_ql`."""
        return self.life / (self.days / QL_DAYS_PER_YEAR)

    def volatility(self, sigma: float) -> float:
        return sigma * math.sqrt(self.scale)

    def rate(self, rate: float) -> float:
        """Rescales a continuously compounded rate or yield."""
        return rate * self.scale

    def dividend_day(self, time: float) -> int:
        """The QuantLib day a dividend `time` true years from now falls on, inside `[1, N-1]`."""
        return min(max(round(time / self.life * self.days), 1), self.days - 1)
