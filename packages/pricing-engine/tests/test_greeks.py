import math
from datetime import UTC, date, datetime
from statistics import NormalDist

import pytest
import QuantLib as ql
from support import priced, request, src, years

from pricing_engine import price

N = NormalDist()

# 2026-07-06 16:00 EDT to 2026-08-05 16:00 EDT: exactly 30 days of elapsed time, no DST change.
EXPIRY = date(2026, 8, 5)
VALUATION = datetime(2026, 7, 6, 20, 0, tzinfo=UTC)
THIRTY_DAYS = years(days=30)


def analytic_european(right, spot, strike, t, rate, sigma):
    """Closed-form delta, gamma, vega (per vol point), theta (per day), rho (per rate point)."""
    sign = 1 if right == "call" else -1
    root_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + (rate + sigma**2 / 2) * t) / (sigma * root_t)
    d2 = d1 - sigma * root_t
    discount = math.exp(-rate * t)
    theta_year = -spot * N.pdf(d1) * sigma / (2 * root_t) - sign * rate * strike * discount * N.cdf(
        sign * d2
    )
    return {
        "delta": N.cdf(d1) if sign == 1 else N.cdf(d1) - 1,
        "gamma": N.pdf(d1) / (spot * sigma * root_t),
        "vega": spot * N.pdf(d1) * root_t / 100,
        "theta": theta_year / 365,
        "rho": sign * strike * t * discount * N.cdf(sign * d2) / 100,
    }


@pytest.mark.parametrize("right", ["call", "put"])
@pytest.mark.parametrize(
    ("life", "strike"), [({"days": 30}, 103), ({"days": 400}, 103), ({"hours": 6}, 100.3)]
)
def test_european_greeks_match_the_closed_form_in_the_stated_units(right, life, strike):
    result = price(
        request(
            right=right, spot=100, strike=strike, rate=0.045, sigma=0.28, life=life, greeks=True
        )
    )
    expected = analytic_european(right, 100, strike, years(**life), 0.045, 0.28)
    greeks = result.greeks
    assert greeks is not None
    assert greeks.delta == pytest.approx(expected["delta"], abs=2e-4)
    assert greeks.gamma == pytest.approx(expected["gamma"], rel=2e-3, abs=1e-6)
    assert greeks.vega == pytest.approx(expected["vega"], rel=1e-4, abs=1e-6)
    assert greeks.rho == pytest.approx(expected["rho"], rel=1e-3, abs=1e-6)
    # Theta is the change over a calendar day; the closed form is the instantaneous rate.
    assert greeks.theta == pytest.approx(expected["theta"], rel=0.03, abs=2e-3)


def quantlib_put():
    """QuantLib's own FD engine on real dates, with no virtual clock, as an independent oracle."""
    today = ql.Date(1, 1, 2030)
    ql.Settings.instance().evaluationDate = today  # the engine module's fixed date
    day_count, calendar = ql.Actual365Fixed(), ql.NullCalendar()

    def build(spot=100.0, sigma=0.30, rate=0.042):
        process = ql.BlackScholesMertonProcess(
            ql.QuoteHandle(ql.SimpleQuote(spot)),
            ql.YieldTermStructureHandle(ql.FlatForward(today, 0.0, day_count)),
            ql.YieldTermStructureHandle(ql.FlatForward(today, rate, day_count)),
            ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, calendar, sigma, day_count)),
        )
        option = ql.VanillaOption(
            ql.PlainVanillaPayoff(ql.Option.Put, 105.0), ql.AmericanExercise(today, today + 30)
        )
        option.setPricingEngine(ql.FdBlackScholesVanillaEngine(process, [], 800, 1600, 0))
        return option

    return build


def test_american_greeks_match_quantlibs_own_engine_values():
    build = quantlib_put()
    oracle = build()
    result = price(
        request(
            right="put",
            exercise="american",
            spot=100,
            strike=105,
            rate=0.042,
            sigma=0.30,
            valuation=VALUATION,
            expiry=EXPIRY,
            greeks=True,
        )
    )
    assert result.remaining_life_years == pytest.approx(THIRTY_DAYS, abs=1e-12)
    greeks = result.greeks
    assert greeks is not None
    assert greeks.delta == pytest.approx(oracle.delta(), abs=2e-3)
    assert greeks.gamma == pytest.approx(oracle.gamma(), rel=0.03)
    assert greeks.theta == pytest.approx(oracle.theta() / 365, abs=2e-3)  # per calendar day

    vega_oracle = (build(sigma=0.31).NPV() - build(sigma=0.29).NPV()) / 2  # per vol point
    rho_oracle = (build(rate=0.052).NPV() - build(rate=0.032).NPV()) / 2  # per rate point
    assert greeks.vega == pytest.approx(vega_oracle, abs=2e-3)
    assert greeks.rho == pytest.approx(rho_oracle, abs=2e-3)


def test_greeks_are_priced_at_the_mark_implied_iv():
    mark = priced(request(strike=105, sigma=0.27, life={"days": 45}))
    solved = price(request(strike=105, sigma=None, mark=src(mark), life={"days": 45}, greeks=True))
    direct = price(request(strike=105, sigma=0.27, life={"days": 45}, greeks=True))
    assert solved.greeks is not None and direct.greeks is not None
    assert solved.greeks.vega == pytest.approx(direct.greeks.vega, rel=1e-6)


def test_greeks_are_omitted_unless_asked_for():
    assert price(request()).greeks is None


def test_an_explicit_forward_moves_with_spot_for_delta():
    # A forward of spot grown at the rate must give the same delta as plain spot pricing.
    forward = 100 * math.exp(0.05)
    plain = price(request(spot=100, rate=0.05, life={"days": 365}, greeks=True))
    explicit = price(
        request(spot=100, rate=0.05, life={"days": 365}, forward=src(forward), greeks=True)
    )
    assert plain.greeks is not None and explicit.greeks is not None
    assert explicit.greeks.delta == pytest.approx(plain.greeks.delta, abs=1e-6)


def test_an_expired_contract_has_only_a_spot_sensitivity():
    result = price(
        request(right="put", strike=110, spot=100, valuation=datetime(2026, 12, 19, tzinfo=UTC),
                greeks=True)
    )  # fmt: skip
    assert result.flags == ["expired"]
    assert result.price == pytest.approx(10.0)
    assert result.greeks is not None
    assert result.greeks.delta == pytest.approx(-1.0, abs=1e-6)
    assert (result.greeks.vega, result.greeks.theta, result.greeks.rho) == (0.0, 0.0, 0.0)
