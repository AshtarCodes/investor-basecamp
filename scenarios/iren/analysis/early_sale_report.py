"""Test fully invested IREN constructions sold early on a rally, or (for spreads) held to expiry, from the cached CLI prices.

Usage: python3 scenarios/iren/analysis/early_sale_report.py [rule2|flat] [interp|front] [frontier]
Reads data/early-sale-quotes-2026-10-26.json and data/early-sale-exit-values-2026-10-26.json (from early_sale_grid.py).
Makes no CLI calls. Standard library only. See early_sale_grid.py for the programmes, dates and spot paths.

A sleeve's return is exit value over entry cost (ask for longs, bid for shorts). A construction is capital weights summing
to 100%: there is no cash. "Scale" sells half of each early-sold sleeve in June and half in November. "Hold" means a
spread is held to expiry, valued at intrinsic on the year-end case spot; stock and outright calls are still sold early.
No downside stress is run: the cases are the thesis bear, base and bull only.
"""

import json
import sys
from pathlib import Path

from early_sale_grid import PROGRAMMES, THESIS, occ, sale_spot

DATA = Path(__file__).resolve().parents[1] / "data"
Q = json.loads((DATA / "early-sale-quotes-2026-10-26.json").read_text())
X = json.loads((DATA / "early-sale-exit-values-2026-10-26.json").read_text())
S0 = Q["spotRef"]
BY = {c["occ"]: c for c in Q["contracts"]}
CASES = ("bear", "base", "bull")
WEIGHTS = {"27": {"bear": 0.30, "base": 0.50, "bull": 0.20}, "28": {"bear": 0.35, "base": 0.45, "bull": 0.20}}
RULE = next((a for a in sys.argv[1:] if a in ("rule2", "flat")), "rule2")
PATH = next((a for a in sys.argv[1:] if a in ("interp", "front")), "interp")

# role -> legs as (strike, quantity); an empty list is the stock
ROLES = {
    "27": {
        "stock": [], "itm": [(15, 1)], "atm": [(25, 1)], "otm": [(40, 1)], "far": [(75, 1)],
        "spm": [(25, 1), (75, -1)], "spw": [(40, 1), (140, -1)], "sp4075": [(40, 1), (75, -1)], "sp40100": [(40, 1), (100, -1)],
    },
    "28": {
        "stock": [], "itm": [(15, 1)], "atm": [(25, 1)], "otm": [(40, 1)], "far": [(90, 1)],
        "spm": [(25, 1), (75, -1)], "spw": [(40, 1), (90, -1)], "sp2590": [(25, 1), (90, -1)], "sp4075": [(40, 1), (75, -1)],
    },
}


def label(prog, role):
    legs = ROLES[prog][role]
    if not legs:
        return "stock"
    ks = "/".join(str(k) for k, _ in legs)
    return f"{'Jan 2028' if prog == '27' else 'Jan 2029'} {'$' + ks if len(legs) == 1 else ks + ' spread'}"


def legs_occ(prog, role):
    e = PROGRAMMES[prog]["expiry"]
    return [(occ(e, k), q) for k, q in ROLES[prog][role]]


def cost(prog, role):
    legs = legs_occ(prog, role)
    return S0 if not legs else sum(BY[o]["ask"] * q if q > 0 else BY[o]["bid"] * q for o, q in legs)


def delta_x(prog, role):
    legs = legs_occ(prog, role)
    return 1.0 if not legs else sum(q * BY[o]["delta"] for o, q in legs) * S0 / cost(prog, role)


def ret(prog, role, case, mode):
    """Return on a sleeve. mode: jun, nov, scale (half each), hold (to expiry)."""
    if mode == "scale":
        return (ret(prog, role, case, "jun") + ret(prog, role, case, "nov")) / 2
    p = PROGRAMMES[prog]
    legs = legs_occ(prog, role)
    if mode == "hold":
        spot = THESIS[prog][case]
        return spot / S0 - 1 if not legs else sum(q * X[f"{prog}|{o}|expiry|{case}"]["value"] for o, q in legs) / cost(prog, role) - 1
    d = p["dates"][0 if mode == "jun" else 1]
    if not legs:
        return sale_spot(prog, case, d, PATH, S0) / S0 - 1
    return sum(q * X[f"{prog}|{o}|{d}|{case}|{PATH}|{RULE}"]["value"] for o, q in legs) / cost(prog, role) - 1


def sleeve_ret(prog, role, case, mode, hold_spreads):
    """A spread follows hold_spreads when set; everything else is sold early."""
    is_spread = len(ROLES[prog][role]) == 2
    if mode != "hold" and is_spread and hold_spreads:
        return ret(prog, role, case, "hold")
    return ret(prog, role, case, mode)


def metrics(prog, alloc, hold_spreads=False):
    out = {}
    for mode in ("jun", "nov", "scale"):
        r = {c: sum(w * sleeve_ret(prog, role, c, mode, hold_spreads) for role, w in alloc.items()) for c in CASES}
        r["ev"] = sum(WEIGHTS[prog][c] * r[c] for c in CASES)
        out[mode] = r
    out["delta"] = sum(w * delta_x(prog, role) for role, w in alloc.items())
    return out


