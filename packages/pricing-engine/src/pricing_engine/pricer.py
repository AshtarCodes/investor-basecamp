"""The public pricing entry point."""

from dataclasses import replace
from datetime import datetime

from pricing_engine.american import leisen_reimer
from pricing_engine.clock import years_between
from pricing_engine.greeks import greeks as compute_greeks
from pricing_engine.iv import SIGMA_MIN, solve
from pricing_engine.model import model_of, value
from pricing_engine.models import (
    CrossCheck,
    Flag,
    ImpliedVolatility,
    PricedInputs,
    PriceRequest,
    PriceResult,
    Sourced,
)
from pricing_engine.problem import Problem
from pricing_engine.settlement import EX_DATE_DROP, NEW_YORK, settlement_instant


def build_problem(request: PriceRequest) -> tuple[Problem, list[Flag]]:
    contract = request.contract
    settles_at = settlement_instant(contract.root, contract.expiry)
    life = max(years_between(request.valuation, settles_at), 0.0)
    flags: list[Flag] = []
    dividends: list[tuple[float, float]] = []
    for dividend in request.dividends:
        ex_at = datetime.combine(dividend.ex_date, EX_DATE_DROP, tzinfo=NEW_YORK)
        t = years_between(request.valuation, ex_at)
        if 0 < t < life:
            dividends.append((t, dividend.amount))
        else:
            flags.append("dividend_not_in_life")
    problem = Problem(
        right=1 if contract.right == "call" else -1,
        american=contract.exercise == "american",
        strike=contract.strike,
        spot=request.spot.value,
        forward=None if request.forward is None else request.forward.value,
        sigma=SIGMA_MIN if request.volatility is None else request.volatility.value,
        rate=request.rate.value,
        carry_yield=request.continuous_yield.value + request.borrow_rate.value,
        dividends=tuple(sorted(dividends)),
        life=life,
        numerics=request.numerics,
    )
    return problem, flags


def price(request: PriceRequest) -> PriceResult:
    """Price a contract at a known σ, or solve its Mark-implied IV from a Mark and price at that."""
    settles_at = settlement_instant(request.contract.root, request.contract.expiry)
    problem, flags = build_problem(request)
    if request.hard_to_borrow:
        flags.append("hard_to_borrow")
    if problem.life <= 0:
        flags.append("expired")

    volatility = request.volatility
    implied: ImpliedVolatility | None = None
    if request.mark is not None:
        implied = solve(problem, request.mark.value)
        if implied.value is not None:
            volatility = Sourced(
                value=implied.value, **{"from": f"mark-implied IV from {request.mark.from_}"}
            )
    if implied is not None and implied.value is not None:
        problem = replace(problem, sigma=implied.value)

    amount: float | None = None
    sensitivities = None
    cross_check = None
    if volatility is None:
        flags.append("no_iv")
    else:
        amount = value(problem)
        if request.greeks:
            sensitivities = compute_greeks(problem)
        if request.cross_check and problem.life > 0:
            tree = leisen_reimer(problem)
            cross_check = CrossCheck(
                model="leisen_reimer",
                steps=problem.numerics.tree_steps,
                price=tree,
                difference=tree - amount,
            )
    return PriceResult(
        price=amount,
        model=model_of(problem),
        inputs=PricedInputs(
            spot=request.spot,
            rate=request.rate,
            volatility=volatility,
            continuous_yield=request.continuous_yield,
            borrow_rate=request.borrow_rate,
            dividends=request.dividends,
            forward=request.forward,
        ),
        iv=implied,
        greeks=sensitivities,
        cross_check=cross_check,
        settlement_instant=settles_at,
        remaining_life_years=problem.life,
        flags=list(dict.fromkeys(flags)),
    )
