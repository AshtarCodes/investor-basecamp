import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from schwab_cli.fx_session import is_fx_market_open
from schwab_cli.usdx import (
    LEG_SPREAD_MAX_SEC,
    UsdxQuoteError,
    build_usdx_payload,
    compute_usdx,
    parse_leg_quotes,
    validate_leg_times,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_compute_usdx_fixture_rates():
    rates = {
        "EURUSD": 1.119495,
        "USDJPY": 156.8545,
        "GBPUSD": 1.33732,
        "USDCAD": 1.399905,
        "USDSEK": 9.94052,
        "USDCHF": 0.825245,
    }
    assert compute_usdx(rates) == pytest.approx(101.795, abs=0.0001)


def test_six_leg_fixture_builds_payload():
    body = json.loads((FIXTURES / "usdx_six_legs.json").read_text())
    legs = parse_leg_quotes(body)
    fetched_at = datetime(2024, 10, 23, 14, 0, tzinfo=UTC)
    payload = build_usdx_payload(legs, fetched_at=fetched_at)
    assert payload["value"] == 101.795
    assert payload["method"] == "ice-formula"
    assert payload["source"] == "schwab-fx"
    assert payload["series"] == "USDX"
    assert len(payload["legs"]) == 6
    assert payload["legSpreadSec"] == 5.0
    assert payload["marketOpen"] is True


def test_missing_leg_raises():
    body = json.loads((FIXTURES / "usdx_six_legs.json").read_text())
    del body["USD/SEK"]
    with pytest.raises(UsdxQuoteError, match="USD/SEK"):
        parse_leg_quotes(body)


def test_stale_leg_spread_raises():
    body = json.loads((FIXTURES / "usdx_six_legs.json").read_text())
    body["USD/CHF"]["quote"]["quoteTime"] = 1730000000000 + (LEG_SPREAD_MAX_SEC + 1) * 1000
    legs = parse_leg_quotes(body)
    fetched_at = datetime(2024, 10, 23, 14, 0, tzinfo=UTC)
    with pytest.raises(UsdxQuoteError, match="spread"):
        build_usdx_payload(legs, fetched_at=fetched_at)


def test_non_positive_mark_raises():
    body = json.loads((FIXTURES / "usdx_six_legs.json").read_text())
    body["EUR/USD"]["quote"]["mark"] = 0
    with pytest.raises(UsdxQuoteError, match="non-positive"):
        parse_leg_quotes(body)


def test_validate_leg_times_within_window():
    body = json.loads((FIXTURES / "usdx_six_legs.json").read_text())
    legs = parse_leg_quotes(body)
    assert validate_leg_times(legs) == 5.0


def test_fx_weekend_closed_saturday():
    sat = datetime(2024, 10, 26, 12, 0, tzinfo=UTC)
    assert is_fx_market_open(sat) is False


def test_fx_weekend_open_sunday_after_17_ny():
    # 2024-10-27 22:00 UTC = 18:00 EDT (after 17:00 NY)
    sun = datetime(2024, 10, 27, 22, 0, tzinfo=UTC)
    assert is_fx_market_open(sun) is True


def test_fx_weekend_closed_friday_after_17_ny():
    # 2024-10-25 22:00 UTC = 18:00 EDT Friday
    fri = datetime(2024, 10, 25, 22, 0, tzinfo=UTC)
    assert is_fx_market_open(fri) is False
