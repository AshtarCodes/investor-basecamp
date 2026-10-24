from datetime import date
from typing import Any

import pytest
from support import priced, request, src

from pricing_engine import price

DIVIDENDS: list[dict[str, Any]] = [
    {"ex_date": date(2026, 11, 20), "amount": 0.80, "from": "test fixture"},
    {"ex_date": date(2027, 2, 19), "amount": 0.80, "from": "test fixture"},
]

# The two fixtures the spikes used: a 103%-vol call, and a dividend-paying in-the-money put.
FIXTURES: dict[str, dict[str, Any]] = {
    "103% call": dict(
        right="call", exercise="american", spot=25.37, strike=22.0, rate=0.042, sigma=1.03,
        life={"days": 80},
    ),
    "dividend-paying ITM put": dict(
        right="put", exercise="american", spot=100.0, strike=105.0, rate=0.042, sigma=0.34,
        expiry=date(2027, 4, 16), life={"days": 172, "hours": 10}, dividends=DIVIDENDS,
    ),
}  # fmt: skip


@pytest.mark.parametrize("name", FIXTURES)
def test_mark_implied_iv_recovers_the_generating_sigma_to_1e_4_vol_points(name):
    fixture = FIXTURES[name]
    generating = fixture["sigma"]
    mark = priced(request(**fixture))

    solved = price(request(**{**fixture, "sigma": None, "mark": src(mark, "schwab mark")}))

    assert solved.iv is not None and solved.iv.value is not None
    assert solved.iv.value == pytest.approx(generating, abs=1e-4 / 100)  # 1e-4 vol points
    assert solved.iv.reason is None and solved.iv.residual is None
    assert solved.price == pytest.approx(mark, abs=1e-9)
    assert solved.flags == []


def test_the_result_echoes_the_solved_sigma_with_the_marks_provenance():
    mark = priced(request(sigma=0.4))
    solved = price(request(sigma=None, mark=src(mark, "schwab chain mark")))
    assert solved.inputs.volatility is not None
    assert solved.iv is not None
    assert solved.inputs.volatility.value == solved.iv.value
    assert "schwab chain mark" in solved.inputs.volatility.from_
    assert solved.inputs.spot.from_ == "test fixture"


def test_a_european_mark_solves_through_the_forward_model():
    mark = priced(request(strike=105, sigma=0.22, life={"days": 45}))
    solved = price(request(strike=105, sigma=None, mark=src(mark), life={"days": 45}))
    assert solved.iv is not None
    assert solved.iv.value == pytest.approx(0.22, abs=1e-6)


def test_a_mark_at_or_below_intrinsic_has_no_iv_but_a_residual():
    # American put, spot 90, strike 100: intrinsic is 10.
    put: dict[str, Any] = {
        "right": "put", "exercise": "american", "spot": 90, "strike": 100, "life": {"days": 30}
    }  # fmt: skip
    below = price(request(**put, sigma=None, mark=src(9.5)))
    floor = priced(request(**put, sigma=0.01))
    assert below.iv is not None
    assert below.iv.value is None
    assert below.iv.reason == "at_or_below_intrinsic"
    assert below.iv.residual == pytest.approx(9.5 - floor, abs=1e-12)
    assert below.price is None and below.greeks is None
    assert "no_iv" in below.flags


def test_a_zero_mark_on_an_out_of_the_money_option_is_at_or_below_intrinsic():
    result = price(request(strike=130, sigma=None, mark=src(0.0), life={"days": 30}))
    assert result.iv is not None and result.iv.reason == "at_or_below_intrinsic"


@pytest.mark.parametrize(
    ("right", "mark", "gap"),
    [("put", 0.001, "below"), ("call", 200.0, "above")],
)
def test_a_mark_no_sigma_brackets_has_no_iv_a_reason_and_a_residual(right, mark, gap):
    # At-the-money, 30 days: sigma in [0.01, 5.0] spans roughly 0.11 to 24 for the put.
    result = price(request(right=right, sigma=None, mark=src(mark), life={"days": 30}))
    floor = priced(request(right=right, sigma=0.01, life={"days": 30}))
    assert result.iv is not None and result.iv.residual is not None
    assert result.iv.value is None
    assert result.iv.reason == "no_bracket"
    assert result.iv.residual == pytest.approx(mark - floor, abs=1e-12)
    assert (result.iv.residual < 0) == (gap == "below")
