"""Builders and independent oracles shared by the tests."""

import math
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pricing_engine import PriceRequest, price, settlement_instant

MINUTES_PER_YEAR = 525_600


def src(value: float, origin: str = "test fixture") -> dict[str, Any]:
    return {"value": value, "from": origin}


def before_settlement(root: str, expiry: date, **delta: float) -> datetime:
    """A UTC instant `delta` before the Settlement instant, by elapsed time (not wall clock)."""
    return settlement_instant(root, expiry).astimezone(UTC) - timedelta(**delta)


def request(**options: Any) -> PriceRequest:
    """A valid request with defaults: an at-the-money European SPY call, 91.25 days out.

    Options: right, exercise, strike, spot, rate, sigma (None to give a mark instead), root,
    expiry, valuation, and `life`, the time from valuation to the Settlement instant such as
    {"days": 30}. Anything else (mark, dividends, forward, numerics, ...) goes to the request.
    """
    root = options.pop("root", "SPY")
    expiry = options.pop("expiry", date(2026, 12, 18))
    sigma = options.pop("sigma", 0.3)
    valuation = options.pop("valuation", None)
    life = options.pop("life", None) or {"days": 91, "hours": 6}
    if valuation is None:
        valuation = before_settlement(root, expiry, **life)
    body: dict[str, Any] = {
        "contract": {
            "root": root,
            "expiry": expiry,
            "strike": options.pop("strike", 100.0),
            "right": options.pop("right", "call"),
            "exercise": options.pop("exercise", "european"),
        },
        "valuation": valuation,
        "spot": src(options.pop("spot", 100.0)),
        "rate": src(options.pop("rate", 0.04)),
        **options,
    }
    if sigma is not None:
        body["volatility"] = src(sigma)
    return PriceRequest.model_validate(body)


def priced(req: PriceRequest) -> float:
    """The model price of a request that is expected to have one."""
    amount = price(req).price
    assert amount is not None
    return amount


def years(**delta: float) -> float:
    return timedelta(**delta).total_seconds() / (365 * 86_400)


def normal_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2))


def bsm(
    right: str, spot: float, strike: float, t: float, rate: float, sigma: float, q: float = 0.0
) -> float:
    """Closed-form Black-Scholes-Merton (Haug), an independent oracle for the engine."""
    d1 = (math.log(spot / strike) + (rate - q + sigma * sigma / 2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    if right == "call":
        return spot * math.exp(-q * t) * normal_cdf(d1) - strike * math.exp(-rate * t) * normal_cdf(
            d2
        )
    return strike * math.exp(-rate * t) * normal_cdf(-d2) - spot * math.exp(-q * t) * normal_cdf(
        -d1
    )
