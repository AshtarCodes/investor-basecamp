"""Read-only Schwab GETs for `option price`, and the mapping from their payloads to engine inputs.

Every call is a GET on /marketdata (never near the order endpoints, ADR 0004). The engine's own
docs leave this mapping to its callers: a payload field becomes a `Sourced` value with a `from`.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal
from urllib.parse import quote
from zoneinfo import ZoneInfo

from pricing_engine import TreasuryCurves, parity_forward, project_dividends
from pricing_engine.models import Sourced

from schwab_cli.http_client import SchwabResponse
from schwab_cli.occ import OccSymbol

Get = Callable[[str], SchwabResponse]

_EXERCISE: dict[str, Literal["american", "european"]] = {"A": "american", "E": "european"}

NEW_YORK = ZoneInfo("America/New_York")
STALE_QUOTE_SECONDS = 30 * 60


class SchwabDataError(ValueError):
    """Schwab answered, but not with what a price needs."""


@dataclass(frozen=True)
class OptionQuote:
    mark: float
    bid: float | None
    ask: float | None
    underlying_price: float
    volatility: float | None  # Schwab IV, percent
    theoretical_value: float | None
    greeks: dict[str, float | None]
    quote_time: datetime | None
    exercise: Literal["american", "european"] | None
    underlying: str


def _get_json(get: Get, path: str, what: str) -> dict[str, Any]:
    response = get(path)
    if response.status_code >= 400:
        raise SchwabDataError(f"Schwab {what} failed: HTTP {response.status_code}")
    try:
        body = json.loads(response.text)
    except json.JSONDecodeError as error:
        raise SchwabDataError(f"Schwab {what} returned unreadable JSON") from error
    return body


def option_quote_path(symbol: str) -> str:
    return f"/marketdata/v1/quotes?symbols={quote(symbol, safe='')}&fields=quote,reference"


def underlying_quote_path(underlying: str) -> str:
    return f"/marketdata/v1/quotes?symbols={quote(underlying, safe='')}&fields=quote,fundamental"


def chain_path(underlying: str, occ: OccSymbol, *, contract_type: str = "ALL") -> str:
    return (
        f"/marketdata/v1/chains?symbol={quote(underlying, safe='')}&contractType={contract_type}"
        f"&fromDate={occ.expiry.isoformat()}&toDate={occ.expiry.isoformat()}&strike={occ.strike:g}"
    )


def analytical_path(
    underlying: str,
    occ: OccSymbol,
    *,
    rate_percent: float,
    spot: float,
    volatility_percent: float,
    days: int,
) -> str:
    """Schwab's own formula on our rate, spot and its IV, for one expiry (ticket 15)."""
    return (
        f"/marketdata/v1/chains?symbol={quote(underlying, safe='')}"
        f"&contractType={'CALL' if occ.right == 'call' else 'PUT'}"
        f"&fromDate={occ.expiry.isoformat()}&toDate={occ.expiry.isoformat()}"
        f"&strategy=ANALYTICAL&interestRate={rate_percent:.6f}&underlyingPrice={spot}"
        f"&volatility={volatility_percent}&daysToExpiration={days}"
    )


def fetch_option_quote(get: Get, occ: OccSymbol) -> OptionQuote:
    body = _get_json(get, option_quote_path(occ.symbol), "option quote")
    row = body.get(occ.symbol)
    if not row:
        raise SchwabDataError(f"Schwab has no quote for {occ.symbol!r}: check the OCC symbol")
    quote_ = row.get("quote") or {}
    reference = row.get("reference") or {}
    mark, underlying_price = quote_.get("mark"), quote_.get("underlyingPrice")
    if mark is None or underlying_price is None:
        raise SchwabDataError(f"Schwab's quote for {occ.symbol!r} has no mark or underlyingPrice")
    quote_time = quote_.get("quoteTime")
    return OptionQuote(
        mark=float(mark),
        bid=quote_.get("bidPrice"),
        ask=quote_.get("askPrice"),
        underlying_price=float(underlying_price),
        volatility=quote_.get("volatility"),
        theoretical_value=quote_.get("theoreticalOptionValue"),
        greeks={name: quote_.get(name) for name in ("delta", "gamma", "theta", "vega", "rho")},
        quote_time=datetime.fromtimestamp(quote_time / 1000, tz=UTC) if quote_time else None,
        exercise=_EXERCISE.get(reference.get("exerciseType") or ""),
        underlying=reference.get("underlying") or occ.root,
    )


def fetch_fundamentals(get: Get, underlying: str) -> tuple[dict[str, Any], float | None]:
    """The Underlying's `fundamental` block and its own Mark (or last price for an index)."""
    body = _get_json(get, underlying_quote_path(underlying), "underlying quote")
    row = body.get(underlying) or {}
    quote_ = row.get("quote") or {}
    price = quote_.get("mark") if quote_.get("mark") is not None else quote_.get("lastPrice")
    return row.get("fundamental") or {}, price


@dataclass(frozen=True)
class ChainFacts:
    interest_rate: float | None  # percent, root level
    call_mark: float | None  # the chain's own Marks at this strike, one snapshot
    put_mark: float | None


