"""`schwab option price`: the engine's first caller (ticket 14).

This module owns the flags, the instant arithmetic, the percent boundary and the JSON shape. The
engine owns the Settlement instant, model choice, the Mark-implied IV, Greeks, flags and the
residual. A scenario (`sell`, `theoretical --dte`) calls the worker's `price_contract` with one
Shock, so the CLI repeats none of the Shock semantics.
"""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Literal

from pricing_engine import (
    BatchContract,
    PriceRequest,
    PriceResult,
    Shock,
    price,
    price_contract,
    settlement_instant,
)
from pricing_engine import TreasuryCurves
from pricing_engine.models import CashDividend, Contract, Numerics, Sourced

from schwab_cli.instants import days_between, resolve_instant
from schwab_cli.occ import OccSymbol, parse_occ
from schwab_cli.schwab_inputs import (
    NEW_YORK,
    Get,
    SchwabDataError,
    default_curves,
    european_forward,
    fetch_analytical_value,
    fetch_chain_facts,
    fetch_fundamentals,
    fetch_option_quote,
    map_dividends,
    quote_age_warning,
)

Mode = Literal["theoretical", "expiry", "sell", "both"]
Exercise = Literal["american", "european"]

# Calendar seconds over a 365-day year: the engine's convention for T (its own `problem.py`).
SECONDS_PER_YEAR = 365 * 86400


@dataclass(frozen=True)
class OptionPriceArgs:
    """The flags of `schwab option price`. Percent flags are percent; the boundary is `_decimal`."""

    symbol: str
    mode: Mode = "theoretical"
    offline: bool = False
    spot: float | None = None
    vol: float | None = None
    vol_unit: Literal["percent", "decimal"] = "percent"
    rate: float | None = None
    dte: float | None = None
    as_of: str | None = None
    expected_spot: float | None = None
    entry: float | None = None
    contracts: int = 1
    model: Literal["auto", "american", "european"] = "auto"
    no_div: bool = False
    div_yield: float | None = None


@dataclass
class PricingInputs:
    """What the engine needs about one contract, however it was gathered (flags or Schwab)."""

    occ: OccSymbol
    exercise: Exercise
    spot: Sourced
    rate: Sourced
    rate_curve_date: str | None
    mark: Sourced | None
    volatility: Sourced | None
    dividends: tuple[CashDividend, ...]
    continuous_yield: Sourced | None
    dividend_info: dict[str, str]
    forward: Sourced | None = None
    schwab: dict[str, Any] | None = None
    default_entry: Sourced | None = None
    warnings: list[str] = field(default_factory=list)


def _percent(value: float) -> float:
    """The one place an engine decimal becomes a percent."""
    return value * 100


def _decimal(value: float, unit: Literal["percent", "decimal"] = "percent") -> float:
    """The one place a flag becomes an engine decimal."""
    return value if unit == "decimal" else value / 100


def _validate(args: OptionPriceArgs) -> None:
    if args.no_div and args.div_yield is not None:
        raise ValueError("--no-div and --div-yield conflict: --div-yield replaces any schedule")
    if args.mode in ("expiry", "sell", "both") and args.expected_spot is None:
        raise ValueError(f"--mode {args.mode} needs --expected-spot")
    if args.spot is not None and args.mode in ("sell", "expiry"):
        raise ValueError("--spot is for theoretical only; sell prices at --expected-spot")
    if args.contracts < 1:
        raise ValueError("--contracts must be at least 1")
    if not args.offline:
        return
    if args.mode != "expiry" and args.model == "auto":
        raise ValueError("--offline has no quote to read the exercise style from: pass --model")
    if args.mode in ("theoretical", "both") and args.spot is None:
        raise ValueError("--offline theoretical needs --spot")
    if args.mode != "expiry" and args.vol is None:
        raise ValueError("--offline needs --vol (there is no Mark to solve an IV from)")
    if args.mode != "expiry" and args.rate is None:
        raise ValueError("--offline needs --rate (there is no Treasury fetch)")
    if args.mode != "theoretical" and args.entry is None:
        raise ValueError("--offline needs --entry for the P&L baseline")


