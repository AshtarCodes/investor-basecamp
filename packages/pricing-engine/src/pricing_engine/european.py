"""European pricing: Black-Scholes-Merton, written on the forward (Black 1976)."""

import math
from statistics import NormalDist

_NORMAL = NormalDist()


def black_76(
    *, right: int, forward: float, strike: float, life: float, rate: float, sigma: float
) -> float:
    """Discounted forward-based price. `right` is +1 for a call and -1 for a put."""
    discount = math.exp(-rate * life)
    if life <= 0 or sigma <= 0:
        return discount * max(right * (forward - strike), 0.0)
    total_vol = sigma * math.sqrt(life)
    d1 = (math.log(forward / strike) + total_vol * total_vol / 2) / total_vol
    d2 = d1 - total_vol
    return discount * right * (forward * _NORMAL.cdf(right * d1) - strike * _NORMAL.cdf(right * d2))


def parity_forward(
    *, strike: float, call_mark: float, put_mark: float, rate: float, life: float
) -> float:
    """The forward implied by put-call parity, `F = K + e^{rT}(C - P)`.

    The caller supplies a call Mark and a put Mark at the same strike and expiry, with `life`
    the years to the Settlement instant.
    """
    return strike + math.exp(rate * life) * (call_mark - put_mark)
