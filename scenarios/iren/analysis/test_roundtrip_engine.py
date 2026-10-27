"""The v2 engine at its public function, run(), with a hand-checkable pricer: every option is worth its intrinsic value.

Run from the repo root: uv run --project packages/pricing-engine pytest scenarios/iren/analysis
"""

import pytest

import roundtrip_engine as eng

QUOTES = {
    "takenAt": "2026-10-27T14:05:00-04:00",
    "spot": 25.0,
    "contracts": [
        {"expiry": "2028-01-21", "strike": 20, "kind": "C", "bid": 5.5, "ask": 6.0, "mark": 5.75, "delta": 0.8, "iv": 90, "rate": 4, "spot": 25.0, "quoteTime": "2026-10-27T14:05:00-04:00"},
        {"expiry": "2028-01-21", "strike": 40, "kind": "C", "bid": 1.8, "ask": 2.0, "mark": 1.9, "delta": 0.4, "iv": 95, "rate": 4, "spot": 25.0, "quoteTime": "2026-10-27T14:05:00-04:00"},
    ],
}


def intrinsic(leg, d, spot):
    return max(spot - leg["strike"], 0.0) if leg["kind"] == "C" else max(leg["strike"] - spot, 0.0)


def call(strike, n, expiry="2028-01-21"):
    return {"id": f"c{strike}", "contracts": n, "legs": [{"expiry": expiry, "strike": strike, "kind": "C", "side": 1}]}


def spread(n):
    return {"id": "s20-40", "contracts": n, "legs": [{"expiry": "2028-01-21", "strike": 20, "kind": "C", "side": 1}, {"expiry": "2028-01-21", "strike": 40, "kind": "C", "side": -1}]}


def build(*sleeves, budget=10_000):
    return {"id": "b", "budget": budget, "sleeves": list(sleeves)}


def path(*points):
    return {"id": "p", "weight": 1, "points": [{"date": d, "price": p, "action": a, "sellPct": pct} for d, p, a, pct in points]}


def run(b, p, debt=0.0):
    return eng.run(b, p, QUOTES, debt, intrinsic)


def test_all_shares_rides_the_path_to_its_last_point():
    r = run(build(), path(("2027-12-31", 50, "hold", None)))
    assert r["total"] == pytest.approx(20_000)
    assert r["end"] == "2027-12-31"


def test_a_call_still_held_is_sold_the_trading_day_before_expiry_into_shares():
    # 1 x $20 call at the $6 ask leaves $9,400 for 376 shares; on 2028-01-20 IREN is still $50, the call fetches $3,000
    r = run(build(call(20, 1)), path(("2027-12-31", 50, "hold", None)))
    assert r["end"] == "2028-01-20"
    assert r["total"] == pytest.approx(376 * 50 + 3_000)
    assert [e["type"] for e in r["events"]] == ["expiry"]
    assert r["events"][0]["contracts"] == 1


def test_the_day_before_a_monday_expiry_is_the_friday():
    assert eng.sale_date("2027-06-21") == "2027-06-18"


def test_sell_half_of_three_contracts_sells_two_and_banks_the_money_at_zero():
    # 3 x $20 calls cost $1,800, so 328 shares; at $40 two calls fetch $4,000 (cash), the third $3,000 at expiry (60 shares)
    r = run(build(call(20, 3)), path(("2027-06-30", 40, "sell_cash", 50), ("2027-12-31", 50, "hold", None)))
    assert r["total"] == pytest.approx(4_000 + (328 + 60) * 50)
    action = r["events"][0]
    assert (action["type"], action["date"], action["contracts"], action["amount"]) == ("action", "2027-06-30", 2, 4_000)


def test_selling_a_quarter_of_one_contract_sells_none():
    r = run(build(call(20, 1)), path(("2027-06-30", 40, "sell_cash", 25), ("2027-12-31", 50, "hold", None)))
    assert r["total"] == pytest.approx(376 * 50 + 3_000)
    assert r["events"][0]["contracts"] == 0


def test_sell_into_shares_buys_at_that_points_price_and_never_sells_shares():
    # the call's $2,000 at $40 buys 50 shares; the 376 bought at entry are untouched
    r = run(build(call(20, 1)), path(("2027-06-30", 40, "sell_shares", 100), ("2027-12-31", 50, "hold", None)))
    assert r["total"] == pytest.approx((376 + 50) * 50)


def test_an_action_sells_spread_sleeves_too():
    # 2 x 20/40 spreads at $6.00 ask less $1.80 bid cost $840, so 366.4 shares; at $50 one spread fetches $2,000 (cash),
    # the other $1,500 at expiry with IREN at $35
    r = run(build(spread(2)), path(("2027-06-30", 50, "sell_cash", 50), ("2027-12-31", 35, "hold", None)))
    assert r["total"] == pytest.approx(2_000 + 366.4 * 35 + 1_500)


