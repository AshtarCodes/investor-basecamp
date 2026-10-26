"""`option price` against replayed live responses: the real engine, fake Schwab and Treasury."""

import json
from datetime import timedelta

import pytest
from schwab_fakes import SYMBOLS, FakeSchwab, now_for, treasury_curves

from schwab_cli.option_price import OptionPriceArgs, run_option_price


def run(key="iren", *, now=None, fake=None, curves=None, **flags):
    fake = fake or FakeSchwab(key)
    args = OptionPriceArgs(symbol=SYMBOLS[key], **flags)
    out = run_option_price(
        args, now=now or now_for(key), get=fake, curves=curves or treasury_curves()
    )
    return out, fake


@pytest.mark.parametrize("key", ["iren", "spy", "xsp"])
def test_theoretical_at_now_reproduces_the_mark(key):
    out, _ = run(key)
    assert out["results"]["theoretical"]["ours"]["value"] == pytest.approx(
        out["schwab"]["mark"], abs=1e-6
    )
    assert out["inputs"]["vol"]["from"] == "mark-implied IV from schwab-mark"
    assert out["flags"] == []


def test_models_follow_the_quotes_exercise_type_not_index_ness():
    models = {key: run(key)[0]["results"]["theoretical"]["ours"]["model"] for key in SYMBOLS}
    assert models == {
        "iren": "american_closed_form",
        "spy": "american_fd_cash_drop",
        "xsp": "black_76",
    }


def test_every_input_carries_provenance_and_the_rate_its_curve_date():
    out, _ = run("iren")
    for name in ("spot", "vol", "rate"):
        assert out["inputs"][name]["from"]
    assert out["inputs"]["spot"]["from"] == "schwab-option-quote"
    assert out["inputs"]["rate"]["from"] == "treasury-gov"
    assert out["inputs"]["rate"]["curveDate"] == "2026-10-23"
    assert 3.5 < out["inputs"]["rate"]["value"] < 5  # percent, not a decimal
    assert out["schwab"]["quoteTime"].startswith("2026-10-26")
    assert out["contract"]["underlying"] == "IREN"


def test_the_underlying_quotes_own_price_is_shown_in_the_schwab_block():
    out, _ = run("iren")
    assert out["schwab"]["underlyingQuote"]["symbol"] == "IREN"
    assert out["schwab"]["underlyingQuote"]["price"] > 0


# sell and the scenario glue


@pytest.mark.parametrize("key", ["iren", "spy", "xsp"])
def test_sell_with_exit_now_at_the_current_spot_equals_theoretical(key):
    theoretical, fake = run(key)
    spot = fake.option_row["quote"]["underlyingPrice"]
    sell, _ = run(key, mode="sell", expected_spot=spot)
    assert sell["results"]["sell"]["saleProceeds"] == pytest.approx(
        theoretical["results"]["theoretical"]["ours"]["value"], abs=1e-9
    )


def test_sell_net_pnl_defaults_its_entry_to_the_schwab_mark():
    out, fake = run("iren", mode="sell", expected_spot=30.0, contracts=2)
    sell = out["results"]["sell"]
    assert sell["entry"] == {"value": fake.option_row["quote"]["mark"], "from": "schwab-mark"}
    assert sell["netPnL"]["perShare"] == pytest.approx(
        sell["saleProceeds"] - sell["entry"]["value"]
    )
    assert sell["netPnL"]["dollars"] == pytest.approx(sell["netPnL"]["perShare"] * 200)


def test_a_date_as_of_equals_dte_across_the_daylight_saving_change():
    # Oct 30 is daylight time, Jan 15 standard: the gap is 77 days and one hour of elapsed time.
    by_date, _ = run("iren", mode="sell", expected_spot=30.0, as_of="2026-10-30")
    by_dte, _ = run("iren", mode="sell", expected_spot=30.0, dte=77 + 1 / 24)
    assert by_date["results"]["sell"]["saleProceeds"] == pytest.approx(
        by_dte["results"]["sell"]["saleProceeds"], abs=1e-9
    )
    plain, _ = run("iren", mode="sell", expected_spot=30.0, as_of="2026-12-15")
    by_days, _ = run("iren", mode="sell", expected_spot=30.0, dte=31)
    assert plain["results"]["sell"]["saleProceeds"] == pytest.approx(
        by_days["results"]["sell"]["saleProceeds"], abs=1e-9
    )


