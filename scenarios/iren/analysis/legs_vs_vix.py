"""Average VIX in IREN's rally and tank legs, daily IREN-VIX relation, and realized volatility.

Usage: python3 scenarios/iren/analysis/legs_vs_vix.py [csv] [reversal]
Reads date,iren_close,vix_close rows (default: the committed one-year file) and a leg-reversal
threshold (default 0.25: a leg ends when IREN reverses 25% from its extreme). Standard library only.
"""

import csv
import math
import statistics as st
import sys
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parents[1] / "data" / "daily-closes-2025-10-23_2026-10-23.csv"


def zigzag(prices: list[float], threshold: float) -> list[int]:
    """Pivot indices: a leg ends when price reverses `threshold` from its running extreme."""
    pivots, direction, extreme = [0], 0, 0
    for i in range(1, len(prices)):
        if direction == 0:
            if prices[i] >= prices[extreme] * (1 + threshold):
                direction, extreme = 1, i
            elif prices[i] <= prices[extreme] * (1 - threshold):
                direction, extreme = -1, i
        elif direction == 1:
            if prices[i] > prices[extreme]:
                extreme = i
            elif prices[i] <= prices[extreme] * (1 - threshold):
                pivots.append(extreme)
                direction, extreme = -1, i
        elif prices[i] < prices[extreme]:
            extreme = i
        elif prices[i] >= prices[extreme] * (1 + threshold):
            pivots.append(extreme)
            direction, extreme = 1, i
    pivots.append(len(prices) - 1)
    return pivots


def correlation(x: list[float], y: list[float]) -> float:
    mx, my = st.mean(x), st.mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    return num / (sum((a - mx) ** 2 for a in x) ** 0.5 * sum((b - my) ** 2 for b in y) ** 0.5)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
    rows = list(csv.DictReader(path.open()))
    days = [r["date"] for r in rows]
    price = [float(r["iren_close"]) for r in rows]
    vix = [float(r["vix_close"]) for r in rows]

    print(f"{len(days)} days, {days[0]} to {days[-1]}; leg reversal {threshold:.0%}\n")
    rally, tank = [], []
    pivots = zigzag(price, threshold)
    for a, b in zip(pivots, pivots[1:], strict=False):
        if b <= a:
            continue
        move = price[b] / price[a] - 1
        seg = vix[a : b + 1]
        (rally if move > 0 else tank).append((b - a, st.mean(seg)))
        kind = "RALLY" if move > 0 else "TANK "
        print(
            f"{days[a]}..{days[b]} {kind} {price[a]:6.1f}>{price[b]:6.1f} {move:+7.1%} "
            f"{b - a:3d}d  VIX avg {st.mean(seg):5.2f}  {vix[a]:5.2f}>{vix[b]:5.2f}"
        )
    for name, legs in (("RALLY", rally), ("TANK", tank)):
        weighted = sum(d * v for d, v in legs) / sum(d for d, _ in legs)
        print(f"day-weighted average VIX in {name} legs: {weighted:.2f}")

    returns = [price[i] / price[i - 1] - 1 for i in range(1, len(price))]
    vix_change = [vix[i] - vix[i - 1] for i in range(1, len(vix))]
    print(f"\ncorrelation, IREN daily return vs VIX daily change: {correlation(returns, vix_change):.2f}")
    logs = [math.log(price[i] / price[i - 1]) for i in range(1, len(price))]
    for label, window in (("full period", len(logs)), ("last 60d", 60), ("last 30d", 30), ("last 10d", 10)):
        print(f"realized vol, {label}: {st.stdev(logs[-window:]) * math.sqrt(252):.0%}")


if __name__ == "__main__":
    main()
