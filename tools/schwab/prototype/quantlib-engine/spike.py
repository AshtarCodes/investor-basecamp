# PROTOTYPE (throwaway): can QuantLib be the pricing engine for ADR 0001?
import math
import random
import time

import QuantLib as ql
from scipy.optimize import brentq

TODAY = ql.Date(26, 10, 2026)
ql.Settings.instance().evaluationDate = TODAY
DC = ql.Actual365Fixed()
CAL = ql.NullCalendar()


def hdr(s):
    print(f"\n=== {s}")


class Pos:
    """One option position with live quotes so shocks don't rebuild objects."""

    def __init__(self, right, k, expiry, spot, vol, r, divs=(), engine="fd", fd=(200, 400)):
        self.divs = divs
        self.k = k
        self.right = right
        self.expiry = expiry
        self.spot_q = ql.SimpleQuote(spot)
        self.vol_q = ql.SimpleQuote(vol)
        self.r = r
        rts = ql.YieldTermStructureHandle(ql.FlatForward(TODAY, r, DC))
        qts = ql.YieldTermStructureHandle(ql.FlatForward(TODAY, 0.0, DC))
        vts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(TODAY, CAL, ql.QuoteHandle(self.vol_q), DC))
        self.proc = ql.BlackScholesMertonProcess(ql.QuoteHandle(self.spot_q), qts, rts, vts)
        payoff = ql.PlainVanillaPayoff(right, k)
        self.opt = ql.VanillaOption(payoff, ql.AmericanExercise(TODAY, expiry))
        sched = [ql.FixedDividend(a, d) for d, a in divs]
        if engine == "fd":
            self.opt.setPricingEngine(
                ql.FdBlackScholesVanillaEngine(self.proc, sched, fd[0], fd[1], 0))
        else:
            raise ValueError

    def npv(self):
        return self.opt.NPV()

    def price(self, spot=None, vol=None):
        if spot is not None:
            self.spot_q.setValue(spot)
        if vol is not None:
            self.vol_q.setValue(vol)
        return self.opt.NPV()


# ---------- (1) import cost ----------
hdr("1. import")
print("QuantLib", ql.__version__)

# ---------- (4a) Haug BSM European oracle ----------
hdr("4a. Haug BSM oracle: S=60 K=65 T=0.25 r=.08 sigma=.30 (b=r) -> call 2.1334")
exp = TODAY + 91  # 91/365 ~ 0.2493; use exact T via rates scaling below instead
# QuantLib time is whole days; pick T=0.25 -> 91.25 days. Use 91 days and compare to BSM at 91/365.
T = 91 / 365
def bsm(cp, S, K, T, r, q, v):
    from scipy.stats import norm
    d1 = (math.log(S / K) + (r - q + v * v / 2) * T) / (v * math.sqrt(T))
    d2 = d1 - v * math.sqrt(T)
    if cp == 1:
        return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)
print("closed form T=0.25:", round(bsm(1, 60, 65, 0.25, 0.08, 0, 0.3), 4))
rts = ql.YieldTermStructureHandle(ql.FlatForward(TODAY, 0.08, DC))
qts = ql.YieldTermStructureHandle(ql.FlatForward(TODAY, 0.0, DC))
vts = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(TODAY, CAL, 0.30, DC))
p = ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(60)), qts, rts, vts)
eu = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Call, 65), ql.EuropeanExercise(exp))
eu.setPricingEngine(ql.AnalyticEuropeanEngine(p))
print(f"QL analytic (91d={T:.5f}y): {eu.NPV():.4f}   closed form same T: {bsm(1,60,65,T,0.08,0,0.3):.4f}")

# ---------- (2) cases ----------
hdr("2. American, FD cash-drop vs LR vs BSM")
# A: IREN-like call, no dividends, American == European
expA = ql.Date(15, 1, 2027)
TA = DC.yearFraction(TODAY, expA)
A = Pos(ql.Option.Call, 55, expA, 25.37, 1.03, 0.0420)
bsmA = bsm(1, 25.37, 55, TA, 0.042, 0, 1.03)
print(f"A IREN 55C 2027-01-15 T={TA:.4f}: FD={A.npv():.4f}  BSM={bsmA:.4f}  diff={A.npv()-bsmA:+.4f}")
fd_hi = Pos(ql.Option.Call, 55, expA, 25.37, 1.03, 0.0420, fd=(800, 1600))
print(f"  FD fine grid (800x1600): {fd_hi.npv():.4f}")