def test_a_european_forward_scales_with_the_exit_spot():
    from pricing_engine import PriceRequest, price

    fake = FakeSchwab("xsp")
    base, _ = run("xsp", fake=fake)
    spot = fake.option_row["quote"]["underlyingPrice"]
    sell, _ = run("xsp", mode="sell", expected_spot=spot * 1.02)
    forward = base["inputs"]["forward"]["value"]
    sigma = base["inputs"]["vol"]["value"] / 100
    twin = price(
        PriceRequest(
            contract={
                "root": "XSP",
                "expiry": "2026-12-18",
                "strike": 768,
                "right": "call",
                "exercise": "european",
            },
            valuation=now_for("xsp"),
            spot={"value": spot * 1.02, "from": "t"},
            rate={"value": base["inputs"]["rate"]["value"] / 100, "from": "t"},
            volatility={"value": sigma, "from": "t"},
            forward={"value": forward * 1.02, "from": "t"},
            numerics={"time_steps": 100, "spot_steps": 200},
        )
    )
    assert sell["results"]["sell"]["saleProceeds"] == pytest.approx(twin.price, rel=1e-6)
    # The echo is the forward actually priced: it moves with the exit spot.
    assert sell["inputs"]["forward"]["value"] == pytest.approx(forward * 1.02, rel=1e-9)


def test_the_parity_forward_is_strike_plus_discounted_call_minus_put_from_the_chain():
    import math

    out, fake = run("xsp")
    marks = {
        side: next(iter(next(iter(fake.chain[side].values())).values()))[0]["mark"]
        for side in ("callExpDateMap", "putExpDateMap")
    }
    rate = out["inputs"]["rate"]["value"] / 100
    years = out["timeToExpiry"]["years"]
    expected = 768 + math.exp(rate * years) * (marks["callExpDateMap"] - marks["putExpDateMap"])
    assert out["inputs"]["forward"]["value"] == pytest.approx(expected, rel=1e-12)
    assert out["inputs"]["dividends"] == {"treatment": "in-parity-forward", "rule": "none"}


def test_a_mark_below_intrinsic_is_reported_as_null_and_carried_in_a_scenario():
    fake = FakeSchwab("iren")
    fake.option_quote[SYMBOLS["iren"]]["quote"]["mark"] = 0.05  # intrinsic is about 0.2
    theoretical, _ = run("iren", fake=fake)
    ours = theoretical["results"]["theoretical"]["ours"]
    assert ours["value"] is None
    assert ours["iv"]["reason"] == "at_or_below_intrinsic"
    assert ours["iv"]["residual"] < 0
    assert "no_iv" in theoretical["flags"]
    spot = fake.option_row["quote"]["underlyingPrice"]
    sell, _ = run("iren", fake=fake, mode="sell", expected_spot=spot)
    assert sell["results"]["sell"]["saleProceeds"] == pytest.approx(0.05, abs=1e-9)
    assert "no_iv" in sell["flags"]


def test_dte_stress_changes_our_price_but_the_cross_check_stays_at_todays_inputs():
    now, fake_now = run("iren")
    stressed, fake = run("iren", dte=30)
    assert stressed["results"]["theoretical"]["ours"]["value"] < 4.9
    assert (
        stressed["results"]["theoretical"]["crossCheck"]
        == now["results"]["theoretical"]["crossCheck"]
    )
    assert (
        fake.analytical_query()["daysToExpiration"]
        == fake_now.analytical_query()["daysToExpiration"]
    )


def test_live_dte_beyond_the_real_life_points_at_offline():
    with pytest.raises(ValueError, match="--offline"):
        run("iren", dte=400)


# the cross-check


def test_cross_check_sends_our_rate_spot_and_schwabs_iv_for_the_real_remaining_days():
    out, fake = run("iren")
    query = fake.analytical_query()
    assert float(query["interestRate"]) == pytest.approx(out["inputs"]["rate"]["value"], abs=1e-5)
    assert float(query["underlyingPrice"]) == out["inputs"]["spot"]["value"]
    assert float(query["volatility"]) == out["schwab"]["volatility"]
    assert query["daysToExpiration"] == "81"  # 2026-10-26 to 2027-01-15, never --dte
    assert query["strategy"] == "ANALYTICAL"
    assert query["fromDate"] == query["toDate"] == "2027-01-15"


def test_cross_check_fields_are_differences_not_assertions():
    out, _ = run("iren")
    check = out["results"]["theoretical"]["crossCheck"]
    ours_iv = out["inputs"]["vol"]["value"]
    assert check["ivGapVolPts"] == pytest.approx(ours_iv - out["schwab"]["volatility"])
    assert check["vsMark"] == pytest.approx(check["ourValueAtSchwabIv"] - out["schwab"]["mark"])
    assert check["vsSchwabAnalytical"] == pytest.approx(
        check["ourValueAtSchwabIv"] - check["schwabAnalytical"]
    )
    assert check["schwabDefaultTheoretical"] == out["schwab"]["theoreticalOptionValue"]
    assert check["chainInterestRate"] == 4.043


