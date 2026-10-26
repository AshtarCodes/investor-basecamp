"""IREN's typical daily and weekly moves, then the volume-and-move study on both timeframes.

Usage: python3 scenarios/iren/analysis/timeframes.py [csv]
Reads date,open,high,low,close,volume rows (default: the committed one-year file). Standard library only.

A "big" move is one beyond one standard deviation of that timeframe's returns, so it means the same
thing daily and weekly. "Low" and "high" volume are the bottom and top third of that timeframe's
relative volume (RVOL: the bar's average daily volume over the prior 20 days, or the prior 8 weeks).
Samples are small and forward windows overlap, so these are leans, not tests.
"""

import csv
import statistics as st
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parents[1] / "data" / "daily-ohlcv-2025-10-23_2026-10-23.csv"


@dataclass(frozen=True)
class Series:
    name: str
    unit: str  # what one bar is called
    labels: list[str]
    close: list[float]
    volume: list[float]  # average daily volume inside the bar
    window: int  # bars in the RVOL baseline and in the high/low lookback
    horizons: tuple[int, int, int]

    @property
    def ret(self) -> list[float | None]:
        return [None] + [self.close[i] / self.close[i - 1] - 1 for i in range(1, len(self.close))]

    @property
    def rvol(self) -> list[float | None]:
        w = self.window
        return [None] * w + [
            self.volume[i] / st.mean(self.volume[i - w : i]) for i in range(w, len(self.close))
        ]


def load(path: Path) -> tuple[Series, Series]:
    rows = list(csv.DictReader(path.open()))
    daily = Series(
        "daily",
        "day",
        [r["date"] for r in rows],
        [float(r["close"]) for r in rows],
        [float(r["volume"]) for r in rows],
        20,
        (1, 5, 10),
    )
    weeks: dict[tuple[int, int], list[dict[str, str]]] = {}
    for r in rows:
        iso = date.fromisoformat(r["date"]).isocalendar()
        weeks.setdefault((iso.year, iso.week), []).append(r)
    ordered = [weeks[k] for k in sorted(weeks)]
    weekly = Series(
        "weekly",
        "week",
        [w[-1]["date"] for w in ordered],
        [float(w[-1]["close"]) for w in ordered],
        [st.mean(float(r["volume"]) for r in w) for w in ordered],
        8,
        (1, 2, 4),
    )
    return daily, weekly


def percentile(sorted_values: list[float], q: float) -> float:
    return sorted_values[min(len(sorted_values) - 1, int(q * len(sorted_values)))]


def forward(series: Series, i: int, k: int) -> float | None:
    return series.close[i + k] / series.close[i] - 1 if i + k < len(series.close) else None


def summarize(values: list[float | None]) -> str:
    kept = [v for v in values if v is not None]
    if not kept:
        return "     n/a"
    up = sum(v > 0 for v in kept) / len(kept)
    return f"{st.mean(kept):+6.1%} ({up:.0%} up)"


def typical_moves(series: Series) -> float:
    kept = [r for r in series.ret if r is not None]
    magnitudes = sorted(abs(r) for r in kept)
    sigma = st.stdev(kept)
    print(f"{series.name.upper()}: {len(series.close)} bars")
    print(f"   mean |move| {st.mean(magnitudes):.1%}   median |move| {st.median(magnitudes):.1%}   "
          f"std {sigma:.1%}   90th pct |move| {percentile(magnitudes, 0.9):.1%}")
    print(f"   biggest up {max(kept):+.1%}   biggest down {min(kept):+.1%}   "
          f"up {sum(r > 0 for r in kept)} / down {sum(r < 0 for r in kept)}")
    return sigma


def thirds(series: Series) -> tuple[float, float]:
    kept = sorted(v for v in series.rvol if v is not None)
    return percentile(kept, 1 / 3), percentile(kept, 2 / 3)


def study(series: Series, sigma: float) -> None:
    n, w = len(series.close), series.window
    ret, rvol = series.ret, series.rvol
    lo, hi = thirds(series)
    bars = range(w, n)
    h = series.horizons
    head = "  ".join(f"next {k} {series.unit}{'s' if k > 1 else ''}".ljust(17) for k in h)
    print(f"\n{series.name.upper()}: move beyond {sigma:.1%} (1 std), volume low < {lo:.2f}x, high > {hi:.2f}x")
    print(f"   {'':26} {'n':>3}  {head}")
    cases = [
        ("down, low volume", lambda i: ret[i] < -sigma and rvol[i] < lo),
        ("down, high volume", lambda i: ret[i] < -sigma and rvol[i] > hi),
        ("up, low volume", lambda i: ret[i] > sigma and rvol[i] < lo),
        ("up, high volume", lambda i: ret[i] > sigma and rvol[i] > hi),
        (f"every {series.unit}", lambda i: True),
    ]
    for name, cond in cases:
        sel = [i for i in bars if cond(i)]
        cells = "  ".join(summarize([forward(series, i, k) for i in sel]).ljust(17) for k in h)
        print(f"   {name:26} {len(sel):3}  {cells}")

    print(f"\n   Close at a {w}-{series.unit} high or low, split by volume (next {h[2]} {series.unit}s)")
    for name, at_extreme in (
        (f"{w}-{series.unit} high", lambda i: series.close[i] >= max(series.close[i - w + 1 : i + 1])),
        (f"{w}-{series.unit} low", lambda i: series.close[i] <= min(series.close[i - w + 1 : i + 1])),
    ):
        sel = [i for i in bars if at_extreme(i)]
        low = [i for i in sel if rvol[i] < lo]
        high = [i for i in sel if rvol[i] > hi]
        print(f"   {name:14} n={len(sel):2}   low volume n={len(low):2} {summarize([forward(series, i, h[2]) for i in low])}"
              f"   high volume n={len(high):2} {summarize([forward(series, i, h[2]) for i in high])}")


def where_it_is_now(series: Series, sigma: float) -> None:
    n, w = len(series.close), series.window
    i = n - 1
    lo, hi = thirds(series)
    ret, rvol = series.ret[i], series.rvol[i]
    band = "low" if rvol < lo else "high" if rvol > hi else "middle"
    window_closes = series.close[i - w + 1 :]
    place = "at its low" if series.close[i] <= min(window_closes) else (
        "at its high" if series.close[i] >= max(window_closes) else "inside its range"
    )
    low_from_high = series.close[i] / max(window_closes) - 1
    print(f"   {series.name:6} last bar {series.labels[i]}: close {series.close[i]:.2f}, move {ret:+.1%} "
          f"({ret / sigma:+.1f} std), RVOL {rvol:.2f}x ({band} third), {w}-{series.unit} range: {place} "
          f"({low_from_high:+.0%} from its high)")
    for back in (1, 2, 3):
        j = i - back
        print(f"      {series.labels[j]}: move {series.ret[j]:+.1%} ({series.ret[j] / sigma:+.1f} std), "
              f"RVOL {series.rvol[j]:.2f}x")


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    daily, weekly = load(path)
    print(f"{daily.labels[0]} to {daily.labels[-1]}\n")
    sigmas = {s.name: typical_moves(s) for s in (daily, weekly)}
    print(f"\n   A weekly std of {sigmas['weekly']:.1%} against a daily {sigmas['daily']:.1%} is "
          f"{sigmas['weekly'] / sigmas['daily']:.1f}x (a random walk gives 2.2x for 5 days).")
    for s in (daily, weekly):
        study(s, sigmas[s.name])
    print("\nWHERE IREN IS NOW")
    for s in (daily, weekly):
        where_it_is_now(s, sigmas[s.name])


if __name__ == "__main__":
    main()