def _offline_inputs(args: OptionPriceArgs, occ: OccSymbol) -> PricingInputs:
    exercise: Exercise = "american" if args.model == "american" else "european"
    spot_value = args.spot if args.spot is not None else args.expected_spot
    vol = args.vol
    warnings = []
    if args.div_yield is not None:
        yield_ = Sourced(value=_decimal(args.div_yield), from_="cli")
        info = {"treatment": "continuous-yield", "rule": "cli"}
    elif args.no_div:
        yield_ = None
        info = {"treatment": "none", "rule": "cli"}
    else:
        yield_ = None
        info = {"treatment": "none", "rule": "offline-default"}
        warnings.append("offline: no dividend data, so dividends are none; pass --div-yield")
    if exercise == "european":
        warnings.append(
            "offline European option: priced on --spot and --div-yield, no parity forward"
        )
    return PricingInputs(
        occ=occ,
        exercise=exercise,
        spot=Sourced(value=spot_value if spot_value is not None else 1.0, from_="cli"),
        rate=Sourced(value=_decimal(args.rate if args.rate is not None else 0.0), from_="cli"),
        rate_curve_date=None,
        mark=None,
        volatility=None
        if vol is None
        else Sourced(value=_decimal(vol, args.vol_unit), from_="cli"),
        dividends=(),
        continuous_yield=yield_,
        dividend_info=info,
        warnings=warnings,
    )


def _live_inputs(
    args: OptionPriceArgs,
    occ: OccSymbol,
    now: datetime,
    get: Get,
    curves: TreasuryCurves | None,
) -> PricingInputs:
    """Gather one contract's inputs from Schwab and the Treasury curve (every call is a GET)."""
    quote = fetch_option_quote(get, occ)
    schwab: dict[str, Any] = {
        "underlying": quote.underlying,
        "mark": quote.mark,
        "bid": quote.bid,
        "ask": quote.ask,
        "volatility": quote.volatility,
        "quoteTime": quote.quote_time.isoformat() if quote.quote_time else None,
        "underlyingPrice": quote.underlying_price,
        "greeks": quote.greeks,
        "theoreticalOptionValue": quote.theoretical_value,
    }
    warnings = [w for w in [quote_age_warning(quote.quote_time, now)] if w]
    exercise = quote.exercise if args.model == "auto" else args.model
    mark = Sourced(value=quote.mark, from_="schwab-mark")
    spot = Sourced(
        value=args.spot if args.spot is not None else quote.underlying_price,
        from_="cli" if args.spot is not None else "schwab-option-quote",
    )
    volatility = (
        None if args.vol is None else Sourced(value=_decimal(args.vol, args.vol_unit), from_="cli")
    )
    if args.mode == "expiry":
        return PricingInputs(
            occ=occ,
            exercise=exercise or "american",  # expiry needs no model, only a valid contract
            spot=spot,
            rate=Sourced(value=0.0, from_="unused"),
            rate_curve_date=None,
            mark=mark,
            volatility=volatility,
            dividends=(),
            continuous_yield=None,
            dividend_info={"treatment": "none", "rule": "not-used-by-expiry"},
            schwab=schwab,
            default_entry=mark,
            warnings=warnings,
        )
    if not exercise:
        raise SchwabDataError("Schwab's quote has no exerciseType: pass --model")

    fundamentals, underlying_mark = fetch_fundamentals(get, quote.underlying)
    schwab["underlyingQuote"] = {"symbol": quote.underlying, "price": underlying_mark}
    chain = fetch_chain_facts(get, quote.underlying, occ)
    chain_rate = chain.interest_rate
    schwab["chainInterestRate"] = chain_rate
    today = now.astimezone(NEW_YORK).date()
    if args.rate is not None:
        rate: Sourced = Sourced(value=_decimal(args.rate), from_="cli")
        curve_date = None
    else:
        curves = curves or default_curves()
        quoted = curves.rate(valuation_date=today, expiry=occ.expiry, fallback_percent=chain_rate)
        rate, curve_date = quoted, quoted.curve_date.isoformat() if quoted.curve_date else None
        if rate.from_ == "schwab-chain-fallback":
            warnings.append("no Treasury curve: the rate is Schwab's chain interestRate")
    treatment = map_dividends(
        fundamentals,
        valuation_date=today,
        expiry=occ.expiry,
        no_div=args.no_div,
        div_yield_percent=args.div_yield,
    )
    warnings += treatment.warnings
    dividends, yield_, info = treatment.dividends, treatment.continuous_yield, treatment.info
    forward = None
    if exercise == "european":
        life = (settlement_instant(occ.root, occ.expiry) - now).total_seconds() / SECONDS_PER_YEAR
        forward = european_forward(occ, chain, rate=rate.value, life_years=life)
        if args.div_yield is not None or dividends or yield_ is not None:
            warnings.append(
                "a European option is priced on its parity forward, which holds the dividends"
            )
        dividends, yield_ = (), None
        info = {"treatment": "in-parity-forward", "rule": info["rule"]}
    return PricingInputs(
        occ=occ,
        exercise=exercise,
        spot=spot,
        rate=rate,
        rate_curve_date=curve_date,
        mark=mark,
        volatility=volatility,
        dividends=tuple(dividends),
        continuous_yield=yield_,
        dividend_info=info,
        forward=forward,
        schwab=schwab,
        default_entry=mark,
        warnings=warnings,
    )


