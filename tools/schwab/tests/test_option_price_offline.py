import math
from datetime import UTC, datetime

import pytest

from schwab_cli.option_price import OptionPriceArgs, run_option_price

NOW = datetime(2026, 10, 26, 14, 30, tzinfo=UTC)
CALL = "XSP   261120C00700000"
PUT = "XSP   261120P00700000"


def run(symbol=CALL, **overrides):
    defaults = {
        "symbol": symbol,
        "offline": True,
        "model": "european",
        "spot": 700.0,
        "vol": 20.0,
        "rate": 4.0,
    }
    return run_option_price(OptionPriceArgs(**{**defaults, **overrides}), now=NOW)


def test_offline_theoretical_obeys_put_call_parity_in_the_stated_units():
    call = run(CALL)["results"]["theoretical"]["ours"]["value"]
    put = run(PUT)["results"]["theoretical"]["ours"]["value"]
    years = run(CALL)["timeToExpiry"]["years"]
    # Rate flag is 4 percent; parity is written here independently of the engine.
    assert call - put == pytest.approx(700 - 700 * math.exp(-0.04 * years), abs=1e-6)


def test_vol_flag_is_percent_and_decimal_unit_is_equivalent_and_output_is_percent():
    as_percent = run(vol=100.0)
    as_decimal = run(vol=1.0, vol_unit="decimal")
    assert as_percent["results"] == as_decimal["results"]
    assert as_percent["inputs"]["vol"] == {"value": 100.0, "from": "cli"}
    assert as_decimal["inputs"]["vol"] == {"value": 100.0, "from": "cli"}


def test_inputs_carry_provenance_and_rate_is_percent():
    out = run()
    assert out["inputs"]["spot"] == {"value": 700.0, "from": "cli"}
    assert out["inputs"]["rate"]["value"] == pytest.approx(4.0)
    assert out["inputs"]["rate"]["from"] == "cli"
    assert out["contract"] == {
        "occ": CALL,
        "underlying": "XSP",
        "expiry": "2026-11-20",
        "strike": 700.0,
        "putCall": "CALL",
    }
    assert out["timeToExpiry"]["settlementInstant"] == "2026-11-20T21:00:00+00:00"


def test_offline_names_the_missing_dividend_data_in_a_warning():
    out = run()
    assert out["inputs"]["dividends"] == {"treatment": "none", "rule": "offline-default"}
    assert any("dividend" in w for w in out["warnings"])


def test_div_yield_is_percent_and_replaces_the_default():
    with_yield = run(div_yield=2.0)
    assert with_yield["inputs"]["dividends"] == {
        "treatment": "continuous-yield",
        "rule": "cli",
        "yield": {"value": 2.0, "from": "cli"},
    }
    without = run()["results"]["theoretical"]["ours"]["value"]
    assert with_yield["results"]["theoretical"]["ours"]["value"] < without  # a call loses to yield


def test_theoretical_reports_ours_with_the_engines_model_and_greeks():
    ours = run()["results"]["theoretical"]["ours"]
    assert ours["model"] == "black_scholes_merton"
    assert 0 < ours["greeks"]["delta"] < 1
    assert ours["leisenReimerCheck"] is None


@pytest.mark.parametrize(
    ("overrides", "needle"),
    [
        ({"model": "auto"}, "--model"),
        ({"spot": None}, "--spot"),
        ({"vol": None}, "--vol"),
        ({"rate": None}, "--rate"),
        ({"no_div": True, "div_yield": 1.0}, "--no-div"),
    ],
)
def test_offline_missing_or_conflicting_inputs_are_one_line_value_errors(overrides, needle):
    with pytest.raises(ValueError, match=needle):
        run(**overrides)


