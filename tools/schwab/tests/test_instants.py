from datetime import UTC, date, datetime, timedelta

import pytest

from schwab_cli.instants import days_between, resolve_instant

NOW = datetime(2026, 10, 26, 14, 30, tzinfo=UTC)
EXPIRY = date(2026, 11, 3)  # settles 16:00 EST = 21:00Z, after the 2026-11-01 fall-back
SETTLEMENT = datetime(2026, 11, 3, 21, 0, tzinfo=UTC)


def resolve(mode="theoretical", *, as_of=None, dte=None, offline=False, root="IREN", now=NOW):
    return resolve_instant(
        mode=mode, root=root, expiry=EXPIRY, now=now, as_of=as_of, dte=dte, offline=offline
    )


def test_default_is_the_wall_clock():
    assert resolve() == NOW


def test_dte_counts_back_from_the_settlement_instant_in_elapsed_days():
    assert resolve(dte=3) == SETTLEMENT - timedelta(days=3)
    assert resolve(dte=2.5) == SETTLEMENT - timedelta(days=2.5)


def test_a_date_as_of_means_four_pm_new_york():
    # 2026-10-31 is still daylight time: 16:00 EDT is 20:00Z.
    assert resolve("sell", as_of="2026-10-31") == datetime(2026, 10, 31, 20, 0, tzinfo=UTC)
    # 2026-11-02 is after the fall-back: 16:00 EST is 21:00Z.
    assert resolve("sell", as_of="2026-11-02") == datetime(2026, 11, 2, 21, 0, tzinfo=UTC)


def test_the_daylight_saving_change_is_counted_in_elapsed_time():
    exit_instant = resolve("sell", as_of="2026-10-31")
    assert days_between(exit_instant, SETTLEMENT) == pytest.approx(3 + 1 / 24)


def test_an_iso_datetime_with_an_offset_is_taken_as_given():
    assert resolve("sell", as_of="2026-10-30T10:00:00-04:00") == datetime(
        2026, 10, 30, 14, 0, tzinfo=UTC
    )


def test_an_iso_datetime_without_an_offset_is_refused():
    with pytest.raises(ValueError, match="offset"):
        resolve("sell", as_of="2026-10-30T10:00:00")


def test_dte_wins_when_both_are_given():
    assert resolve("sell", as_of="2026-10-31", dte=3) == SETTLEMENT - timedelta(days=3)


def test_live_dte_longer_than_the_real_life_points_at_offline():
    with pytest.raises(ValueError, match="--offline"):
        resolve(dte=30)


def test_live_exit_in_the_past_points_at_offline():
    with pytest.raises(ValueError, match="--offline"):
        resolve("sell", as_of="2026-10-20")


def test_offline_allows_a_past_instant():
    assert resolve("sell", as_of="2026-10-20", offline=True) == datetime(
        2026, 10, 20, 20, 0, tzinfo=UTC
    )


def test_live_theoretical_takes_only_now_as_its_date():
    with pytest.raises(ValueError, match="--dte"):
        resolve(as_of="2026-10-30")
    with pytest.raises(ValueError, match="--dte"):
        resolve(as_of="2026-10-20")


def test_offline_theoretical_takes_a_date():
    assert resolve(as_of="2026-10-20", offline=True) == datetime(2026, 10, 20, 20, 0, tzinfo=UTC)


def test_an_instant_at_or_after_settlement_is_an_error():
    with pytest.raises(ValueError, match="Settlement"):
        resolve("sell", as_of="2026-11-03")  # 16:00 EST is the settlement instant
    with pytest.raises(ValueError, match="Settlement"):
        resolve("sell", as_of="2026-11-04")
    with pytest.raises(ValueError, match="Settlement"):
        resolve(dte=0)


def test_negative_dte_is_an_error():
    with pytest.raises(ValueError, match="--dte"):
        resolve(dte=-1)


def test_an_unsupported_root_is_the_engines_error():
    with pytest.raises(ValueError, match="NDX"):
        resolve(root="NDX")
