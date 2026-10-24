import math
from datetime import UTC, date, datetime, timedelta

import pytest
from support import bsm, request, src, years

from pricing_engine import price


def test_haug_table_value_to_four_decimals():
    # Haug, S=60 K=65 T=0.25 r=8% sigma=30%: 2.1334
    result = price(
        request(spot=60, strike=65, rate=0.08, sigma=0.30, life={"days": 91, "hours": 6})
    )
    assert result.price == pytest.approx(2.1334, abs=5e-5)
    assert result.model == "black_scholes_merton"


@pytest.mark.parametrize(
    "life",
    [
        {"hours": 3.5},
        {"days": 1},
        {"days": 1.5},
        {"days": 30},
        {"days": 91, "hours": 6},
        {"days": 730},
    ],
)
@pytest.mark.parametrize("right", ["call", "put"])
def test_european_equals_closed_form_at_the_exact_fractional_t(life, right):
    result = price(request(right=right, strike=102, spot=100, rate=0.042, sigma=0.35, life=life))
    expected = bsm(right, 100, 102, years(**life), 0.042, 0.35)
    assert result.price == pytest.approx(expected, abs=1e-9)
    assert result.remaining_life_years == pytest.approx(years(**life), abs=1e-12)


def test_a_continuous_yield_and_a_borrow_rate_both_lower_the_forward():
    life = {"days": 120}
    result = price(
        request(
            right="put",
            strike=100,
            rate=0.04,
            sigma=0.3,
            life=life,
            continuous_yield=src(0.02, "etf yield"),
            borrow_rate=src(0.015, "broker borrow"),
            hard_to_borrow=True,
        )
    )
    assert result.price == pytest.approx(
        bsm("put", 100, 100, years(**life), 0.04, 0.3, q=0.035), abs=1e-9
    )
    assert result.flags == ["hard_to_borrow"]
    assert result.inputs.borrow_rate.from_ == "broker borrow"
    assert result.inputs.continuous_yield.from_ == "etf yield"


def test_a_european_dividend_is_taken_from_spot_at_its_present_value():
    life = {"days": 120}
    dividends = [{"ex_date": date(2026, 11, 20), "amount": 1.5, "from": "test fixture"}]
    result = price(request(right="put", strike=100, life=life, dividends=dividends))
    # The ex-date drop is at 09:30 EST on 2026-11-20 (14:30 UTC).
    ex_years = (
        datetime(2026, 11, 20, 14, 30, tzinfo=UTC)
        - (datetime(2026, 12, 18, 21, 0, tzinfo=UTC) - timedelta(days=120))
    ).total_seconds() / (365 * 86_400)
    escrowed = 100 - 1.5 * math.exp(-0.04 * ex_years)
    assert result.price == pytest.approx(
        bsm("put", escrowed, 100, years(**life), 0.04, 0.3), abs=1e-9
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"sigma": None},  # neither volatility nor mark
        {"mark": src(5.0)},  # both
        {"forward": src(100.0), "exercise": "american"},
        {"cross_check": True},  # a cross-check needs an American contract
        {"numerics": {"tree_steps": 100}},  # a Leisen-Reimer tree needs an odd step count
    ],
)
def test_an_inconsistent_request_is_rejected(bad):
    with pytest.raises(ValueError):
        request(**bad)
