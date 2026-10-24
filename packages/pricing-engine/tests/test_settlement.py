from datetime import UTC, date, datetime

import pytest

from pricing_engine import UnknownRootError, settlement_instant


def utc(instant: datetime) -> datetime:
    return instant.astimezone(UTC)


def test_equity_settles_at_4pm_eastern_during_daylight_time():
    assert utc(settlement_instant("SPY", date(2026, 10, 30))) == datetime(
        2026, 10, 30, 20, 0, tzinfo=UTC
    )


def test_equity_settles_at_4pm_eastern_during_standard_time():
    assert utc(settlement_instant("AAPL", date(2026, 11, 20))) == datetime(
        2026, 11, 20, 21, 0, tzinfo=UTC
    )


def test_the_2026_11_01_fall_back_is_honoured_on_both_sides():
    # EDT (UTC-4) through Saturday-night 2026-10-31, EST (UTC-5) from 2026-11-01 02:00.
    before = utc(settlement_instant("SPY", date(2026, 10, 30)))
    after = utc(settlement_instant("SPY", date(2026, 11, 2)))
    assert before == datetime(2026, 10, 30, 20, 0, tzinfo=UTC)
    assert after == datetime(2026, 11, 2, 21, 0, tzinfo=UTC)


def test_the_2027_03_14_spring_forward_is_honoured_on_both_sides():
    assert utc(settlement_instant("SPY", date(2027, 3, 12))) == datetime(
        2027, 3, 12, 21, 0, tzinfo=UTC
    )
    assert utc(settlement_instant("SPY", date(2027, 3, 15))) == datetime(
        2027, 3, 15, 20, 0, tzinfo=UTC
    )


@pytest.mark.parametrize("root", ["SPXW", "XSP"])
def test_pm_settled_index_roots_settle_at_4pm_eastern(root: str):
    assert utc(settlement_instant(root, date(2026, 10, 30))) == datetime(
        2026, 10, 30, 20, 0, tzinfo=UTC
    )


def test_am_settled_spx_settles_at_930am_eastern():
    assert utc(settlement_instant("SPX", date(2026, 11, 20))) == datetime(
        2026, 11, 20, 14, 30, tzinfo=UTC
    )
    assert utc(settlement_instant("SPX", date(2026, 10, 30))) == datetime(
        2026, 10, 30, 13, 30, tzinfo=UTC
    )


def test_the_instant_is_timezone_aware_in_new_york():
    instant = settlement_instant("SPY", date(2026, 10, 30))
    assert instant.tzinfo is not None
    assert str(instant.tzinfo) == "America/New_York"


@pytest.mark.parametrize("root", ["", "spy", "NDX", "VIX", "TOOLONGROOT", "SP Y", "123"])
def test_an_unknown_or_unsupported_root_is_an_error(root: str):
    with pytest.raises(UnknownRootError):
        settlement_instant(root, date(2026, 10, 30))
