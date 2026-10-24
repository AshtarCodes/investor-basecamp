"""Mark-implied IV: the σ at which the model reproduces a Mark."""

import math
from dataclasses import replace

from scipy.optimize import brentq

from pricing_engine.model import value
from pricing_engine.models import ImpliedVolatility
from pricing_engine.problem import Problem

SIGMA_MIN = 0.01
SIGMA_MAX = 5.0
SIGMA_TOLERANCE = 1e-12


def intrinsic_value(problem: Problem) -> float:
    """The floor the model respects: exercise now (American) or the discounted forward payoff."""
    if problem.american or problem.life <= 0:
        return problem.intrinsic
    discount = math.exp(-problem.rate * problem.life)
    return discount * max(problem.right * (problem.european_forward() - problem.strike), 0.0)


def solve(problem: Problem, mark: float) -> ImpliedVolatility:
    """Brent on the price function over σ in `[0.01, 5.0]` (decimals).

    With no IV the result carries the residual, the Mark minus the model value at the lowest
    bound, which ADR 0001 carries unchanged under Shocks.
    """

    def gap(sigma: float) -> float:
        return value(replace(problem, sigma=sigma)) - mark

    at_lowest = gap(SIGMA_MIN)
    residual = -at_lowest
    if mark <= intrinsic_value(problem):
        return ImpliedVolatility(value=None, reason="at_or_below_intrinsic", residual=residual)
    if at_lowest > 0 or gap(SIGMA_MAX) < 0:
        return ImpliedVolatility(value=None, reason="no_bracket", residual=residual)
    sigma = brentq(gap, SIGMA_MIN, SIGMA_MAX, xtol=SIGMA_TOLERANCE)
    return ImpliedVolatility(value=sigma)
