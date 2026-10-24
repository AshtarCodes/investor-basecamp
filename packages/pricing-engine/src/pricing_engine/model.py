"""The model value of a Problem: which model prices it, and what it is worth."""

from pricing_engine.american import cash_drop, early_exercise_is_never_optimal
from pricing_engine.european import black_76
from pricing_engine.models import PricingModel
from pricing_engine.problem import Problem


def model_of(problem: Problem) -> PricingModel:
    if problem.life <= 0:
        return "intrinsic"
    if problem.american:
        if early_exercise_is_never_optimal(problem):
            return "american_closed_form"
        return "american_fd_cash_drop"
    return "black_76" if problem.forward is not None else "black_scholes_merton"


def value(problem: Problem) -> float:
    """The model value per share."""
    if problem.life <= 0:
        return problem.intrinsic
    if problem.american and not early_exercise_is_never_optimal(problem):
        return cash_drop(problem)
    return black_76(
        right=problem.right,
        forward=problem.european_forward(),
        strike=problem.strike,
        life=problem.life,
        rate=problem.rate,
        sigma=problem.sigma,
    )