def test_time_to_expiry_matches_the_engines_remaining_life():
    from pricing_engine import PriceRequest, price

    out = run()
    request = PriceRequest(
        contract={
            "root": "XSP",
            "expiry": "2026-11-20",
            "strike": 700,
            "right": "call",
            "exercise": "european",
        },
        valuation=NOW,
        spot={"value": 700, "from": "t"},
        rate={"value": 0.04, "from": "t"},
        volatility={"value": 0.2, "from": "t"},
    )
    assert out["timeToExpiry"]["years"] == pytest.approx(price(request).remaining_life_years)


# expiry: hold to expiration, no model, no vol.


def test_expiry_call_is_intrinsic_with_net_pnl_and_closed_form_breakeven():
    out = run(
        mode="expiry",
        expected_spot=720.0,
        entry=12.5,
        contracts=3,
        spot=None,
        vol=None,
        rate=None,
        model="auto",
    )
    expiry = out["results"]["expiry"]
    assert expiry["intrinsic"] == 20.0
    assert expiry["netPnL"] == {"perShare": 7.5, "dollars": 7.5 * 100 * 3}
    assert expiry["breakevenSpot"] == 712.5
    assert expiry["entry"] == {"value": 12.5, "from": "cli"}
    assert "inputs" not in out and "timeToExpiry" not in out


def test_expiry_put_out_of_the_money_loses_the_entry():
    out = run(
        PUT,
        mode="expiry",
        expected_spot=720.0,
        entry=9.0,
        spot=None,
        vol=None,
        rate=None,
        model="auto",
    )
    expiry = out["results"]["expiry"]
    assert expiry["intrinsic"] == 0.0
    assert expiry["netPnL"]["perShare"] == -9.0
    assert expiry["breakevenSpot"] == 691.0


def test_offline_expiry_without_entry_is_an_error():
    with pytest.raises(ValueError, match="--entry"):
        run(mode="expiry", expected_spot=720.0, spot=None, vol=None, rate=None, model="auto")


def test_both_carries_theoretical_and_expiry_and_needs_expected_spot():
    out = run(mode="both", expected_spot=720.0, entry=12.5)
    assert set(out["results"]) == {"theoretical", "expiry"}
    with pytest.raises(ValueError, match="--expected-spot"):
        run(mode="both", entry=12.5)


# sell: our value at the exit instant, spot = --expected-spot.


def test_sell_prices_at_the_expected_spot_and_exit_instant_not_at_today():
    sell = run(mode="sell", expected_spot=720.0, entry=12.5, as_of="2026-11-10", spot=None)
    theoretical_at_exit = run(spot=720.0, as_of="2026-11-10")["results"]["theoretical"]["ours"]
    assert sell["results"]["sell"]["saleProceeds"] == theoretical_at_exit["value"]
    assert sell["results"]["sell"]["exitInstant"] == "2026-11-10T21:00:00+00:00"
    assert sell["results"]["sell"]["netPnL"]["perShare"] == pytest.approx(
        theoretical_at_exit["value"] - 12.5
    )


def test_sell_with_dte_wins_over_as_of():
    by_dte = run(mode="sell", expected_spot=720.0, entry=1.0, dte=10, spot=None)
    both = run(mode="sell", expected_spot=720.0, entry=1.0, dte=10, as_of="2026-11-01", spot=None)
    assert by_dte["results"]["sell"] == both["results"]["sell"]


def test_sell_spot_flag_is_refused():
    with pytest.raises(ValueError, match="--spot"):
        run(mode="sell", expected_spot=720.0, entry=1.0)


def test_sell_at_or_after_settlement_is_an_error():
    with pytest.raises(ValueError, match="Settlement"):
        run(mode="sell", expected_spot=720.0, entry=1.0, as_of="2026-11-20", spot=None)


def test_a_zero_spot_is_the_engines_error_not_a_silent_one():
    with pytest.raises(ValueError, match="spot"):
        run(spot=0.0)


def test_a_zero_rate_is_a_valid_rate():
    assert run(rate=0.0)["inputs"]["rate"]["value"] == 0.0


def test_offline_dte_has_no_greeks():
    assert run(dte=10)["results"]["theoretical"]["ours"]["greeks"] is None
