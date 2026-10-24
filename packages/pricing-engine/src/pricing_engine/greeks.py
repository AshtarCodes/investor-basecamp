"""Greeks by bump-and-reprice, so every Greek shares the price function's code path."""

import math
from dataclasses import replace

from pricing_engine.model import value
from pricing_engine.models import Greeks
from pricing_engine.problem import Problem

SPOT_BUMP_MAX = 0.01  # relative
SPOT_BUMP_MIN = 0.0003
MOVE_FRACTION = 0.05  # of the option's one-sigma move over its remaining life
VOL_BUMP = 0.005  # half a vol point each side
RATE_BUMP = 0.0005  # half a rate point each side
DAY = 1 / 365
POINT = 0.01  # one vol point or one rate point, as a decimal


def central(up: float, down: float, bump: float) -> float:
    """The central difference per unit of the bumped input."""
    return (up - down) / (2 * bump)


def spot_bump(problem: Problem) -> float:
    """1% of spot, narrowed for options whose whole distribution is narrower than that."""
    move = MOVE_FRACTION * problem.sigma * math.sqrt(max(problem.life, 0.0))
    return min(max(move, SPOT_BUMP_MIN), SPOT_BUMP_MAX)


def greeks(problem: Problem) -> Greeks:
    """Delta and gamma per share of spot; vega per vol point; theta per day; rho per rate point.

    Theta is the central change over one calendar day. It narrows to the remaining life when
    that is under a day, and it includes a dividend that falls inside the window.
    """
    base = value(problem)
    step = problem.spot * spot_bump(problem)
    up = value(problem.with_spot(problem.spot + step))
    down = value(problem.with_spot(problem.spot - step))
    delta = (up - down) / (2 * step)
    gamma = (up - 2 * base + down) / step**2
    if problem.life <= 0:
        return Greeks(delta=delta, gamma=gamma, vega=0.0, theta=0.0, rho=0.0)

    vol = min(VOL_BUMP, problem.sigma / 2)
    vega = POINT * central(
        value(replace(problem, sigma=problem.sigma + vol)),
        value(replace(problem, sigma=problem.sigma - vol)),
        vol,
    )
    rho = POINT * central(
        value(replace(problem, rate=problem.rate + RATE_BUMP)),
        value(replace(problem, rate=problem.rate - RATE_BUMP)),
        RATE_BUMP,
    )
    half = min(DAY / 2, problem.life / 2)
    theta = DAY * central(value(problem.advance(half)), value(problem.advance(-half)), half)

    return Greeks(delta=delta, gamma=gamma, vega=vega, theta=theta, rho=rho)
