"""Test position constructions against the IREN thesis cases, from the cached CLI prices.

Usage: python3 scenarios/iren/analysis/construction_report.py [flat|rule2]
Reads data/leap-quotes-2026-10-26.json and data/leap-exit-values-2026-10-26.json (written by construction_grid.py).
Makes no CLI calls. Standard library only.

A sleeve's return is exit value over its entry cost, with entry at the ask for longs and the bid for shorts. A
construction is a set of capital weights over sleeves (the rest is cash at 0%), so its return is the weighted sum.
Exit is at the model value, with no exit slippage. The thesis EV uses the owner's case weights per year-end.
"""

import itertools
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
Q = json.loads((DATA / "leap-quotes-2026-10-26.json").read_text())
X = json.loads((DATA / "leap-exit-values-2026-10-26.json").read_text())
SPOT = Q["spotRef"]
BY_OCC = {c["occ"]: c for c in Q["contracts"]}
WEIGHTS = {"2027": {"bear": 0.30, "base": 0.50, "bull": 0.20}, "2028": {"bear": 0.35, "base": 0.45, "bull": 0.20}}
CASES = ["bear", "base", "bull"]
STRESS = ["+0%", "-30%", "-50%"]
RULE = sys.argv[1] if len(sys.argv) > 1 else "rule2"


def occ(expiry: str, strike: int) -> str:
    return f"IREN  {expiry}C{strike * 1000:08d}"


def call(expiry, strike):
    return [(occ(expiry, strike), +1)]


def spread(expiry, k1, k2):
    return [(occ(expiry, k1), +1), (occ(expiry, k2), -1)]


# name -> legs; the stock is the empty list
SLEEVES = {
    "stock": [],
    "J29 $15 deep ITM": call("290119", 15),
    "J29 $25 ATM": call("290119", 25),
    "J29 $40 OTM": call("290119", 40),
    "J29 $60 OTM": call("290119", 60),
    "J29 $75 OTM": call("290119", 75),
    "J29 $90 far OTM": call("290119", 90),
    "J29 25/75 spread": spread("290119", 25, 75),
    "J29 25/90 spread": spread("290119", 25, 90),
    "J29 40/90 spread": spread("290119", 40, 90),
    "J29 40/75 spread": spread("290119", 40, 75),
    "J28 $25 ATM": call("280121", 25),
    "J28 $40 OTM": call("280121", 40),
    "J28 $75 OTM": call("280121", 75),
    "J28 25/75 spread": spread("280121", 25, 75),
    "J28 40/75 spread": spread("280121", 40, 75),
    "J28 40/100 spread": spread("280121", 40, 100),
}


def cost(legs):
    return SPOT if not legs else sum(BY_OCC[o]["ask"] * q if q > 0 else BY_OCC[o]["bid"] * q for o, q in legs)


def exit_spot(h, label):
    return next(r["spot"] for k, r in X.items() if k.startswith(f"{h}|") and k.split("|")[2] == label)


def sleeve_return(name, h, label):
    legs = SLEEVES[name]
    if not legs:
        return exit_spot(h, label) / SPOT - 1
    value = sum(q * X[f"{h}|{o}|{label}|{RULE}"]["value"] for o, q in legs)
    return value / cost(legs) - 1


def valid(name, h):
    return all(f"{h}|{o}|bear|{RULE}" in X for o, _ in SLEEVES[name])


def delta_per_dollar(name):
    legs = SLEEVES[name]
    if not legs:
        return 1.0
    return sum(q * BY_OCC[o]["delta"] for o, q in legs) * SPOT / cost(legs)


def metrics(alloc, h):
    r = {lab: sum(w * sleeve_return(n, h, lab) for n, w in alloc.items()) for lab in CASES + STRESS}
    r["ev"] = sum(WEIGHTS[h][c] * r[c] for c in CASES)
    r["lev"] = sum(w * delta_per_dollar(n) for n, w in alloc.items())
    return r


CONSTRUCTIONS = {
    "1 All stock": {"stock": 1.0},
    "2 All ATM LEAP": {"J29 $25 ATM": 1.0},
    "3 All OTM LEAP": {"J29 $60 OTM": 1.0},
    "4 All spreads 25/75": {"J29 25/75 spread": 1.0},
    "5 Your sketch: 30 stock / 30 ATM / 20 40-90 spread / 10 OTM": {
        "stock": 0.3, "J29 $25 ATM": 0.3, "J29 40/90 spread": 0.2, "J29 $60 OTM": 0.1},
    "6 Same, spread is 25/75": {
        "stock": 0.3, "J29 $25 ATM": 0.3, "J29 25/75 spread": 0.2, "J29 $60 OTM": 0.1},
    "7 Stock-heavy: 50 stock / 25 ATM / 15 spread / 10 OTM": {
        "stock": 0.5, "J29 $25 ATM": 0.25, "J29 25/75 spread": 0.15, "J29 $60 OTM": 0.1},
    "8 Stock + OTM kicker: 80 stock / 20 OTM": {"stock": 0.8, "J29 $60 OTM": 0.2},
    "9 Deep-ITM core: 60 $15 LEAP / 20 spread / 10 OTM / 10 cash": {
        "J29 $15 deep ITM": 0.6, "J29 25/75 spread": 0.2, "J29 $60 OTM": 0.1},
    "10 Barbell: 50 stock / 50 far OTM": {"stock": 0.5, "J29 $90 far OTM": 0.5},
}