def fetch_chain_facts(get: Get, underlying: str, occ: OccSymbol) -> ChainFacts:
    """The chain's root `interestRate` and its call and put Marks at this strike.

    The parity forward uses both Marks from this one response, so it is not skewed by the option
    quote and the chain being two snapshots.
    """
    body = _get_json(get, chain_path(underlying, occ), "option chain")
    marks: dict[str, float | None] = {}
    for side in ("callExpDateMap", "putExpDateMap"):
        marks[side] = None
        for strikes in (body.get(side) or {}).values():
            for key, rows in strikes.items():
                if abs(float(key) - occ.strike) < 1e-6 and rows:
                    marks[side] = rows[0].get("mark")
    return ChainFacts(body.get("interestRate"), marks["callExpDateMap"], marks["putExpDateMap"])


def fetch_analytical_value(
    get: Get,
    underlying: str,
    occ: OccSymbol,
    *,
    rate_percent: float,
    spot: float,
    volatility_percent: float,
    now: datetime,
) -> float | None:
    """Schwab's `theoreticalOptionValue` for this contract on our rate, spot and its own IV.

    `daysToExpiration` is the real calendar days left, never `--dte`.
    """
    days = (occ.expiry - now.astimezone(NEW_YORK).date()).days
    path = analytical_path(
        underlying,
        occ,
        rate_percent=rate_percent,
        spot=spot,
        volatility_percent=volatility_percent,
        days=days,
    )
    body = _get_json(get, path, "ANALYTICAL chain")
    side = "callExpDateMap" if occ.right == "call" else "putExpDateMap"
    for strikes in (body.get(side) or {}).values():
        for rows in strikes.values():
            for row in rows:
                if row.get("symbol") == occ.symbol:
                    return row.get("theoreticalOptionValue")
    return None


def quote_age_warning(quote_time: datetime | None, now: datetime) -> str | None:
    if quote_time is None:
        return "Schwab gave no quoteTime, so the quote's age is unknown"
    age = (now - quote_time).total_seconds()
    if age > STALE_QUOTE_SECONDS:
        return f"the option quote is {age / 60:.0f} minutes old (the market may be closed)"
    return None


@dataclass(frozen=True)
class DividendTreatment:
    dividends: tuple[Any, ...]
    continuous_yield: Sourced | None
    info: dict[str, Any]
    warnings: tuple[str, ...]


def map_dividends(
    fundamentals: dict[str, Any],
    *,
    valuation_date: date,
    expiry: date,
    no_div: bool,
    div_yield_percent: float | None,
) -> DividendTreatment:
    """Each `project_dividends` rule becomes a treatment (ticket 14's decisions table)."""
    if no_div:
        return DividendTreatment((), None, {"treatment": "none", "rule": "cli"}, ())
    if div_yield_percent is not None:
        yield_ = Sourced(value=div_yield_percent / 100, from_="cli")
        return DividendTreatment((), yield_, {"treatment": "continuous-yield", "rule": "cli"}, ())
    projection = project_dividends(
        next_div_ex_date=fundamentals.get("nextDivExDate"),
        div_pay_amount=fundamentals.get("divPayAmount") or 0.0,
        div_freq=fundamentals.get("divFreq") or 0,
        div_yield=fundamentals.get("divYield") or 0.0,
        valuation_date=valuation_date,
        expiry=expiry,
    )
    rule = projection.rule
    if rule in ("unsupported-frequency", "missing-ex-date"):
        raise SchwabDataError(
            f"cannot project this Underlying's dividends (rule {rule}): "
            "pass --no-div to price with none, or --div-yield for a continuous yield"
        )
    if rule == "needs-continuous-yield":
        yield_ = Sourced(value=(fundamentals.get("divYield") or 0.0) / 100, from_="schwab:divYield")
        return DividendTreatment(
            (),
            yield_,
            {"treatment": "continuous-yield", "rule": rule},
            ("dividends are a continuous yield from Schwab's divYield, not a dated schedule",),
        )
    if rule == "quarterly-from-next-ex-date":
        warnings = (
            ("Schwab's nextDivExDate is past; the schedule is rolled forward by quarters",)
            if projection.rolled_forward
            else ()
        )
        info = {"treatment": "discrete", "rule": rule, "count": len(projection.dividends)}
        return DividendTreatment(projection.dividends, None, info, warnings)
    return DividendTreatment((), None, {"treatment": "none", "rule": rule}, ())


def european_forward(
    occ: OccSymbol, chain: ChainFacts, *, rate: float, life_years: float
) -> Sourced:
    """The put-call parity forward from the call and put Marks at this strike (ADR 0001)."""
    if chain.call_mark is None or chain.put_mark is None:
        raise SchwabDataError(
            "a European option is priced on a parity forward, but the chain has no call and put "
            f"Marks at strike {occ.strike:g}"
        )
    value = parity_forward(
        strike=occ.strike,
        call_mark=chain.call_mark,
        put_mark=chain.put_mark,
        rate=rate,
        life=life_years,
    )
    return Sourced(value=value, from_="parity-forward from schwab-chain-marks")


def default_curves() -> TreasuryCurves:
    from schwab_cli.config import local_schwab_dir

    return TreasuryCurves(cache_dir=local_schwab_dir())
