import pytest
from support import request, src

from pricing_engine import parity_forward, price


@pytest.mark.parametrize("known_forward", [4950.0, 5100.0, 5300.0])
@pytest.mark.parametrize("life", [{"hours": 6}, {"days": 12}, {"days": 200}])
def test_parity_forward_recovers_the_forward_that_generated_the_prices(known_forward, life):
    strike, rate = 5100.0, 0.043
    legs = {
        right: price(
            request(
                right=right,
                root="SPXW",
                strike=strike,
                spot=5000.0,
                rate=rate,
                sigma=0.18,
                life=life,
                forward=src(known_forward),
            )
        )
        for right in ("call", "put")
    }
    assert legs["call"].model == "black_76"
    assert legs["call"].price is not None and legs["put"].price is not None
    recovered = parity_forward(
        strike=strike,
        call_mark=legs["call"].price,
        put_mark=legs["put"].price,
        rate=rate,
        life=legs["call"].remaining_life_years,
    )
    assert recovered == pytest.approx(known_forward, abs=1e-9)


def test_an_explicit_forward_replaces_spot_and_carry():
    # With F = S e^{rT} the explicit forward must agree with plain spot pricing.
    plain = price(request(spot=100, rate=0.05, life={"days": 365}))
    forward = 100 * 1.0512710963760241  # e^{0.05}
    explicit = price(request(spot=100, rate=0.05, life={"days": 365}, forward=src(forward)))
    assert plain.price is not None and explicit.price is not None
    assert explicit.price == pytest.approx(plain.price, abs=1e-9)