def _cross_check(
    inputs: PricingInputs, our_iv: float | None, now: datetime, get: Get
) -> dict[str, Any] | None:
    """Our value at Schwab's IV, against Schwab's ANALYTICAL value on our rate (informational).

    Always at today's inputs, so a `--dte` stress changes our price but not this.
    """
    schwab = inputs.schwab
    if schwab is None or inputs.mark is None or schwab.get("volatility") is None:
        return None
    schwab_iv = schwab["volatility"]
    at_schwab_iv = replace(
        inputs, volatility=Sourced(value=schwab_iv / 100, from_="schwab-volatility")
    )
    ours = price(_request(at_schwab_iv, now, spot=inputs.spot, use_mark=False)).price
    analytical = fetch_analytical_value(
        get,
        schwab["underlying"],
        inputs.occ,
        rate_percent=_percent(inputs.rate.value),
        spot=inputs.spot.value,
        volatility_percent=schwab_iv,
        now=now,
    )
    return {
        "ivGapVolPts": None if our_iv is None else _percent(our_iv) - schwab_iv,
        "ourValueAtSchwabIv": ours,
        "vsMark": None if ours is None else ours - inputs.mark.value,
        "schwabAnalytical": analytical,
        "vsSchwabAnalytical": None if ours is None or analytical is None else ours - analytical,
        "schwabDefaultTheoretical": schwab.get("theoreticalOptionValue"),
        "chainInterestRate": schwab.get("chainInterestRate"),
    }


def _scaled_forward(inputs: PricingInputs, spot: Sourced) -> Sourced | None:
    """An explicit forward moves with spot, as the worker's Shock does."""
    forward = inputs.forward
    if forward is None or spot.value == inputs.spot.value:
        return forward
    return Sourced(value=forward.value * spot.value / inputs.spot.value, from_=forward.from_)


def _request(
    inputs: PricingInputs,
    valuation: datetime,
    *,
    spot: Sourced,
    use_mark: bool,
    greeks: bool = False,
) -> PriceRequest:
    forward = _scaled_forward(inputs, spot)
    occ = inputs.occ
    cross_check = greeks and inputs.exercise == "american"
    return PriceRequest(
        contract=Contract(
            root=occ.root,
            expiry=occ.expiry,
            strike=occ.strike,
            right=occ.right,
            exercise=inputs.exercise,
        ),
        valuation=valuation,
        spot=spot,
        rate=inputs.rate,
        mark=inputs.mark if use_mark else None,
        volatility=None if use_mark else inputs.volatility,
        continuous_yield=inputs.continuous_yield or Sourced(value=0.0, from_="default"),
        dividends=list(inputs.dividends),
        forward=forward,
        greeks=greeks,
        cross_check=cross_check,
    )


