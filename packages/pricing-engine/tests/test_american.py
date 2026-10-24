from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from support import bsm, priced, request, src, years

from pricing_engine import price


def crr_american(right: str, spot, strike, t, rate, sigma, q=0.0, steps=4000) -> float:
    """A 4,000-step Cox-Ross-Rubinstein tree at the exact T: an independent American oracle."""
    cp = 1 if right == "call" else -1
    dt = t / steps
    up = np.exp(sigma * np.sqrt(dt))
    down = 1 / up
    p = (np.exp((rate - q) * dt) - down) / (up - down)
    discount = np.exp(-rate * dt)
    j = np.arange(steps + 1)
    values = np.maximum(cp * (spot * up ** (steps - j) * down**j - strike), 0.0)
    for i in range(steps - 1, -1, -1):
        j = np.arange(i + 1)
        exercise = np.maximum(cp * (spot * up ** (i - j) * down**j - strike), 0.0)
        values = np.maximum(discount * (p * values[:-1] + (1 - p) * values[1:]), exercise)
    return float(values[0])


# The 4,000-step tree is itself up to 0.014 cent from its converged value (the 12,000-step tree
# puts the K=105, 30-day put 0.09 cent from the 100 by 200 grid, but 0.104 from this oracle), so the
# 0.1 and 0.05 cent bars get 0.01 cent of oracle slack.
ORACLE_SLACK = 0.0001

LIVES = [{"hours": 3.5}, {"days": 1.5}, {"days": 30}]
# (right, spot, strike, sigma, yield): puts, a high-vol put, and a call carrying a yield
# (a call on a non-dividend payer takes the closed form instead).
CASES = [
    ("put", 100, 100, 0.35, 0.0),
    ("put", 100, 105, 0.35, 0.0),
    ("put", 25.37, 30, 1.03, 0.0),
    ("call", 100, 95, 0.35, 0.06),
]


@pytest.mark.parametrize("life", LIVES)
@pytest.mark.parametrize(("right", "spot", "strike", "sigma", "carry"), CASES)
def test_american_without_dividends_matches_a_4000_step_tree(
    life, right, spot, strike, sigma, carry
):
    t = years(**life)
    oracle = crr_american(right, spot, strike, t, 0.042, sigma, q=carry)
    common: dict[str, Any] = {
        "right": right, "exercise": "american", "spot": spot, "strike": strike,
        "rate": 0.042, "sigma": sigma, "life": life, "continuous_yield": src(carry),
    }  # fmt: skip
    default = price(request(**common))
    fine = price(request(**common, numerics={"time_steps": 400, "spot_steps": 800}))
    assert default.model == "american_fd_cash_drop"
    assert default.price == pytest.approx(oracle, abs=0.001 + ORACLE_SLACK)  # 0.1 cent
    assert fine.price == pytest.approx(oracle, abs=0.0005 + ORACLE_SLACK)  # 0.05 cent


def test_a_call_on_a_non_dividend_payer_uses_the_closed_form():
    result = price(
        request(right="call", exercise="american", spot=25.37, strike=22, sigma=1.03, rate=0.042,
                life={"days": 80})
    )  # fmt: skip
    assert result.model == "american_closed_form"
    assert result.price == pytest.approx(
        bsm("call", 25.37, 22, years(days=80), 0.042, 1.03), abs=1e-9
    )


def test_a_borrow_cost_or_a_dividend_takes_a_call_off_the_closed_form():
    borrowed = price(
        request(right="call", exercise="american", borrow_rate=src(0.05), hard_to_borrow=True)
    )
    assert borrowed.model == "american_fd_cash_drop"
    assert "hard_to_borrow" in borrowed.flags
    dividend = price(
        request(
            right="call",
            exercise="american",
            dividends=[{"ex_date": date(2026, 11, 20), "amount": 0.8, "from": "test fixture"}],
        )
    )
    assert dividend.model == "american_fd_cash_drop"


NEW_YORK = ZoneInfo("America/New_York")
FIRST_EX_DATE = date(2026, 11, 20)
SECOND_EX_DATE = date(2027, 2, 19)
TWO_DIVIDENDS: list[dict[str, Any]] = [
    {"ex_date": FIRST_EX_DATE, "amount": 0.80, "from": "test fixture"},
    {"ex_date": SECOND_EX_DATE, "amount": 0.80, "from": "test fixture"},
]
APRIL_PUT: dict[str, Any] = {
    "right": "put",
    "exercise": "american",
    "spot": 100,
    "strike": 105,
    "sigma": 0.30,
    "rate": 0.042,
    "expiry": date(2027, 4, 16),
}


def put_with_dividends(**extra: Any):
    return request(
        **{**APRIL_PUT, "life": {"days": 172, "hours": 10}, "dividends": TWO_DIVIDENDS}, **extra
    )


def test_cash_dividends_raise_a_put_and_are_stable_as_the_virtual_clock_grows():
    undivided = priced(request(**APRIL_PUT, life={"days": 172, "hours": 10}))
    prices = [
        priced(
            put_with_dividends(numerics={"clock_days": days, "time_steps": 200, "spot_steps": 400})
        )
        for days in (730, 3650, 36500)
    ]
    assert all(p > undivided + 0.3 for p in prices)
    assert max(prices) - min(prices) < 0.0005  # 0.05 cent


def test_a_shock_that_moves_the_valuation_past_a_dividend_drops_that_dividend():
    # Valuation after the first ex-date but before the second: only the second counts.
    life = {"days": 60}
    later = request(**APRIL_PUT, life=life, dividends=TWO_DIVIDENDS)
    only_second = request(**APRIL_PUT, life=life, dividends=TWO_DIVIDENDS[1:])
    first_ex_instant = datetime.combine(FIRST_EX_DATE, time(9, 30), tzinfo=NEW_YORK)
    second_ex_instant = datetime.combine(SECOND_EX_DATE, time(9, 30), tzinfo=NEW_YORK)
    assert first_ex_instant < later.valuation < second_ex_instant
    assert priced(later) == pytest.approx(priced(only_second), abs=1e-12)
    assert "dividend_not_in_life" in price(later).flags


def test_leisen_reimer_on_spot_less_the_dividends_cross_checks_the_cash_drop_price():
    result = price(put_with_dividends(cross_check=True))
    check = result.cross_check
    assert check is not None
    assert check.model == "leisen_reimer"
    assert check.steps == 101  # odd
    assert result.price is not None
    assert check.difference == pytest.approx(check.price - result.price, abs=1e-12)
    # ADR 0007: the tree lands about 3 cents either side of the cash-drop price.
    assert abs(check.difference) < 0.06
