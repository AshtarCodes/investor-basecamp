# PROTOTYPE (throwaway): exact minutes-to-settlement in QuantLib via a "virtual clock".
# Map true time [0, T] onto N whole QuantLib days; rescale sigma, r and dividend times so
# sigma^2*T, r*T and r/sigma^2 are unchanged.
import math
import time

import numpy as np
import QuantLib as ql
from scipy.stats import norm

TODAY = ql.Date(26, 10, 2026)
ql.Settings.instance().evaluationDate = TODAY
DC = ql.Actual365Fixed()
CAL = ql.NullCalendar()
MIN_PER_YEAR = 525_600


def bsm(cp, S, K, T, r, v):
    d1 = (math.log(S / K) + (r + v * v / 2) * T) / (v * math.sqrt(T))
    d2 = d1 - v * math.sqrt(T)
    if cp == 1:
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def ql_price(cp, S, K, r, v, T, divs=(), amer=True, N=3650, fd=(100, 200)):
    """T in true years; divs = [(true_time_years, cash)]."""
    Tq = N / 365.0
    f = T / Tq                      # true years per QL year
    r2, v2 = r * f, v * math.sqrt(f)
    exp = TODAY + N
    rts = ql.YieldTermStructureHandle(ql.FlatForward(TODAY, r2, DC))
    qts = ql.YieldTermStructureHandle(ql.FlatForward(TODAY, 0.0, DC))
    vts = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(TODAY, CAL, v2, DC))
    proc = ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(S)), qts, rts, vts)
    ex = ql.AmericanExercise(TODAY, exp) if amer else ql.EuropeanExercise(exp)
    o = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Call if cp == 1 else ql.Option.Put, K), ex)
    if not amer:
        o.setPricingEngine(ql.AnalyticEuropeanEngine(proc)); return o.NPV()
    sched = [ql.FixedDividend(a, TODAY + max(1, round(td / T * N))) for td, a in divs]
    o.setPricingEngine(ql.FdBlackScholesVanillaEngine(proc, sched, fd[0], fd[1], 0))
    return o.NPV()


def crr_american(cp, S, K, r, v, T, n=4000):
    dt = T / n; u = math.exp(v * math.sqrt(dt)); d = 1 / u
    p = (math.exp(r * dt) - d) / (u - d); disc = math.exp(-r * dt)
    j = np.arange(n + 1)
    ST = S * u ** (n - j) * d ** j
    V = np.maximum(cp * (ST - K), 0.0)
    for i in range(n - 1, -1, -1):
        j = np.arange(i + 1)
        Sx = S * u ** (i - j) * d ** j
        V = np.maximum(disc * (p * V[:-1] + (1 - p) * V[1:]), np.maximum(cp * (Sx - K), 0.0))
    return V[0]


print("=== European (analytic engine on virtual clock) vs closed form at exact T")
cases = [
    ("3.5h to 4pm, SPY-like 0DTE", 3.5 * 60),
    ("1 day", 1440), ("1.5 days", 2160), ("91.25 days (T=0.25y)", 0.25 * MIN_PER_YEAR),
    ("2 years", 2 * MIN_PER_YEAR)]
worst = 0.0
for name, mins in cases:
    T = mins / MIN_PER_YEAR
    for cp in (1, -1):
        a = ql_price(cp, 100, 100, 0.042, 0.35, T, amer=False)
        b = bsm(cp, 100, 100, T, 0.042, 0.35)
        worst = max(worst, abs(a - b))
    print(f"{name:30s} T={T:.6f}  QL {a:.6f}  closed {b:.6f}  err {abs(a-b):.2e}")
print("worst abs error (price):", f"{worst:.2e}")

print("\n=== American, no dividends: FD on virtual clock vs 4000-step CRR at exact T")
for name, mins in (("3.5h", 210), ("1.5 days", 2160), ("30 days", 30 * 1440)):
    T = mins / MIN_PER_YEAR
    for cp, S, K, v in ((-1, 100, 100, 0.35), (-1, 100, 105, 0.35), (1, 25.37, 22, 1.03), (-1, 25.37, 30, 1.03)):
        a = ql_price(cp, S, K, 0.042, v, T)
        a2 = ql_price(cp, S, K, 0.042, v, T, fd=(400, 800))
        b = crr_american(cp, S, K, 0.042, v, T)
        print(f"{name:9s} {'C' if cp==1 else 'P'} S={S:<6} K={K:<4} FD100x200 {a:.5f}  FD400x800 {a2:.5f}  CRR {b:.5f}  err(fine) {abs(a2-b):.1e}")

print("\n=== invariance to the virtual-clock length N (American put with two cash dividends, T=0.4y)")
T = 0.4
divs = [(0.10, 0.80), (0.35, 0.80)]
for N in (730, 3650, 36500):
    print(f"N={N:6d}: {ql_price(-1, 100, 105, 0.042, 0.30, T, divs=divs, N=N, fd=(200,400)):.5f}")
# whole-day reference without any rescale: T = 146 days exactly, N = 146
Tw = 146 / 365
print(f"unscaled 146-day reference (N=146, f=1): {ql_price(-1, 100, 105, 0.042, 0.30, Tw, divs=[(0.10*Tw/T, 0.8),(0.35*Tw/T,0.8)], N=146, fd=(200,400)):.5f}  vs virtual-clock at T=146/365: {ql_price(-1, 100, 105, 0.042, 0.30, Tw, divs=[(0.10*Tw/T, 0.8),(0.35*Tw/T,0.8)], N=3650, fd=(200,400)):.5f}")

print("\n=== 0-DTE with dividend ex-date inside the last day (T=1 day, ex at 0.4 day)")
T = 1 / 365
for N in (730, 3650, 36500):
    print(f"N={N:6d}: {ql_price(-1, 100, 100, 0.042, 0.30, T, divs=[(0.4*T, 1.5)], N=N, fd=(200,400)):.5f}")

print("\n=== cost: price time at N=3650 vs N=36500 (FD 100x200)")
for N in (146, 3650, 36500):
    t = time.perf_counter()
    for i in range(200):
        ql_price(-1, 100 + i * 0.01, 105, 0.042, 0.30, 0.4, divs=divs, N=N)
    print(f"N={N:6d}: {(time.perf_counter()-t)/200*1000:.2f} ms/price (includes object build)")
