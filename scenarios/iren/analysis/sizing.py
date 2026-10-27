"""Size the early-sale constructions in whole contracts for a given amount of capital, from the cached CLI prices.

Usage: python3 scenarios/iren/analysis/sizing.py [capital] [27|28]
Reads the same cached quotes and exit values as early_sale_report.py. Makes no CLI calls. Standard library only.

Options are bought in whole contracts at the ask (bid for the short leg). Stock takes what is left, in whole shares, so the
capital is fully deployed. Returns are the scale-out returns of early_sale_report (half sold in June, half in November),
on both spot paths, with Rule 2 IV. The search keeps the combination with the best thesis-weighted EV on the interp path
whose thesis-bear P/L is at least each floor, and shows the front path for the same combination.
"""

import itertools
import sys

capital = float(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1] in ("27", "28") else 10_000.0
progs = [a for a in sys.argv[1:] if a in ("27", "28")] or ["28", "27"]
sys.argv = sys.argv[:1]
import early_sale_report as r  # noqa: E402  (parses argv at import, so argv is cleared first)

CALLS = ["itm", "atm", "otm", "far"]
SPREADS = ["spm", "spw"]


def returns(prog, role, hold, path):
    r.PATH = path
    return [r.sleeve_ret(prog, role, c, "scale", hold) for c in r.CASES]


def search(prog):
    w = list(r.WEIGHTS[prog].values())
    best = {}  # floor -> (ev, combo)
    stock_px = r.S0
    for holds in itertools.product((False, True), repeat=2):
        hold = dict(zip(SPREADS, holds))
        sleeves = [(role, hold.get(role, False)) for role in CALLS + SPREADS]
        cost = [r.cost(prog, role) * 100 for role, _ in sleeves]
        ret = {p: [returns(prog, role, h, p) for role, h in sleeves] for p in ("interp", "front")}
        stock = {p: [r.ret(prog, "stock", c, "scale") for c in r.CASES] for p in ("interp", "front")}
        for p in ("interp", "front"):
            r.PATH = p
            stock[p] = [r.ret(prog, "stock", c, "scale") for c in r.CASES]

        def walk(i, left, counts):
            if i == len(sleeves):
                yield counts, left
                return
            for n in range(int(left // cost[i]) + 1):
                yield from walk(i + 1, left - n * cost[i], counts + [n])

        for counts, left in walk(0, capital, []):
            shares = int(left // stock_px)
            used = sum(n * c for n, c in zip(counts, cost)) + shares * stock_px

            def pl(p):
                return [sum(n * cost[i] * ret[p][i][k] for i, n in enumerate(counts)) + shares * stock_px * stock[p][k] for k in range(3)]

            a = pl("interp")
            ev = sum(x * y for x, y in zip(w, a))
            for floor in (0.0, 0.2 * capital, 0.4 * capital, 0.6 * capital):
                if a[0] >= floor - 1e-9 and (floor not in best or ev > best[floor][0]):
                    best[floor] = (ev, sleeves, counts, shares, used, a, pl("front"))
    return best


def show(prog):
    w = list(r.WEIGHTS[prog].values())
    when = "Jan 2028 options sold in 2027" if prog == "27" else "Jan 2029 options sold in 2028"
    print(f"\n=== Programme {prog} ({when}), capital ${capital:,.0f}, spot {r.S0} ===")
    all_stock = int(capital // r.S0)
    for p in ("interp", "front"):
        r.PATH = p
        pl = [all_stock * r.S0 * r.ret(prog, "stock", c, "scale") for c in r.CASES]
        print(f"  all stock, {all_stock} shares, {p}: bear {pl[0]:+,.0f} base {pl[1]:+,.0f} bull {pl[2]:+,.0f} EV {sum(x * y for x, y in zip(w, pl)):+,.0f}")
    best = search(prog)
    for floor in sorted(best):
        ev, sleeves, counts, shares, used, a, f = best[floor]
        buy = ", ".join(f"{n} x {r.label(prog, role)}{' (held)' if h else ''}" for n, (role, h) in zip(counts, sleeves) if n)
        print(f"\n  thesis-bear P/L >= {floor / capital:+.0%} of capital (${floor:+,.0f}): {buy}, {shares} shares; deployed ${used:,.0f}")
        for name, x in (("interp", a), ("front", f)):
            evx = sum(x_ * y for x_, y in zip(w, x))
            print(f"    {name:6} P/L bear {x[0]:+8,.0f} ({x[0] / capital:+5.0%})  base {x[1]:+9,.0f} ({x[1] / capital:+5.0%})  bull {x[2]:+10,.0f} ({x[2] / capital:+6.0%})  EV {evx:+9,.0f} ({evx / capital:+5.0%})")


# Plain builds to set beside the search results: (role, spreads held) -> contracts; shares take the rest
NAMED = {
    "28": {
        "A  stock only": {},
        "B  4 ATM ($25) calls": {("atm", False): 4},
        "C  3 ATM calls + 4 25/75 spreads held": {("atm", False): 3, ("spm", True): 4},
        "D  3 ATM calls + 6 40/90 spreads sold": {("atm", False): 3, ("spw", False): 6},
        "E  3 ATM calls + 6 40/90 spreads held": {("atm", False): 3, ("spw", True): 6},
        "F  8 40/90 spreads sold + 2 far ($90) calls": {("spw", False): 8, ("far", False): 2},
        "G  2 ATM calls + 4 40/90 spreads sold + 2 25/75 spreads held + 3 far calls": {
            ("atm", False): 2, ("spw", False): 4, ("spm", True): 2, ("far", False): 3},
    },
    "27": {
        "A  stock only": {},
        "B  6 deep-ITM ($15) calls": {("itm", False): 6},
        "C  4 deep-ITM calls + 2 25/75 spreads held": {("itm", False): 4, ("spm", True): 2},
        "D  4 deep-ITM calls + 4 40/100 spreads held": {("itm", False): 4, ("spw", True): 4},
    },
}


def named(prog):
    w = list(r.WEIGHTS[prog].values())
    print(f"\n--- plain builds, programme {prog}, capital ${capital:,.0f} ---")
    for name, build in NAMED[prog].items():
        spend = sum(n * r.cost(prog, role) * 100 for (role, _), n in build.items())
        shares = int((capital - spend) // r.S0)
        used = spend + shares * r.S0
        print(f"  {name}: {shares} shares; deployed ${used:,.0f}")
        for p in ("interp", "front"):
            r.PATH = p
            pl = [sum(n * r.cost(prog, role) * 100 * r.sleeve_ret(prog, role, c, "scale", h) for (role, h), n in build.items())
                  + shares * r.S0 * r.ret(prog, "stock", c, "scale") for c in r.CASES]
            ev = sum(x * y for x, y in zip(w, pl))
            print(f"    {p:6} P/L bear {pl[0]:+8,.0f} ({pl[0] / capital:+5.0%})  base {pl[1]:+9,.0f} ({pl[1] / capital:+5.0%})  bull {pl[2]:+10,.0f} ({pl[2] / capital:+6.0%})  EV {ev:+9,.0f} ({ev / capital:+5.0%})")


if __name__ == "__main__":
    for prog in progs:
        show(prog)
        named(prog)