def _time_to_expiry(occ: OccSymbol, instant: datetime) -> dict[str, Any]:
    settlement = settlement_instant(occ.root, occ.expiry).astimezone(UTC)
    seconds = (settlement - instant).total_seconds()
    return {
        "years": seconds / SECONDS_PER_YEAR,
        "minutes": int(seconds // 60),
        "settlementInstant": settlement.isoformat(),
    }


def _contract_json(occ: OccSymbol, inputs: PricingInputs) -> dict[str, Any]:
    underlying = (inputs.schwab or {}).get("underlying") or occ.root
    return {
        "occ": occ.symbol,
        "underlying": underlying,
        "expiry": occ.expiry.isoformat(),
        "strike": occ.strike,
        "putCall": occ.right.upper(),
    }


def _sourced_json(value: Sourced | None, *, as_percent: bool = False) -> dict[str, Any] | None:
    if value is None:
        return None
    return {"value": _percent(value.value) if as_percent else value.value, "from": value.from_}


def _uses_mark(inputs: PricingInputs) -> bool:
    return inputs.mark is not None and inputs.volatility is None


def _vol_json(inputs: PricingInputs, iv_value: float | None) -> dict[str, Any] | None:
    if _uses_mark(inputs):
        assert inputs.mark is not None
        value = None if iv_value is None else _percent(iv_value)
        return {"value": value, "from": f"mark-implied IV from {inputs.mark.from_}"}
    return _sourced_json(inputs.volatility, as_percent=True)


def _inputs_json(inputs: PricingInputs, spot: Sourced, iv_value: float | None) -> dict[str, Any]:
    rate = _sourced_json(inputs.rate, as_percent=True)
    assert rate is not None
    if inputs.rate_curve_date is not None:
        rate["curveDate"] = inputs.rate_curve_date
    out: dict[str, Any] = {
        "spot": _sourced_json(spot),
        "vol": _vol_json(inputs, iv_value),
        "rate": rate,
        "dividends": inputs.dividend_info,
    }
    if inputs.continuous_yield is not None:
        out["dividends"] = {
            **inputs.dividend_info,
            "yield": _sourced_json(inputs.continuous_yield, as_percent=True),
        }
    if inputs.forward is not None:
        out["forward"] = _sourced_json(_scaled_forward(inputs, spot))
    return out


def _ours_json(result: PriceResult) -> dict[str, Any]:
    check = result.cross_check
    iv = result.iv
    return {
        "model": result.model,
        "value": result.price,
        "greeks": result.greeks.model_dump() if result.greeks else None,
        "leisenReimerCheck": None
        if check is None
        else {"steps": check.steps, "price": check.price, "difference": check.difference},
        "iv": None
        if iv is None or iv.value is not None
        else {"value": None, "reason": iv.reason, "residual": iv.residual},
    }


def _entry(args: OptionPriceArgs, inputs: PricingInputs) -> Sourced:
    if args.entry is not None:
        return Sourced(value=args.entry, from_="cli")
    assert inputs.default_entry is not None  # `_validate` demands --entry offline
    return inputs.default_entry


def _net_pnl(per_share: float, args: OptionPriceArgs) -> dict[str, Any]:
    return {"perShare": per_share, "dollars": per_share * 100 * args.contracts}


def _theoretical(
    inputs: PricingInputs, instant: datetime, now: datetime, *, greeks: bool
) -> dict[str, Any]:
    """The value at the valuation instant: one price, with Greeks unless `--dte` stresses it."""
    use_mark = _uses_mark(inputs)
    if use_mark and instant != now:
        return _scenario(inputs, instant, now, inputs.spot)
    result = price(_request(inputs, instant, spot=inputs.spot, use_mark=use_mark, greeks=greeks))
    # With `--vol` there is no Mark-implied IV; the gap to Schwab's IV is then the override's.
    iv = (
        result.iv.value
        if result.iv
        else result.inputs.volatility.value
        if result.inputs.volatility
        else None
    )
    return {
        "inputs": _inputs_json(inputs, inputs.spot, iv),
        "timeToExpiry": _time_to_expiry(inputs.occ, instant),
        "flags": list(result.flags),
        "results": {"ours": _ours_json(result)},
        "iv": iv,
    }


def _scenario(
    inputs: PricingInputs,
    instant: datetime,
    now: datetime,
    spot: Sourced,
) -> dict[str, Any]:
    """The worker's `price_contract` with one Shock, from today's Mark-implied IV."""
    shock = Shock(
        spot_move=spot.value / inputs.spot.value - 1,
        iv_shift=0.0,
        days_forward=days_between(now, instant),
    )
    base = _request(inputs, now, spot=inputs.spot, use_mark=True)
    priced = price_contract(BatchContract(request=base, shocks=[shock]), "absolute", Numerics())
    flags = list(priced.flags)
    for shock_flags in priced.shock_flags:
        flags += [flag for flag in shock_flags.flags if flag not in flags]
    return {
        "inputs": _inputs_json(inputs, spot, priced.iv.value),
        "timeToExpiry": _time_to_expiry(inputs.occ, instant),
        "flags": flags,
        "iv": priced.iv.value,
        "results": {
            "ours": {
                "value": priced.prices[0],
                "iv": None
                if priced.iv.value is not None
                else {"value": None, "reason": priced.iv.reason, "residual": priced.iv.residual},
            }
        },
    }


def _intrinsic(occ: OccSymbol, spot: float) -> float:
    return max(spot - occ.strike, 0.0) if occ.right == "call" else max(occ.strike - spot, 0.0)


def _expiry_block(args: OptionPriceArgs, inputs: PricingInputs, entry: Sourced) -> dict[str, Any]:
    """Hold to expiration: intrinsic at the terminal spot, no model."""
    assert args.expected_spot is not None
    occ = inputs.occ
    value = _intrinsic(occ, args.expected_spot)
    breakeven = occ.strike + entry.value if occ.right == "call" else occ.strike - entry.value
    return {
        "terminalSpot": args.expected_spot,
        "intrinsic": value,
        "entry": _sourced_json(entry),
        "netPnL": _net_pnl(value - entry.value, args),
        "breakevenSpot": breakeven,
    }


def _sell_block(
    args: OptionPriceArgs,
    inputs: PricingInputs,
    exit_instant: datetime,
    now: datetime,
    entry: Sourced,
) -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
    """The sell block, the `inputs` echo for the exit, and the engine flags."""
    """Sell before expiration: our value at the exit instant if the stock is `--expected-spot`."""
    assert args.expected_spot is not None
    exit_spot = Sourced(value=args.expected_spot, from_="cli")
    use_mark = _uses_mark(inputs)
    priced: dict[str, Any]
    if use_mark:
        priced = _scenario(inputs, exit_instant, now, exit_spot)
    else:
        result = price(_request(inputs, exit_instant, spot=exit_spot, use_mark=False))
        priced = {
            "inputs": _inputs_json(inputs, exit_spot, None),
            "timeToExpiry": _time_to_expiry(inputs.occ, exit_instant),
            "flags": list(result.flags),
            "results": {"ours": _ours_json(result)},
        }
    proceeds = priced["results"]["ours"]["value"]
    block = {
        "exitInstant": exit_instant.isoformat(),
        "expectedSpot": args.expected_spot,
        "timeToExpiry": priced["timeToExpiry"],
        "saleProceeds": proceeds,
        "entry": _sourced_json(entry),
        "netPnL": None if proceeds is None else _net_pnl(proceeds - entry.value, args),
        "iv": priced["results"]["ours"].get("iv"),
    }
    return block, priced["inputs"], list(priced["flags"])


def run_option_price(
    args: OptionPriceArgs,
    *,
    now: datetime,
    get: Get | None = None,
    curves: TreasuryCurves | None = None,
) -> dict[str, Any]:
    """The JSON of one `schwab option price` run. `get` and `curves` are the two network seams."""
    _validate(args)
    occ = parse_occ(args.symbol)
    settlement_instant(occ.root, occ.expiry)  # an unsupported root fails before any network call
    if args.offline:
        inputs = _offline_inputs(args, occ)
        live_get = None
    else:
        if get is None:
            from schwab_cli.http_client import schwab_get

            get = schwab_get
        live_get = get
        inputs = _live_inputs(args, occ, now, get, curves)
    out: dict[str, Any] = {"contract": _contract_json(occ, inputs)}
    if inputs.schwab is not None:
        out["schwab"] = inputs.schwab
    flags: list[str] = []
    results: dict[str, Any] = {}

    if args.mode in ("theoretical", "both"):
        instant = resolve_instant(
            mode="theoretical",
            root=occ.root,
            expiry=occ.expiry,
            now=now,
            as_of=args.as_of,
            dte=args.dte,
            offline=args.offline,
        )
        block = _theoretical(inputs, instant, now, greeks=args.dte is None)
        out["inputs"] = block["inputs"]
        out["timeToExpiry"] = block["timeToExpiry"]
        flags += block["flags"]
        results["theoretical"] = block["results"]
        if live_get is not None:
            check = _cross_check(inputs, block["iv"], now, live_get)
            if check is not None:
                results["theoretical"]["crossCheck"] = check

    if args.mode in ("expiry", "both"):
        results["expiry"] = _expiry_block(args, inputs, _entry(args, inputs))

    if args.mode == "sell":
        exit_instant = resolve_instant(
            mode="sell",
            root=occ.root,
            expiry=occ.expiry,
            now=now,
            as_of=args.as_of,
            dte=args.dte,
            offline=args.offline,
        )
        block, out["inputs"], sell_flags = _sell_block(
            args, inputs, exit_instant, now, _entry(args, inputs)
        )
        out["timeToExpiry"] = block["timeToExpiry"]
        flags += sell_flags
        results["sell"] = block

    out["results"] = results
    out["flags"] = list(dict.fromkeys(flags))
    out["warnings"] = inputs.warnings
    return out
