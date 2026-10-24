from __future__ import annotations

import json
import math
import urllib.parse
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from schwab_cli.fx_session import is_fx_market_open

USDX_K = 50.14348112

# Single source of truth: internal pair key → (Schwab symbol, ICE exponent).
USDX_LEGS: dict[str, tuple[str, float]] = {
    "EURUSD": ("EUR/USD", -0.576),
    "USDJPY": ("USD/JPY", 0.136),
    "GBPUSD": ("GBP/USD", -0.119),
    "USDCAD": ("USD/CAD", 0.091),
    "USDSEK": ("USD/SEK", 0.042),
    "USDCHF": ("USD/CHF", 0.036),
}

PRICE_FIELD = "mark"
LEG_SPREAD_MAX_SEC = 60


class UsdxQuoteError(ValueError):
    """All-or-nothing quote validation failed."""


@dataclass(frozen=True)
class LegQuote:
    schwab_symbol: str
    price: float
    quote_time_ms: int

    @property
    def quote_time(self) -> datetime:
        return datetime.fromtimestamp(self.quote_time_ms / 1000, tz=UTC)


def compute_usdx(rates: dict[str, float]) -> float:
    product = USDX_K
    for pair, (_, exponent) in USDX_LEGS.items():
        product *= math.pow(rates[pair], exponent)
    return product


def usdx_quotes_path() -> str:
    encoded = ",".join(
        urllib.parse.quote(schwab_sym, safe="") for _, (schwab_sym, _) in USDX_LEGS.items()
    )
    return f"/marketdata/v1/quotes?symbols={encoded}"


def parse_leg_quotes(body: dict[str, Any]) -> dict[str, LegQuote]:
    invalid = (body.get("errors") or {}).get("invalidSymbols") or []
    if invalid:
        msg = f"invalid Schwab symbols: {', '.join(invalid)}"
        raise UsdxQuoteError(msg)

    legs: dict[str, LegQuote] = {}
    missing: list[str] = []

    for pair, (schwab_sym, _) in USDX_LEGS.items():
        row = body.get(schwab_sym)
        if not row:
            missing.append(schwab_sym)
            continue
        quote = row.get("quote") or {}
        raw_price = quote.get(PRICE_FIELD)
        raw_time = quote.get("quoteTime")
        if raw_price is None or raw_time is None:
            missing.append(schwab_sym)
            continue
        price = float(raw_price)
        if price <= 0:
            msg = f"non-positive {PRICE_FIELD} on {schwab_sym}: {price}"
            raise UsdxQuoteError(msg)
        legs[pair] = LegQuote(
            schwab_symbol=schwab_sym,
            price=price,
            quote_time_ms=int(raw_time),
        )

    if missing:
        msg = f"missing or incomplete legs: {', '.join(missing)}"
        raise UsdxQuoteError(msg)

    return legs


def leg_spread_sec(legs: dict[str, LegQuote]) -> float:
    times = [leg.quote_time_ms for leg in legs.values()]
    return (max(times) - min(times)) / 1000.0


def validate_leg_times(legs: dict[str, LegQuote]) -> float:
    spread = leg_spread_sec(legs)
    if spread > LEG_SPREAD_MAX_SEC:
        msg = f"leg quote times spread {spread:.1f}s exceeds {LEG_SPREAD_MAX_SEC}s"
        raise UsdxQuoteError(msg)
    return spread


def build_usdx_payload(
    legs: dict[str, LegQuote],
    *,
    fetched_at: datetime,
) -> dict[str, Any]:
    spread = leg_spread_sec(legs)
    validate_leg_times(legs)

    rates = {pair: leg.price for pair, leg in legs.items()}
    value = compute_usdx(rates)

    quote_times = [leg.quote_time for leg in legs.values()]
    as_of = min(quote_times)

    leg_json: dict[str, Any] = {}
    for pair, leg in legs.items():
        leg_json[leg.schwab_symbol] = {
            "price": leg.price,
            "quoteTime": leg.quote_time.isoformat(),
        }

    return {
        "series": "USDX",
        "method": "ice-formula",
        "source": "schwab-fx",
        "value": round(value, 4),
        "asOf": as_of.isoformat(),
        "legSpreadSec": spread,
        "marketOpen": is_fx_market_open(fetched_at),
        "legs": leg_json,
        "fetchedAt": fetched_at.astimezone(UTC).isoformat(),
    }


def parse_schwab_quotes_json(text: str) -> dict[str, Any]:
    return json.loads(text)