def test_the_cross_check_belongs_to_theoretical_and_both_only():
    sell, fake = run("iren", mode="sell", expected_spot=30.0)
    assert "crossCheck" not in sell["results"]["sell"]
    assert not any("ANALYTICAL" in p for p in fake.paths)
    both, _ = run("iren", mode="both", expected_spot=30.0)
    assert "crossCheck" in both["results"]["theoretical"]


# dividends


def spy(fundamental_updates, **flags):
    fake = FakeSchwab("spy")
    fake.fundamental.update(fundamental_updates)
    return run("spy", fake=fake, **flags)[0]


def test_a_quarterly_payer_gets_a_discrete_schedule_named_by_its_rule():
    out, _ = run("spy")
    assert out["inputs"]["dividends"] == {
        "treatment": "discrete",
        "rule": "quarterly-from-next-ex-date",
        "count": 1,
    }


def test_a_past_next_ex_date_is_rolled_forward_with_a_warning():
    out = spy({"nextDivExDate": "2026-09-18T00:00:00Z"})
    assert out["inputs"]["dividends"]["rule"] == "quarterly-from-next-ex-date"
    assert any("rolled forward" in w for w in out["warnings"])


def test_a_daily_payer_with_a_yield_is_a_continuous_yield_with_a_warning():
    out = spy({"divFreq": 0, "divPayAmount": 0.0, "divYield": 3.0, "nextDivExDate": None})
    assert out["inputs"]["dividends"] == {
        "treatment": "continuous-yield",
        "rule": "needs-continuous-yield",
        "yield": {"value": 3.0, "from": "schwab:divYield"},
    }
    assert any("continuous yield" in w for w in out["warnings"])


def test_no_dividend_fields_means_none_and_the_json_names_which():
    zero = {"divFreq": 0, "divPayAmount": 0.0, "divYield": 0.0, "nextDivExDate": None}
    assert spy(zero)["inputs"]["dividends"] == {"treatment": "none", "rule": "none"}
    later = spy({"nextDivExDate": "2027-03-19T00:00:00Z"})
    assert later["inputs"]["dividends"] == {"treatment": "none", "rule": "none-before-expiry"}


@pytest.mark.parametrize(
    ("updates", "rule"),
    [({"divFreq": 2}, "unsupported-frequency"), ({"nextDivExDate": None}, "missing-ex-date")],
)
def test_an_unprojectable_schedule_is_an_error_that_points_at_the_overrides(updates, rule):
    with pytest.raises(ValueError, match=rule) as info:
        spy(updates)
    assert "--no-div" in str(info.value) and "--div-yield" in str(info.value)


def test_no_div_and_div_yield_override_the_schedule():
    forced = spy({}, no_div=True)
    assert forced["inputs"]["dividends"] == {"treatment": "none", "rule": "cli"}
    replaced = spy({}, div_yield=1.5)
    assert replaced["inputs"]["dividends"]["treatment"] == "continuous-yield"
    assert replaced["inputs"]["dividends"]["yield"] == {"value": 1.5, "from": "cli"}


# rate, volatility, staleness, errors


def test_rate_flag_replaces_the_curve_without_fetching_it():
    out, _ = run("iren", rate=5.0, curves=treasury_curves(fail=True))
    assert out["inputs"]["rate"] == {"value": 5.0, "from": "cli"}


def test_without_a_curve_the_chain_rate_is_a_flagged_fallback():
    out, _ = run("iren", curves=treasury_curves(fail=True))
    assert out["inputs"]["rate"]["from"] == "schwab-chain-fallback"
    assert out["inputs"]["rate"]["value"] == pytest.approx(4.043)
    assert any("Treasury" in w for w in out["warnings"])


def test_vol_flag_replaces_the_mark_implied_iv_but_not_the_entry():
    out, _ = run("iren", vol=100.0, mode="sell", expected_spot=30.0)
    assert out["inputs"]["vol"] == {"value": 100.0, "from": "cli"}
    assert out["results"]["sell"]["entry"]["from"] == "schwab-mark"


def test_a_quote_older_than_thirty_minutes_warns():
    fresh, _ = run("iren")
    assert not any("old" in w for w in fresh["warnings"])
    stale, _ = run("iren", now=now_for("iren") + timedelta(minutes=31))
    assert any("minutes old" in w for w in stale["warnings"])


def test_schwab_errors_are_one_line_value_errors():
    with pytest.raises(ValueError, match="HTTP 401"):
        run("iren", fake=FakeSchwab("iren", status=401))
    fake = FakeSchwab("iren")
    fake.option_quote = {}
    with pytest.raises(ValueError, match="OCC symbol"):
        run("iren", fake=fake)


def test_an_unsupported_root_fails_before_any_network_call():
    fake = FakeSchwab("iren")
    with pytest.raises(ValueError, match="NDX"):
        run_option_price(
            OptionPriceArgs(symbol="NDX   261218C20000000"), now=now_for("iren"), get=fake
        )
    assert fake.paths == []


