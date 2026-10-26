"""How IREN's volume behaves as price moves, and around its reversals.

Usage: python3 scenarios/iren/analysis/volume_vs_price.py [csv] [reversal]
Reads date,open,high,low,close,volume rows (default: the committed one-year file) and a
leg-reversal threshold (default 0.25, as in legs_vs_vix.py). Standard library only.

Relative volume (RVOL) is a day's volume divided by the mean of the 20 days before it.
"""

import csv
import statistics as st
import sys
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parents[1] / "data" / "daily-ohlcv-2025-10-23_2026-10-23.csv"
WINDOW = 20


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
    close = [float(r["close"]) for r in rows]
    volume = [float(r["volume"]) for r in rows]
    n = len(rows)
    ret = [None] + [close[i] / close[i - 1] - 1 for i in range(1, n)]
    rvol = [None] * WINDOW + [volume[i] / st.mean(volume[i - WINDOW : i]) for i in range(WINDOW, n)]

    print(f"{n} days, {days[0]} to {days[-1]}; mean volume {st.mean(volume) / 1e6:.1f}M shares\n")

    # 1. Volume against the size and sign of the daily move
    both = [i for i in range(WINDOW, n)]
    abs_ret = [abs(ret[i]) for i in both]
    print("1. Daily volume vs the move")
    print(f"   corr(|return|, RVOL)          {correlation(abs_ret, [rvol[i] for i in both]):+.2f}")
    print(f"   corr(return, RVOL)            {correlation([ret[i] for i in both], [rvol[i] for i in both]):+.2f}")
    up = [rvol[i] for i in both if ret[i] > 0]
    down = [rvol[i] for i in both if ret[i] < 0]
    print(f"   mean RVOL, up days            {st.mean(up):.2f}x  ({len(up)} days)")
    print(f"   mean RVOL, down days          {st.mean(down):.2f}x  ({len(down)} days)")
    buckets = [(-1, -0.10), (-0.10, -0.05), (-0.05, 0), (0, 0.05), (0.05, 0.10), (0.10, 1)]
    print("   RVOL by the day's return:")
    for lo, hi in buckets:
        sel = [rvol[i] for i in both if lo <= ret[i] < hi]
        if sel:
            print(f"     {lo:+.0%} to {hi:+.0%}".replace("-100%", "below").replace("+100%", "above")
                  + f"   {st.mean(sel):.2f}x  ({len(sel)} days)")

    # 2. Volume in rally legs and tank legs
    pivots = zigzag(close, threshold)
    print(f"\n2. Legs (reversal {threshold:.0%}): daily volume and RVOL inside each")
    print("   leg    start       end         move     days  avg vol   avg RVOL  up-day vol / down-day vol")
    legs = []
    for a, b in zip(pivots, pivots[1:], strict=False):
        if b <= a:
            continue
        move = close[b] / close[a] - 1
        idx = range(a + 1, b + 1)
        avg = st.mean(volume[i] for i in idx)
        rv = [rvol[i] for i in idx if rvol[i] is not None]
        u = [volume[i] for i in idx if ret[i] > 0]
        d = [volume[i] for i in idx if ret[i] < 0]
        ratio = st.mean(u) / st.mean(d) if u and d else float("nan")
        kind = "rally" if move > 0 else "tank"
        legs.append((kind, move, avg, rv, ratio))
        rv_text = f"{st.mean(rv):.2f}x" if rv else "  n/a"
        print(f"   {kind:5}  {days[a]}  {days[b]}  {move:+7.0%}  {b - a:4}  {avg / 1e6:5.1f}M   {rv_text:>6}   {ratio:.2f}")
    for kind in ("rally", "tank"):
        sel = [leg for leg in legs if leg[0] == kind]
        if sel:
            print(f"   {kind}: mean daily volume {st.mean(leg[2] for leg in sel) / 1e6:.1f}M over {len(sel)} legs")

    # 3. Volume around the pivots (the reversals)
    tops = [p for p in pivots[1:-1] if close[p] > close[p - 1] and close[p] >= max(close[max(0, p - 5) : p + 5])]
    bottoms = [p for p in pivots[1:-1] if p not in tops]
    print("\n3. RVOL around reversal pivots (day 0 = the extreme close; -3..+3 trading days)")
    offsets = range(-3, 4)
    for label, group in (("tops", tops), ("bottoms", bottoms)):
        print(f"   {label} ({len(group)}):  " + "  ".join(f"{o:+d}" for o in offsets))
        for p in group:
            cells = []
            for o in offsets:
                j = p + o
                cells.append(f"{rvol[j]:.1f}" if 0 <= j < n and rvol[j] is not None else " . ")
            print(f"     {days[p]} {close[p]:7.2f}  " + "  ".join(f"{c:>2}" for c in cells))
        means = []
        for o in offsets:
            vals = [rvol[p + o] for p in group if 0 <= p + o < n and rvol[p + o] is not None]
            means.append(f"{st.mean(vals):.2f}" if vals else " . ")
        print(f"     mean            " + "  ".join(f"{m:>2}" for m in means))

    # 4. Biggest volume days, and what price did next
    print("\n4. Ten highest-RVOL days and the next 5 days' return")
    ranked = sorted(both, key=lambda i: rvol[i], reverse=True)[:10]
    for i in sorted(ranked):
        fwd = close[i + 5] / close[i] - 1 if i + 5 < n else None
        fwd_text = f"{fwd:+.0%}" if fwd is not None else "  n/a"
        print(f"   {days[i]}  RVOL {rvol[i]:.1f}x  day {ret[i]:+.1%}  next 5d {fwd_text}")


if __name__ == "__main__":
    main()
