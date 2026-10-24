import math
from datetime import date
from pathlib import Path

import pytest

from pricing_engine import TreasuryCurves, TreasuryError, parse_curve

FIXTURES = Path(__file__).parent / "fixtures"
OCTOBER = (FIXTURES / "treasury-202610.xml").read_text()
NOVEMBER_BEFORE_ANY_ENTRY = (FIXTURES / "treasury-202611-empty.xml").read_text()


def test_the_latest_date_in_the_month_is_the_curve():
    assert str(parse_curve(OCTOBER).curve_date) == "2026-10-23"


def test_rate_at_a_quoted_tenor_is_the_converted_par_yield():
    # 4.22% bond-equivalent par yield at 3 months, as a continuous rate: 2·ln(1 + 0.0422/2).
    assert math.isclose(parse_curve(OCTOBER).rate(3 / 12), 2 * math.log(1.0211), abs_tol=1e-9)


def continuous(par_yield_percent: float) -> float:
    return 2 * math.log(1 + par_yield_percent / 200)


def test_rate_between_quoted_tenors_is_linear_in_tenor():
    # 2 months quote 4.16 and 3 months quote 4.22; 2.5 months sits halfway.
    expected = (continuous(4.16) + continuous(4.22)) / 2
    assert math.isclose(parse_curve(OCTOBER).rate(2.5 / 12), expected, abs_tol=1e-9)


def test_rate_below_the_shortest_tenor_is_the_shortest_rate():
    assert math.isclose(parse_curve(OCTOBER).rate(14 / 365), continuous(4.11), abs_tol=1e-9)


def test_rate_beyond_the_longest_tenor_is_the_longest_rate():
    assert math.isclose(parse_curve(OCTOBER).rate(40.0), continuous(5.33), abs_tol=1e-9)


class FakeTreasury:
    """Stands in for the network: serves saved months and counts the requests."""

    def __init__(self, months: dict[str, str]):
        self.months = months
        self.requests: list[str] = []

    def __call__(self, month: str) -> str:
        self.requests.append(month)
        if month not in self.months:
            raise OSError(f"no route to {month}")
        return self.months[month]


VALUATION = date(2026, 10, 24)
THREE_MONTHS_OUT = date(2027, 1, 22)  # 90 days from VALUATION


def test_a_rate_names_its_source_and_curve_date():
    curves = TreasuryCurves(fetch=FakeTreasury({"202610": OCTOBER}))
    rate = curves.rate(valuation_date=VALUATION, expiry=THREE_MONTHS_OUT, fallback_percent=4.043)
    # Linear between the 2-month (4.16) and 3-month (4.22) par yields, worked by hand.
    assert math.isclose(rate.value, 0.04173680359945271, abs_tol=1e-9)
    assert rate.from_ == "treasury-gov"
    assert rate.curve_date == date(2026, 10, 23)


def test_a_month_with_no_entries_yet_uses_the_previous_month():
    fetch = FakeTreasury({"202611": NOVEMBER_BEFORE_ANY_ENTRY, "202610": OCTOBER})
    rate = TreasuryCurves(fetch=fetch).rate(
        valuation_date=date(2026, 11, 2), expiry=date(2027, 2, 1), fallback_percent=4.043
    )
    assert fetch.requests == ["202611", "202610"]
    assert rate.from_ == "treasury-gov"
    assert rate.curve_date == date(2026, 10, 23)


def test_a_failed_fetch_uses_the_callers_fallback_flagged_as_such():
    rate = TreasuryCurves(fetch=FakeTreasury({})).rate(
        valuation_date=VALUATION, expiry=THREE_MONTHS_OUT, fallback_percent=4.043
    )
    assert rate.value == pytest.approx(0.04043)
    assert rate.from_ == "schwab-chain-fallback"
    assert rate.curve_date is None


def test_a_failed_fetch_without_a_fallback_is_an_error():
    with pytest.raises(TreasuryError):
        TreasuryCurves(fetch=FakeTreasury({})).rate(
            valuation_date=VALUATION, expiry=THREE_MONTHS_OUT, fallback_percent=None
        )


def test_a_garbled_month_uses_the_fallback():
    rate = TreasuryCurves(fetch=FakeTreasury({"202610": "<html>maintenance</html>"})).rate(
        valuation_date=VALUATION, expiry=THREE_MONTHS_OUT, fallback_percent=4.043
    )
    assert rate.from_ == "schwab-chain-fallback"


class Clock:
    def __init__(self, now: float = 1_000_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


def quote(curves: TreasuryCurves):
    return curves.rate(valuation_date=VALUATION, expiry=THREE_MONTHS_OUT, fallback_percent=None)


def test_a_fetched_month_is_reused_for_a_day():
    fetch, clock = FakeTreasury({"202610": OCTOBER}), Clock()
    curves = TreasuryCurves(fetch=fetch, now=clock)
    quote(curves)
    clock.now += 23 * 3600
    quote(curves)
    assert fetch.requests == ["202610"]
    clock.now += 2 * 3600
    quote(curves)
    assert fetch.requests == ["202610", "202610"]


def test_a_fetched_month_on_disk_serves_a_new_process_for_a_day(tmp_path: Path):
    clock = Clock()
    first = FakeTreasury({"202610": OCTOBER})
    quote(TreasuryCurves(fetch=first, cache_dir=tmp_path, now=clock))
    clock.now += 3600
    second = FakeTreasury({})
    cached = quote(TreasuryCurves(fetch=second, cache_dir=tmp_path, now=clock))
    assert second.requests == []
    assert cached.from_ == "treasury-gov"
    clock.now += 24 * 3600
    refetch = FakeTreasury({"202610": OCTOBER})
    quote(TreasuryCurves(fetch=refetch, cache_dir=tmp_path, now=clock))
    assert refetch.requests == ["202610"]


def test_a_month_with_no_entries_is_asked_for_again():
    fetch = FakeTreasury({"202611": NOVEMBER_BEFORE_ANY_ENTRY, "202610": OCTOBER})
    curves = TreasuryCurves(fetch=fetch)
    for _ in range(2):
        curves.rate(
            valuation_date=date(2026, 11, 2), expiry=date(2027, 2, 1), fallback_percent=None
        )
    assert fetch.requests == ["202611", "202610", "202611"]