# expiry makes no engine call


def test_live_expiry_is_closed_form_and_needs_only_the_option_quote(monkeypatch):
    import schwab_cli.option_price as module

    def refuse(*_args, **_kwargs):
        raise AssertionError("the engine must not be called for expiry")

    monkeypatch.setattr(module, "price", refuse)
    monkeypatch.setattr(module, "price_contract", refuse)
    out, fake = run("iren", mode="expiry", expected_spot=40.0)
    mark = fake.option_row["quote"]["mark"]
    expiry = out["results"]["expiry"]
    assert expiry["intrinsic"] == 15.0
    assert expiry["entry"] == {"value": mark, "from": "schwab-mark"}
    assert expiry["breakevenSpot"] == pytest.approx(25 + mark)
    assert len(fake.paths) == 1  # the option quote only
    json.dumps(out)


# the scenario glue against the engine called directly (an independent twin of the Shock)


def twin_price(key, *, valuation, spot, sigma_percent, rate_percent, **extra):
    from pricing_engine import PriceRequest, price

    fake = FakeSchwab(key)
    row = fake.option_row
    contract = {
        "root": SYMBOLS[key].split()[0],
        "expiry": {"iren": "2027-01-15", "spy": "2027-01-15", "xsp": "2026-12-18"}[key],
        "strike": {"iren": 25, "spy": 765, "xsp": 768}[key],
        "right": "call",
        "exercise": "european" if row["reference"]["exerciseType"] == "E" else "american",
    }
    request = PriceRequest(
        contract=contract,
        valuation=valuation,
        spot={"value": spot, "from": "t"},
        rate={"value": rate_percent / 100, "from": "t"},
        volatility={"value": sigma_percent / 100, "from": "t"},
        **extra,
    )
    return price(request).price


def test_sell_at_another_spot_equals_the_engine_priced_at_that_spot_and_the_solved_iv():
    base, _ = run("iren")
    sell, _ = run("iren", mode="sell", expected_spot=30.0)
    expected = twin_price(
        "iren",
        valuation=now_for("iren"),
        spot=30.0,
        sigma_percent=base["inputs"]["vol"]["value"],
        rate_percent=base["inputs"]["rate"]["value"],
    )
    assert sell["results"]["sell"]["saleProceeds"] == pytest.approx(expected, abs=1e-9)
    assert sell["results"]["sell"]["saleProceeds"] > base["results"]["theoretical"]["ours"]["value"]


def test_sell_by_dte_equals_the_engine_priced_at_the_exit_instant():
    from schwab_cli.instants import resolve_instant

    base, _ = run("iren")
    sell, _ = run("iren", mode="sell", expected_spot=30.0, dte=31)
    exit_instant = resolve_instant(
        mode="sell",
        root="IREN",
        expiry=__import__("datetime").date(2027, 1, 15),
        now=now_for("iren"),
        as_of=None,
        dte=31,
        offline=False,
    )
    assert exit_instant.isoformat() == "2026-12-15T21:00:00+00:00"
    expected = twin_price(
        "iren",
        valuation=exit_instant,
        spot=30.0,
        sigma_percent=base["inputs"]["vol"]["value"],
        rate_percent=base["inputs"]["rate"]["value"],
    )
    assert sell["results"]["sell"]["saleProceeds"] == pytest.approx(expected, abs=1e-9)


def test_a_european_sell_on_a_vol_override_scales_the_forward_with_spot():
    base, fake = run("xsp", vol=15.0)
    spot = fake.option_row["quote"]["underlyingPrice"]
    sell, _ = run("xsp", vol=15.0, mode="sell", expected_spot=spot * 1.02)
    forward = base["inputs"]["forward"]["value"]
    expected = twin_price(
        "xsp",
        valuation=now_for("xsp"),
        spot=spot * 1.02,
        sigma_percent=15.0,
        rate_percent=base["inputs"]["rate"]["value"],
        forward={"value": forward * 1.02, "from": "t"},
    )
    assert sell["results"]["sell"]["saleProceeds"] == pytest.approx(expected, abs=1e-9)


def test_a_dte_stress_returns_no_greeks_and_a_vol_override_still_gets_the_iv_gap():
    stressed, _ = run("iren", vol=100.0, dte=30)
    assert stressed["results"]["theoretical"]["ours"]["greeks"] is None
    assert stressed["results"]["theoretical"]["ours"]["leisenReimerCheck"] is None
    now, _ = run("iren", vol=100.0)
    assert now["results"]["theoretical"]["ours"]["greeks"] is not None
    gap = now["results"]["theoretical"]["crossCheck"]["ivGapVolPts"]
    assert gap == pytest.approx(100.0 - now["schwab"]["volatility"])
