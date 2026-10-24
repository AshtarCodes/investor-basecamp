"""A dated cash dividend schedule projected from Schwab's dividend fields (ADR 0001).

Pure: the caller reads `fundamental.nextDivExDate`, `divPayAmount`, `divFreq` and `divYield` from
the quote and passes them in.
"""

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pricing_engine.models import CashDividend

Rule = Literal[
    "quarterly-from-next-ex-date",
    "none",
    "none-before-expiry",
    "needs-continuous-yield",
    "unsupported-frequency",
    "missing-ex-date",
]


@dataclass(frozen=True)
class DividendProjection:
    rule: Rule
    dividends: tuple[CashDividend, ...] = ()
    # Schwab's next ex-date was already past, so the schedule starts at a later quarter.
    rolled_forward: bool = False


def project_dividends(
    *,
    next_div_ex_date: date | str | None,
    div_pay_amount: float,
    div_freq: int,
    div_yield: float,
    valuation_date: date,
    expiry: date,
) -> DividendProjection:
    """The cash dividends between the valuation date and the expiry, and the rule that made them."""
    if div_freq == 0:
        if div_yield > 0:
            return DividendProjection("needs-continuous-yield")
        return DividendProjection("none" if div_pay_amount == 0 else "unsupported-frequency")
    if div_freq != 4:
        return DividendProjection("unsupported-frequency")
    ex_date = _to_date(next_div_ex_date)
    if div_pay_amount <= 0:
        return DividendProjection("none")
    if ex_date is None:
        return DividendProjection("missing-ex-date")
    rule: Rule = "quarterly-from-next-ex-date"
    first_quarter = 0
    while _add_months(ex_date, 3 * first_quarter) < valuation_date:
        first_quarter += 1
    dividends = []
    for quarter in range(first_quarter, first_quarter + 400):
        projected = _add_months(ex_date, 3 * quarter)
        if projected > expiry:
            break
        dividends.append(
            CashDividend(ex_date=projected, amount=div_pay_amount, **{"from": f"schwab:{rule}"})
        )
    if not dividends:
        return DividendProjection("none-before-expiry")
    return DividendProjection(rule, tuple(dividends), rolled_forward=first_quarter > 0)


def _to_date(value: date | str | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value[:10])


def _add_months(anchor: date, months: int) -> date:
    """`anchor` plus `months`, clamped to the month's last day (Nov 30 + 3 months is Feb 28)."""
    index = anchor.year * 12 + anchor.month - 1 + months
    year, month = divmod(index, 12)
    last_day = calendar.monthrange(year, month + 1)[1]
    return date(year, month + 1, min(anchor.day, last_day))
