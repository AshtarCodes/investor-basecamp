#!/usr/bin/env python3
"""PROTOTYPE (throwaway): what does Schwab's `/chains` ANALYTICAL strategy actually do?

Questions (see tools/schwab/prototype/ANALYTICAL_CHAIN_VERDICT.md for answers):
  T1  Do the volatility / underlyingPrice / interestRate / daysToExpiration overrides change anything,
      and for which request shapes? Does the flat-vol theoretical look American or European?
  T2  Is ANALYTICAL with no overrides the same as SINGLE?
  T3  Does Schwab's own per-contract `volatility` reproduce Schwab's own mark under textbook
      Black-Scholes? Is `theoreticalOptionValue` a function of that volatility?
  T4  Does `theoreticalOptionValue` look American (>= intrinsic on deep ITM puts) or European?

Read-only market data via the existing CLI client. Run from the repo root:
  uv run --project tools/schwab python tools/schwab/prototype_analytical_chain.py [SYMBOL]
"""

from __future__ import annotations

import json
import math
import sys
from statistics import NormalDist, median

from schwab_cli.http_client import schwab_get

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "SPY"
FROM, TO = "2026-11-20", "2027-01-22"
N = NormalDist().cdf


def chain(extra: str = "", *, strike_count: int = 3, frm: str = FROM, to: str = TO, symbol: str = SYMBOL, rng: str = "", strike: float | None = None, ctype: str = "ALL") -> dict:
    pick_strikes = f"&strike={strike}" if strike is not None else f"&strikeCount={strike_count}"
    path = f"/marketdata/v1/chains?symbol={symbol}&contractType={ctype}{pick_strikes}&fromDate={frm}&toDate={to}{rng}{extra}"
    r = schwab_get(path)
    if r.status_code != 200:
        raise SystemExit(f"{path} -> {r.status_code} {r.text[:200]}")
    return json.loads(r.text)


def chain_raw(extra: str, symbol: str = SYMBOL) -> dict:
    path = f"/marketdata/v1/chains?symbol={symbol}{extra}"
    r = schwab_get(path)
    if r.status_code != 200:
        raise SystemExit(f"{path} -> {r.status_code} {r.text[:200]}")
    return json.loads(r.text)


def contracts(d: dict):
    for side in ("callExpDateMap", "putExpDateMap"):
        for exp, strikes in d[side].items():
            for k, cs in strikes.items():
                yield exp, float(k), cs[0]


def bsm(s, k, t, r, v, q, cp):
    d1 = (math.log(s / k) + (r - q + 0.5 * v * v) * t) / (v * math.sqrt(t))
    d2 = d1 - v * math.sqrt(t)
    if cp == "C":
        return s * math.exp(-q * t) * N(d1) - k * math.exp(-r * t) * N(d2)
    return k * math.exp(-r * t) * N(-d2) - s * math.exp(-q * t) * N(-d1)


def implied(s, k, t, r, q, cp, price):
    lo, hi = 0.005, 3.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if bsm(s, k, t, r, mid, q, cp) < price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def snapshot(c: dict) -> dict:
    return {f: c.get(f) for f in ("mark", "volatility", "theoreticalOptionValue", "theoreticalVolatility", "delta", "daysToExpiration")}