CONSTRUCTIONS = {
    "1 All stock": {"stock": 1.0},
    "2 All deep-ITM LEAP ($15)": {"itm": 1.0},
    "3 All ATM LEAP ($25)": {"atm": 1.0},
    "4 All $40 LEAP": {"otm": 1.0},
    "5 80 stock / 20 $40 LEAP": {"stock": 0.8, "otm": 0.2},
    "6 Your sketch: 30 stock / 30 ATM / 20 wide spread / 10 far": {"stock": 0.3, "atm": 0.3, "spw": 0.2, "far": 0.1},
    "7 50 stock / 50 deep-ITM": {"stock": 0.5, "itm": 0.5},
    "8 40 stock / 40 deep-ITM / 20 $40 LEAP": {"stock": 0.4, "itm": 0.4, "otm": 0.2},
    "9 60 deep-ITM / 20 wide spread / 20 $40 LEAP": {"itm": 0.6, "spw": 0.2, "otm": 0.2},
    "10 50 stock / 50 mid spread (25/75)": {"stock": 0.5, "spm": 0.5},
    "11 50 stock / 50 wide spread": {"stock": 0.5, "spw": 0.5},
    "12 40 stock / 30 ATM / 30 wide spread": {"stock": 0.4, "atm": 0.3, "spw": 0.3},
    "13 All wide spreads": {"spw": 1.0},
    "14 All mid spreads (25/75)": {"spm": 1.0},
}


def table(prog):
    print(f"\n=== Programme {prog}: {label(prog, 'itm').split(' $')[0]} options sold {PROGRAMMES[prog]['dates'][0]} / {PROGRAMMES[prog]['dates'][1]}, "
          f"spot path {PATH}, IV {RULE}, spot {S0} ===")
    print("\nSleeves (return on the capital in the sleeve)")
    print(f"{'':28}{'cost':>7}{'$/ctr':>7}{'dlt/$':>7} | " + "".join(f"{c + ' ' + m:>11}" for m in ("jun", "nov") for c in CASES) + " |" + "".join(f"{'hold ' + c:>11}" for c in CASES))
    for role in ROLES[prog]:
        row = "".join(f"{ret(prog, role, c, m):11.0%}" for m in ("jun", "nov") for c in CASES)
        hold = "".join(f"{ret(prog, role, c, 'hold'):11.0%}" for c in CASES) if len(ROLES[prog][role]) == 2 else " " * 33
        print(f"{label(prog, role):28}{cost(prog, role):7.2f}{cost(prog, role) * 100:7.0f}{delta_x(prog, role):7.2f} | {row} |{hold}")
    print(f"\nConstructions (no cash). Scale = half sold in each month. EV on the thesis weights {tuple(WEIGHTS[prog].values())}.")
    print(f"{'':66}{'bear':>7}{'base':>7}{'bull':>7}{'EV':>7} | {'EV jun':>7}{'EV nov':>7} | {'dlt x':>6}")
    for name, alloc in CONSTRUCTIONS.items():
        variants = [(name, False)]
        if any(len(ROLES[prog][r]) == 2 for r in alloc):
            variants = [(name + "  [spreads sold]", False), (name + "  [spreads held]", True)]
        for nm, hold in variants:
            m = metrics(prog, alloc, hold)
            s = m["scale"]
            print(f"{nm[:65]:66}{s['bear']:7.0%}{s['base']:7.0%}{s['bull']:7.0%}{s['ev']:7.0%} | {m['jun']['ev']:7.0%}{m['nov']['ev']:7.0%} | {m['delta']:6.2f}")


def compositions(n, total):
    """Every n-tuple of non-negative ints summing to exactly total."""
    if n == 1:
        yield (total,)
        return
    for x in range(total + 1):
        for rest in compositions(n - 1, total - x):
            yield (x, *rest)


def frontier(prog):
    """Best EV with no cash, 5% steps, by floor on the scale-out thesis-bear return."""
    sleeves = [("stock", False), ("itm", False), ("atm", False), ("otm", False), ("far", False),
               ("spm", False), ("spw", False), ("spw", True)]
    vec = [[sleeve_ret(prog, r, c, "scale", h) for c in CASES] for r, h in sleeves]
    wts = [WEIGHTS[prog][c] for c in CASES]
    names = [label(prog, r) + (" (held)" if h else "") for r, h in sleeves]
    rows = []
    for ws in compositions(len(sleeves), 20):
        r = [sum(w * vec[i][k] for i, w in enumerate(ws)) / 20 for k in range(3)]
        rows.append((ws, r))
    print(f"\nFrontier, programme {prog} (no cash, 5% steps, scale-out, spot path {PATH}, IV {RULE}): best EV by floor on the thesis-bear return")
    for floor in (-0.10, 0.0, 0.10, 0.20, 0.30, 0.40):
        ok = [x for x in rows if x[1][0] >= floor - 1e-9]
        if not ok:
            print(f"  bear >= {floor:4.0%}: no mix")
            continue
        ws, r = max(ok, key=lambda x: sum(w * v for w, v in zip(wts, x[1])))
        mix = ", ".join(f"{w * 5} {n}" for w, n in zip(ws, names) if w)
        ev = sum(w * v for w, v in zip(wts, r))
        print(f"  bear >= {floor:4.0%}: EV {ev:5.0%} (bear {r[0]:4.0%}, base {r[1]:5.0%}, bull {r[2]:6.0%}) | {mix}")


if __name__ == "__main__":
    if "frontier" in sys.argv:
        for prog in ("27", "28"):
            frontier(prog)
    else:
        for prog in ("27", "28"):
            table(prog)
