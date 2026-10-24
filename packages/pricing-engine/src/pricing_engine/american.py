"""American pricing: QuantLib's finite-difference engine with cash dividends, and a tree check."""

import QuantLib as ql

from pricing_engine.clock import VirtualClock
from pricing_engine.problem import Problem

# QuantLib dates are whole days and its evaluation date is global state, so every price uses
# one fixed date and lays the virtual clock out after it.
START = ql.Date(1, 1, 2030)
ql.Settings.instance().evaluationDate = START
DAY_COUNT = ql.Actual365Fixed()
CALENDAR = ql.NullCalendar()


def _process(
    spot: float, rate: float, carry_yield: float, sigma: float
) -> ql.BlackScholesMertonProcess:
    """A flat Black-Scholes-Merton process on the virtual clock. Inputs are already rescaled."""
    return ql.BlackScholesMertonProcess(
        ql.QuoteHandle(ql.SimpleQuote(spot)),
        ql.YieldTermStructureHandle(ql.FlatForward(START, carry_yield, DAY_COUNT)),
        ql.YieldTermStructureHandle(ql.FlatForward(START, rate, DAY_COUNT)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(START, CALENDAR, sigma, DAY_COUNT)),
    )


def _option(problem: Problem, days: int) -> ql.VanillaOption:
    payoff = ql.PlainVanillaPayoff(
        ql.Option.Call if problem.right == 1 else ql.Option.Put, problem.strike
    )
    return ql.VanillaOption(payoff, ql.AmericanExercise(START, START + days))


def cash_drop(problem: Problem) -> float:
    """Finite-difference value with each dividend a cash drop at its ex-date."""
    clock = VirtualClock(problem.life, problem.numerics.clock_days)
    option = _option(problem, clock.days)
    process = _process(
        problem.spot,
        clock.rate(problem.rate),
        clock.rate(problem.carry_yield),
        clock.volatility(problem.sigma),
    )
    schedule = [
        ql.FixedDividend(amount, START + clock.dividend_day(t)) for t, amount in problem.dividends
    ]
    option.setPricingEngine(
        ql.FdBlackScholesVanillaEngine(
            process, schedule, problem.numerics.time_steps, problem.numerics.spot_steps, 0
        )
    )
    return option.NPV()


def leisen_reimer(problem: Problem) -> float:
    """Leisen-Reimer tree on spot less the present value of the dividends (ADR 0001)."""
    clock = VirtualClock(problem.life, problem.numerics.clock_days)
    option = _option(problem, clock.days)
    escrowed = problem.spot - problem.present_value_of_dividends()
    process = _process(
        max(escrowed, 1e-9),
        clock.rate(problem.rate),
        clock.rate(problem.carry_yield),
        clock.volatility(problem.sigma),
    )
    option.setPricingEngine(ql.BinomialVanillaEngine(process, "lr", problem.numerics.tree_steps))
    return option.NPV()


def early_exercise_is_never_optimal(problem: Problem) -> bool:
    """A call on a non-dividend payer with no borrow cost and a non-negative rate."""
    return (
        problem.right == 1
        and not problem.dividends
        and problem.carry_yield == 0
        and problem.rate >= 0
    )
