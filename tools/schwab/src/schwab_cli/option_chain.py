"""`schwab option chain`: every listed call for an Underlying as one Quote Set (plan-v2 for /prototype/roundtrip).

One read-only GET on /marketdata/v1/chains (ADR 0004), plus the Treasury curve for each expiry's rate. Nothing is priced
here: the caller solves each contract's Mark-implied IV with the pricing engine. Output is percent, as for `option price`.
"""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from pricing_engine import TreasuryCurves

from schwab_cli.schwab_inputs import NEW_YORK, Get, SchwabDataError, _get_json, default_curves

KINDS = {"CALL": "C", "PUT": "P"}
SIDES = {"CALL": ("callExpDateMap",), "PUT": ("putExpDateMap",), "ALL": ("callExpDateMap", "putExpDateMap")}


def full_chain_path(symbol: str, *, contract_type: str, from_date: str | None) -> str:
    path = f"/marketdata/v1/chains?symbol={quote(symbol, safe='')}&contractType={contract_type}"
    return path + (f"&fromDate={from_date}" if from_date else "")


def run_option_chain(
    symbol: str,
    *,
    now: datetime,
    get: Get | None = None,
    curves: TreasuryCurves | None = None,
    from_date: str | None = None,
    contract_type: str = "CALL",
) -> dict[str, Any]:
    """The Quote Set: spot, and bid, ask, Mark, delta, Schwab IV, rate and quote time per contract."""
    if get is None:
        from schwab_cli.http_client import schwab_get

        get = schwab_get
    body = _get_json(get, full_chain_path(symbol, contract_type=contract_type, from_date=from_date), "option chain")
    spot = body.get("underlyingPrice")
    if spot is None:
        raise SchwabDataError(f"Schwab's chain for {symbol!r} has no underlyingPrice")
    curves = curves or default_curves()
    today = now.astimezone(NEW_YORK).date()
    rates: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    contracts = []
    for side in SIDES[contract_type]:
        for strikes in (body.get(side) or {}).values():
            for rows in strikes.values():
                for row in rows:
                    expiry = row["expirationDate"][:10]
                    if expiry not in rates:
                        quoted = curves.rate(
                            valuation_date=today,
                            expiry=datetime.fromisoformat(expiry).date(),
                            fallback_percent=body.get("interestRate"),
                        )
                        rates[expiry] = {"value": quoted.value * 100, "from": quoted.from_}
                        if quoted.curve_date:
                            rates[expiry]["curveDate"] = quoted.curve_date.isoformat()
                        elif not warnings:
                            warnings.append("no Treasury curve: the rate is Schwab's chain interestRate")
                    contracts.append(
                        {
                            "occ": row["symbol"],
                            "expiry": expiry,
                            "strike": float(row["strikePrice"]),
                            "kind": KINDS[row["putCall"]],
                            "bid": row.get("bid"),
                            "ask": row.get("ask"),
                            "mark": row.get("mark"),
                            "delta": row.get("delta"),
                            "iv": row.get("volatility"),
                            "rate": rates[expiry]["value"],
                            "spot": spot,
                            "quoteTime": datetime.fromtimestamp(row["quoteTimeInLong"] / 1000, tz=UTC).isoformat(),
                        }
                    )
    return {"symbol": symbol, "takenAt": now.isoformat(), "spot": spot, "rates": rates, "warnings": warnings, "contracts": contracts}
