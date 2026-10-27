"""How often did IREN give back a rally, in the two years of daily closes we hold?

Usage: python3 scenarios/iren/analysis/overshoot_check.py
Reads both daily-closes files in data/ (2024-10-23 to 2026-10-23). Standard library only.

Legs are found with a 25% reversal threshold (the same as legs_vs_vix.py): a leg runs from one extreme to the next, and
turns when the price moves 25% against it. For every rally leg this reports the fall that followed, and for every fall
whether a rally of at least 50% and 100% came first. It also counts, for any day, how often a +100% advance over 60
trading days was followed by a drop of at least 40%, 50% and 60% from the high within the next 20, 40 and 60 days.
Two years and a handful of legs: a count, not a rate.
"""

import csv
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
FILES = ["daily-closes-2024-10-23_2025-10-22.csv", "daily-closes-2025-10-23_2026-10-23.csv"]
THRESHOLD = 0.25


def load():
    rows = []
    for f in FILES:
        with open(DATA / f) as fh:
            rows += [(r["date"], float(r["iren_close"])) for r in csv.DictReader(fh)]
    return rows


def legs(rows):
    out = []
    lo = hi = 0  # indexes of the running extremes
    direction = 0
    start = 0
    for i, (_, p) in enumerate(rows):
        if p > rows[hi][1]:
            hi = i
        if p < rows[lo][1]:
            lo = i
        if direction >= 0 and p <= rows[hi][1] * (1 - THRESHOLD) and hi >= start:
            out.append((start, hi, "rally")) if direction == 1 else None
            if direction == 0 and hi > start:
                out.append((start, hi, "rally"))
            start, direction, lo = hi, -1, i
            hi = i
        elif direction <= 0 and p >= rows[lo][1] * (1 + THRESHOLD) and lo >= start:
            if direction == -1:
                out.append((start, lo, "fall"))
            elif lo > start:
                out.append((start, lo, "fall"))
            start, direction, hi = lo, 1, i
            lo = i
    return out


def main():
    rows = load()
    print(f"{len(rows)} closes, {rows[0][0]} to {rows[-1][0]}; last {rows[-1][1]}")
    ls = legs(rows)
    print("\nLegs (25% reversal):")
    for a, b, kind in ls:
        ch = rows[b][1] / rows[a][1] - 1
        print(f"  {kind:5} {rows[a][0]} {rows[a][1]:7.2f} -> {rows[b][0]} {rows[b][1]:7.2f}  {ch:+7.0%}  {b - a:3d} trading days")
    print("\nRally legs followed by a fall:")
    for (a, b, k), nxt in zip(ls, ls[1:]):
        if k == "rally" and nxt[2] == "fall":
            r = rows[b][1] / rows[a][1] - 1
            f = rows[nxt[1]][1] / rows[nxt[0]][1] - 1
            print(f"  rally {r:+6.0%} over {b - a:3d} days, then fall {f:+5.0%} over {nxt[1] - nxt[0]:3d} days, ending at {rows[nxt[1]][1] / rows[a][1] - 1:+5.0%} of the rally's start")
    print("\nAny day: a +100% advance over the prior 60 trading days, then the worst drop from the running high:")
    hits = [i for i in range(60, len(rows)) if rows[i][1] / rows[i - 60][1] >= 2.0]
    print(f"  {len(hits)} days qualify")
    for horizon in (20, 40, 60):
        tallies = []
        for i in hits:
            window = rows[i : i + horizon + 1]
            if len(window) < horizon + 1:
                continue
            hi, worst = window[0][1], 0.0
            for _, p in window:
                hi = max(hi, p)
                worst = min(worst, p / hi - 1)
            tallies.append(worst)
        if tallies:
            row = "  ".join(f">={x:.0%}: {sum(t <= -x for t in tallies)}/{len(tallies)}" for x in (0.4, 0.5, 0.6))
            print(f"  next {horizon:2d} days, drop from the high of {row}")


if __name__ == "__main__":
    main()