def show(title, items, h):
    print(f"\n{title}  (exit {h}-year-end, IV {RULE})")
    print(f"{'':62}{'bear':>8}{'base':>8}{'bull':>8}{'EV':>8}{'flat':>8}{'-30%':>8}{'-50%':>8}{'delta x':>8}")
    for name, alloc in items.items():
        if not all(valid(n, h) for n in alloc):
            continue
        m = metrics(alloc, h)
        row = [m["bear"], m["base"], m["bull"], m["ev"], m["+0%"], m["-30%"], m["-50%"]]
        print(f"{name[:61]:62}" + "".join(f"{v:8.0%}" for v in row) + f"{m['lev']:8.2f}")


def sleeves_table():
    print(f"\nSleeves, return on the capital in the sleeve (entry ask/bid, spot {SPOT}, IV {RULE})")
    for h in ("2027", "2028"):
        print(f"\n  exit {h}-year-end" + " " * 30 + "".join(f"{x:>8}" for x in CASES + STRESS + ["EV"]) + f"{'cost':>8}{'delta/$':>8}")
        for n in SLEEVES:
            if not valid(n, h):
                continue
            r = [sleeve_return(n, h, lab) for lab in CASES + STRESS]
            ev = sum(WEIGHTS[h][c] * sleeve_return(n, h, c) for c in CASES)
            print(f"  {n:46}" + "".join(f"{v:8.0%}" for v in r) + f"{ev:8.0%}{cost(SLEEVES[n]):8.2f}{delta_per_dollar(n):8.2f}")


def matched(items, h):
    """Each construction scaled to 1.0x entry delta (weights divided by its delta multiple, the rest cash)."""
    print(f"\nSame constructions at equal stock-equivalent delta (1.0x), rest in cash  (exit {h}-year-end, IV {RULE})")
    print(f"{'':62}{'bear':>8}{'base':>8}{'bull':>8}{'EV':>8}{'flat':>8}{'-30%':>8}{'-50%':>8}{'invested':>9}")
    for name, alloc in items.items():
        if not all(valid(n, h) for n in alloc):
            continue
        m = metrics(alloc, h)
        k = 1 / m["lev"]
        row = [m["bear"], m["base"], m["bull"], m["ev"], m["+0%"], m["-30%"], m["-50%"]]
        print(f"{name[:61]:62}" + "".join(f"{v * k:8.0%}" for v in row) + f"{sum(alloc.values()) * k:9.0%}")


def compositions(n, total):
    """Every n-tuple of non-negative ints summing to at most total."""
    if n == 1:
        for x in range(total + 1):
            yield (x,)
        return
    for x in range(total + 1):
        for rest in compositions(n - 1, total - x):
            yield (x, *rest)


def frontier(target=1.0, min_bear=0.0):
    """Best average thesis EV over both year-ends at a fixed entry delta, per floor on the loss if the stock goes nowhere.

    J29 sleeves only, 5% steps, the rest in cash. Both thesis bear cases must return at least min_bear. The floor is on
    the loss of total capital if the stock is flat at the year-end where it is worse (2028, when the Jan 2029 options
    have three weeks left). The -30% and -50% columns are the worse-year losses at those spot moves.
    """
    names = ["stock", "J29 $15 deep ITM", "J29 $25 ATM", "J29 25/75 spread", "J29 40/90 spread", "J29 $60 OTM", "J29 $90 far OTM"]
    labs = ("bear", "base", "bull", "+0%", "-30%", "-50%")
    vec = {n: [sleeve_return(n, h, lab) for h in ("2027", "2028") for lab in labs] for n in names}
    dl = {n: delta_per_dollar(n) for n in names}
    wts = [WEIGHTS[h][c] for h in ("2027", "2028") for c in CASES]
    rows = []
    for ws in compositions(len(names), 20):
        if sum(ws) == 0:
            continue
        w = [x / 20 for x in ws]
        if abs(sum(wi * dl[n] for wi, n in zip(w, names)) - target) > 0.025:
            continue
        r = [sum(wi * vec[n][k] for wi, n in zip(w, names)) for k in range(12)]
        if min(r[0], r[6]) < min_bear:
            continue
        ev = (sum(r[k] * wts[k] for k in range(3)) + sum(r[6 + k] * wts[3 + k] for k in range(3))) / 2
        rows.append((dict((n, wi) for n, wi in zip(names, w) if wi), ev, min(r[3], r[9]), min(r[4], r[10]), min(r[5], r[11]), r[0], r[6]))
    print(f"\nFrontier at {target:.2f}x entry delta, both thesis bears >= {min_bear:.0%}: best average thesis EV (2027 and 2028 year-ends) by floor on the flat-stock loss (IV {RULE})")
    for floor in (0.0, -0.10, -0.20, -0.30, -0.40, -0.60):
        ok = [r for r in rows if r[2] >= floor - 1e-9]
        if not ok:
            print(f"  flat floor {floor:5.0%}: no mix")
            continue
        b = max(ok, key=lambda r: r[1])
        mix = ", ".join(f"{int(w * 100)} {n}" for n, w in b[0].items()) + f", {100 - int(sum(b[0].values()) * 100)} cash"
        print(f"  flat >= {floor:5.0%}: EV {b[1]:5.0%}  flat {b[2]:5.0%}  -30% {b[3]:5.0%}  -50% {b[4]:5.0%}  bear27 {b[5]:5.0%} bear28 {b[6]:5.0%} | {mix}")


if __name__ == "__main__":
    if "frontier" in sys.argv:
        frontier(1.0)
        frontier(1.0, 0.25)
        frontier(1.25)
        sys.exit()
    sleeves_table()
    for h in ("2027", "2028"):
        show("Constructions", CONSTRUCTIONS, h)
    for h in ("2027", "2028"):
        matched(CONSTRUCTIONS, h)