def main() -> None:
    print(f"== {SYMBOL} ==")

    # T1: which request shapes honour overrides? (HTTP 200 either way; look at the echoed root and per-contract IVs)
    one = f"&fromDate={FROM}&toDate={FROM}"
    print("\nT1 override request shapes (vol=20)")
    for label, q in [
        ("1 expiry, CALL", f"&contractType=CALL{one}&volatility=20"),
        ("1 expiry + strike=762", f"&contractType=CALL{one}&strike=762&volatility=20"),
        ("2 expiries, CALL", f"&contractType=CALL&fromDate={FROM}&toDate=2026-11-27&volatility=20"),
        ("no dates, CALL", "&contractType=CALL&strikeCount=2&volatility=20"),
    ]:
        d = chain_raw("&strategy=ANALYTICAL" + q)
        ivs = sorted({c["volatility"] for _, _, c in contracts(d)})
        print(f"  {label:<24} root vol={d.get('volatility')}  contracts={sum(1 for _ in contracts(d))}  distinct contract IVs={ivs[:3]}{'...' if len(ivs) > 3 else ''}")

    print("  overrides one at a time, 1 expiry, call K=300 (deep ITM) and K=762:")
    for label, q in [("baseline", ""), ("vol=20", "&volatility=20"), ("S=700", "&underlyingPrice=700"), ("r=3", "&interestRate=3"), ("days=10", "&daysToExpiration=10")]:
        d = chain_raw("&strategy=ANALYTICAL&contractType=CALL" + one + q)
        by_k = {k: c for _, k, c in contracts(d)}
        for k in (300.0, 762.0):
            if k in by_k:
                c = by_k[k]
                print(f"    {label:<9} root={ {x: d.get(x) for x in ('underlyingPrice','interestRate','volatility','daysToExpiration')} } K={k} mark={c['mark']} iv={c['volatility']} theo={c['theoreticalOptionValue']}")

    # T1b: American or European? flat vol puts, deep ITM: European value < intrinsic, American = intrinsic
    d = chain_raw("&strategy=ANALYTICAL&contractType=PUT" + one + "&volatility=20")
    s0, r0 = d["underlyingPrice"], d["interestRate"] / 100
    for e, k, c in contracts(d):
        if k in (900.0, 1000.0):
            t = c["daysToExpiration"] / 365
            print(f"  T1b put K={k}: intrinsic={k - s0:.3f} theo={c['theoreticalOptionValue']}  European floor (q=0) {k * math.exp(-r0 * t) - s0:.3f}")

    # T1c: continuous dividend yield implied by a deep ITM call at flat vol (European-call formula: theo = S e^{-qT} - K e^{-rT})
    d = chain_raw("&strategy=ANALYTICAL&contractType=CALL" + one + "&volatility=20")
    c300 = next(c for _, k, c in contracts(d) if k == 300.0)
    s0, r0 = d["underlyingPrice"], d["interestRate"] / 100
    for basis in (365, 360, 252):
        t = c300["daysToExpiration"] / basis
        q = -math.log((c300["theoreticalOptionValue"] + 300.0 * math.exp(-r0 * t)) / s0) / t
        print(f"  T1c day basis {basis}: implied continuous q = {q * 100:.3f}%")

    # T2: SINGLE vs ANALYTICAL no overrides
    single, anal = chain(), chain("&strategy=ANALYTICAL")
    diffs = [
        (e, k, a["volatility"], b["volatility"])
        for (e, k, a), (_, _, b) in zip(contracts(single), contracts(anal))
        if snapshot(a) != snapshot(b)
    ]
    print(f"\nT2 SINGLE vs ANALYTICAL(no overrides): contracts={sum(1 for _ in contracts(single))}  differing contract fields={len(diffs)}")
    print("   root volatility  SINGLE:", single.get("volatility"), " ANALYTICAL:", anal.get("volatility"))

    # T3: textbook BSM against Schwab's own numbers
    s, r = single["underlyingPrice"], single["interestRate"] / 100
    print(f"\nT3 vs textbook BSM (S={s}, r={r:.4f}); gaps in vol points")
    for q in (0.0, 0.012):
        gaps, theo_gaps, theo_eq_mark = [], [], 0
        n = 0
        for e, k, c in contracts(single):
            t = c["daysToExpiration"] / 365
            cp = "C" if c["putCall"] == "CALL" else "P"
            if not (c.get("mark") and c.get("volatility") and c.get("theoreticalOptionValue")) or t <= 0:
                continue
            n += 1
            iv_mark = implied(s, k, t, r, q, cp, c["mark"]) * 100
            gaps.append(c["volatility"] - iv_mark)
            theo_gaps.append(c["theoreticalOptionValue"] - bsm(s, k, t, r, c["volatility"] / 100, q, cp))
            theo_eq_mark += abs(c["theoreticalOptionValue"] - c["mark"]) < 0.02
        print(
            f"  q={q:.3f}: n={n}  SchwabIV - IV(mark): median {median(gaps):+.2f}, min {min(gaps):+.2f}, max {max(gaps):+.2f}"
            f" | theo - BSM(SchwabIV): median {median(theo_gaps):+.3f}, min {min(theo_gaps):+.3f}, max {max(theo_gaps):+.3f}"
            f" | theo within 2c of mark: {theo_eq_mark}/{n}"
        )

    # adjacent-strike smoothness of Schwab IV on one expiry (calls)
    exp0 = next(iter(single["callExpDateMap"]))
    ivs = [(k, c["volatility"]) for e, k, c in contracts(single) if e == exp0 and c["putCall"] == "CALL"]
    print("   Schwab IV across adjacent call strikes,", exp0, ivs)

    # T4: American vs European on deep ITM puts (strike ~5% above spot)
    k_deep = round(single["underlyingPrice"] * 1.05)
    deep = chain("", frm="2026-12-18", to="2026-12-18", strike=k_deep, ctype="PUT")
    sd = deep["underlyingPrice"]
    print(f"\nT4 deep ITM put K={k_deep} (S={sd}); intrinsic={k_deep - sd:.2f}")
    for e, k, c in contracts(deep):
        t = c["daysToExpiration"] / 365
        iv = c["volatility"] / 100
        print(
            f"  {e} K={k}: mark={c['mark']} theo={c['theoreticalOptionValue']} SchwabIV={c['volatility']} "
            f"BSM(q=0.012,SchwabIV)={bsm(sd, k, t, deep['interestRate'] / 100, iv, 0.012, 'P'):.2f} "
            f"mark>=intrinsic={c['mark'] >= k - sd}"
        )

if __name__ == "__main__":
    main()