def test_debt_comes_from_cash_first_then_shares():
    # the call's $2,000 is banked in June; on 2027-11-30 wealth is $2,000 + 376 x $50 = $20,800, so 25% of the gain is
    # $2,700: all $2,000 of cash, then 14 shares
    r = run(build(call(20, 1)), path(("2027-06-30", 40, "sell_cash", 100), ("2027-11-30", 50, "hold", None)), debt=0.25)
    assert r["debt"] == pytest.approx(2_700)
    assert r["wealth"] == pytest.approx(362 * 50)
    assert r["total"] == pytest.approx(20_800)


def test_debt_sells_the_highest_leverage_sleeve_first_in_whole_contracts():
    # leverage: the $40 call 0.4 x $25 / $2 = 5, the $20 call 0.8 x $25 / $6 = 3.3. On 2027-11-30 at $50 wealth is
    # 368 x $50 + $3,000 + $1,000 = $22,400, so 10% is $1,240: the $40 call pays $1,000, one $20 call the last $240 and
    # leaves $2,760 in cash. IREN then rises to $60, where the 368 shares are worth $22,080.
    r = run(build(call(40, 1), call(20, 1)), path(("2027-11-30", 50, "hold", None), ("2027-12-31", 60, "hold", None)), debt=0.10)
    assert r["debt"] == pytest.approx(1_240)
    assert r["wealth"] == pytest.approx(2_760 + 368 * 60)
    assert [e["type"] for e in r["events"]] == ["debt"]


def test_no_debt_is_paid_without_a_gain():
    r = run(build(), path(("2027-11-30", 20, "hold", None)), debt=0.5)
    assert r["debt"] == 0


def test_the_trace_records_holdings_after_each_dates_trades_and_adds_up():
    r = eng.run(build(call(20, 3)), path(("2027-06-30", 40, "sell_cash", 50), ("2027-12-31", 50, "hold", None)), QUOTES, 0.0, intrinsic, trace=True)
    t = r["trace"]
    assert t["dates"] == ["2026-10-27", "2027-06-30", "2027-12-31", "2028-01-20"]
    assert t["spot"] == [25.0, 40, 50, 50]
    june = 1
    assert (t["legs"]["stock"][june], t["legs"]["c20"][june], t["legs"]["cash"][june], t["legs"]["total"][june]) == (328 * 40, 2_000, 4_000, 19_120)
    assert t["legs"]["c20"][0] == 1_800  # entry cost on the first day
    assert t["unit"]["c20"] == [0.0, pytest.approx(2_000 / 600 - 1), pytest.approx(3_000 / 600 - 1), None]
    # what each leg added: the calls' $7,000 of proceeds less $1,800; the shares end at $19,400 less $8,200 + $3,000 bought
    assert t["contrib"] == {"stock": pytest.approx(8_200), "c20": pytest.approx(5_200)}
    assert t["legs"]["total"][-1] == pytest.approx(r["total"])


def test_a_build_that_cannot_be_priced_today_says_why():
    assert eng.unpriceable(build(call(20, 1)), QUOTES) is None
    assert eng.unpriceable(build(call(20, 1, expiry="2026-10-23")), QUOTES) == "Oct 2026 $20 call expired"
    assert eng.unpriceable(build(call(25, 1)), QUOTES) == "Jan 2028 $25 call is not listed"
    assert eng.unpriceable(build(call(20, 18)), QUOTES) == "over budget by $800"  # 18 x $600 = $10,800


def test_points_on_or_before_the_quote_day_are_skipped():
    r = run(build(), path(("2026-10-01", 99, "sell_cash", 50), ("2027-12-31", 50, "hold", None)))
    assert r["total"] == pytest.approx(20_000)
    assert r["events"] == []


def test_the_quote_day_is_new_yorks_even_after_8_pm_there():
    # 2026-10-28 01:30 UTC is still Oct 27 in New York, so a point on Oct 28 is in the future and counts
    late = {**QUOTES, "takenAt": "2026-10-28T01:30:00+00:00"}
    r = eng.run(build(), path(("2026-10-28", 50, "hold", None)), late, 0.0, intrinsic)
    assert r["total"] == pytest.approx(20_000)


def test_a_leg_quoted_without_a_bid_or_ask_cannot_be_priced():
    no_ask = {**QUOTES, "contracts": [{**QUOTES["contracts"][0], "ask": None}, QUOTES["contracts"][1]]}
    assert eng.unpriceable(build(call(20, 1)), no_ask) == "Jan 2028 $20 call has no bid or ask"