# B: dividend payer, ITM American put, two $0.80 cash dividends
S0, K, v, r = 100.0, 105.0, 0.30, 0.042
expB = ql.Date(16, 4, 2027)
divsB = [(ql.Date(20, 11, 2026), 0.80), (ql.Date(19, 2, 2027), 0.80)]
B = Pos(ql.Option.Put, K, expB, S0, v, r, divs=divsB)
BhiFD = Pos(ql.Option.Put, K, expB, S0, v, r, divs=divsB, fd=(800, 1600))
pv = sum(a * math.exp(-r * DC.yearFraction(TODAY, d)) for d, a in divsB)
adj = S0 - pv
# LR binomial on spot minus PV(divs), no dividends
rts = ql.YieldTermStructureHandle(ql.FlatForward(TODAY, r, DC))
qts = ql.YieldTermStructureHandle(ql.FlatForward(TODAY, 0.0, DC))
vts = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(TODAY, CAL, v, DC))
def lr_price(n, spot=adj, amer=True):
    pr = ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(spot)), qts, rts, vts)
    ex = ql.AmericanExercise(TODAY, expB) if amer else ql.EuropeanExercise(expB)
    o = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Put, K), ex)
    o.setPricingEngine(ql.BinomialVanillaEngine(pr, "lr", n))
    return o.NPV()
print(f"B put K={K} (PV divs={pv:.4f}, adj spot={adj:.4f}):")
print(f"  FD cash-drop 200x400 = {B.npv():.4f}   FD cash-drop 800x1600 = {BhiFD.npv():.4f}")
print(f"  LR n=101 = {lr_price(101):.4f}  LR n=201 = {lr_price(201):.4f}  (escrowed spot)")
print(f"  European BSM on escrowed spot = {bsm(-1, adj, K, DC.yearFraction(TODAY, expB), r, 0, v):.4f}")
no_div = Pos(ql.Option.Put, K, expB, S0, v, r)
print(f"  FD with NO dividends = {no_div.npv():.4f}  (dividends should raise the put)")

# ---------- (3) mark-implied IV and greeks ----------
hdr("3. mark-implied IV + greeks")
mark_A = round(A.price(vol=1.03), 2)
A.vol_q.setValue(1.03)
t = time.perf_counter()
ivA = brentq(lambda x: A.price(vol=x) - mark_A, 0.01, 5.0, xtol=1e-8)
print(f"A: mark {mark_A} -> IV {ivA:.5f}  ({(time.perf_counter()-t)*1000:.0f} ms)")
mark_B = round(B.price(vol=0.34), 2)
t = time.perf_counter()
ivB = brentq(lambda x: B.price(vol=x) - mark_B, 0.01, 5.0, xtol=1e-8)
print(f"B: mark {mark_B} -> IV {ivB:.5f}  ({(time.perf_counter()-t)*1000:.0f} ms)")
B.vol_q.setValue(ivB)

def bump_greeks(P, ds_rel=0.01, dv=0.01, dr=0.0001):
    s0, v0 = P.spot_q.value(), P.vol_q.value()
    base = P.price(spot=s0, vol=v0)
    ds = s0 * ds_rel
    up, dn = P.price(spot=s0 + ds), P.price(spot=s0 - ds)
    P.price(spot=s0)
    delta = (up - dn) / (2 * ds)
    gamma = (up - 2 * base + dn) / ds**2
    vega = (P.price(vol=v0 + dv) - P.price(vol=v0 - dv)) / (2 * dv) / 100  # per vol point
    P.price(vol=v0)
    return base, delta, gamma, vega

for name, P in (("A", A), ("B", B)):
    P.price(spot=P.spot_q.value())
    base, d, g, ve = bump_greeks(P)
    try:
        ed, eg, et = P.opt.delta(), P.opt.gamma(), P.opt.theta()
    except Exception as e:
        ed = eg = et = f"n/a ({e})"
    print(f"{name}: price {base:.4f} bump delta {d:.4f} gamma {g:.5f} vega/pt {ve:.4f} | engine delta {ed} gamma {eg} theta {et}")
    print(f"   (vega and rho: engine does not provide; bump-and-reprice)")

# ---------- (5) grid timing ----------
hdr("5. grid: 50 positions x 100 shocks")
random.seed(7)
positions = []
exps = [ql.Date(20, 11, 2026), ql.Date(18, 12, 2026), ql.Date(15, 1, 2027), ql.Date(16, 4, 2027), ql.Date(18, 6, 2027)]
t = time.perf_counter()
for i in range(50):
    s = random.choice([25.37, 100.0, 180.0, 55.0, 420.0])
    right = random.choice([ql.Option.Call, ql.Option.Put])
    k = round(s * random.uniform(0.8, 1.25), 0)
    ex = random.choice(exps)
    vol = random.uniform(0.2, 1.0)
    divs = [] if i % 2 == 0 else [(ql.Date(20, 11, 2026), s * 0.004), (ql.Date(19, 2, 2027), s * 0.004)]
    divs = [(d, a) for d, a in divs if d < ex]
    positions.append(Pos(right, k, ex, s, vol, 0.042, divs=divs, fd=(100, 200)))
print(f"build 50 positions: {(time.perf_counter()-t)*1000:.0f} ms (FD grid 100x200)")

spy_moves = [-0.20, -0.15, -0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10, 0.15]
iv_shifts = [-0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
betas = [random.uniform(0.6, 2.0) for _ in positions]
bases = [(p.spot_q.value(), p.vol_q.value()) for p in positions]
t = time.perf_counter()
n = 0
for P, (s0, v0), b in zip(positions, bases, betas):
    for m in spy_moves:
        for dv in iv_shifts:
            P.price(spot=s0 * (1 + b * m), vol=max(v0 + dv, 0.01))
            n += 1
dt = time.perf_counter() - t
print(f"{n} repricings (FD 100x200): {dt:.2f} s  ({dt/n*1000:.2f} ms each)")


# ---- FD grid coarseness vs accuracy on B (dividend put) and a high-vol call with divs
print("FD accuracy vs grid (B put, ref 800x1600=%.4f):" % BhiFD.npv())
for tg, xg in ((50, 100), (100, 200), (200, 400)):
    q = Pos(ql.Option.Put, K, expB, S0, v, r, divs=divsB, fd=(tg, xg))
    t = time.perf_counter(); [q.price(spot=S0 * (1 + 0.001 * i)) for i in range(200)]
    print(f"  {tg}x{xg}: {q.price(spot=S0):.4f}  {(time.perf_counter()-t)/200*1000:.2f} ms/price")

# ---- routing: analytic where exact (call, no divs, q=0 -> European BSM), FD otherwise
def analytic(P, spot, vol):
    return bsm(1, spot, P.k, DC.yearFraction(TODAY, P.expiry), P.r, 0.0, vol)
t = time.perf_counter(); fd_n = an_n = 0
for P, (s0, v0), b in zip(positions, bases, betas):
    exact = (P.right == ql.Option.Call and not P.divs)
    for m in spy_moves:
        for dv in iv_shifts:
            sp, vo = s0 * (1 + b * m), max(v0 + dv, 0.01)
            if exact: analytic(P, sp, vo); an_n += 1
            else: P.price(spot=sp, vol=vo); fd_n += 1
dt3 = time.perf_counter() - t
print(f"routed grid: {an_n} analytic + {fd_n} FD(100x200) = {dt3:.2f} s")

# ---- multiprocessing: fork workers, one position slice each
import multiprocessing as mp, os
def work(idx):
    out = 0.0
    for i in idx:
        P, (s0, v0), b = positions[i], bases[i], betas[i]
        for m in spy_moves:
            for dv in iv_shifts:
                out += P.price(spot=s0 * (1 + b * m), vol=max(v0 + dv, 0.01))
    return out
nproc = os.cpu_count()
ctx = mp.get_context("fork")
t = time.perf_counter()
with ctx.Pool(nproc) as pool:
    pool.map(work, [list(range(i, 50, nproc)) for i in range(nproc)])
print(f"fork pool ({nproc} cpus), full FD grid incl. pool startup: {time.perf_counter()-t:.2f} s")
t = time.perf_counter()
for P, (s0, v0) in zip(positions, bases):
    P.price(spot=s0, vol=v0)
    mk = P.npv()
    brentq(lambda x: P.price(vol=x) - mk, 0.01, 5.0, xtol=1e-6)
    P.price(vol=v0)
print(f"50 base IV solves (FD 100x200): {(time.perf_counter()-t):.2f} s")
