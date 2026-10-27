"""Test two-book constructions with a half-sale, a put hedge and a November 2027 debt payment, from cached CLI prices.

Usage: python3 scenarios/iren/analysis/roundtrip_report.py [flat|rule2|up] [debt <fraction>]
Reads data/roundtrip-quotes-2026-10-26.json and data/roundtrip-exit-values-2026-10-26.json (from roundtrip_grid.py).
Makes no CLI calls. Standard library only. The first argument is the IV assumption for puts (default flat); calls are
always Rule 2. The debt fraction (default 0.25) is the share of the gain at 2027-11-30 that is withdrawn then.

Programmes: 27 = Jan 2028 options, everything left is valued on 2027-12-31; 28 = Jan 2029 options, everything left is
sold half on 2028-06-30 and half on 2028-11-30. Spreads are held to expiry in both. Paths and dates are in roundtrip_grid.py.

The 2028 exit (Jan 2029 programme) is the policy's "exit": "scale" (the default here) sells half of what is left on
2028-06-30 and half on 2028-11-30; "hold" sells nothing and values everything at the Jan 2029 expiry. The chart export
(export_chart_data.py) offers both; the report's own tables use "scale".

Rules modelled:
  trigger: the first of 2027-06-30 / 2027-11-30 on which the path's spot is at or above the trigger level ($85 or $103).
  half-sale: on the trigger date, sell half (rounded up) of each outright call position; proceeds are banked at 0%.
  puts: bought on the trigger date, sized to cover ratio x the dollar value of what is left, in whole contracts, paid from
    the banked proceeds (half-sale policies) or by selling shares (puts-only policies); price is the model value plus half
    of today's quoted spread (at most 5%). No 2028 puts.
  debt: on 2027-11-30, withdraw debt x max(0, wealth - 10,000) from banked cash first, then calls (highest leverage first),
    then shares. Puts are not sold for it.
Banked cash earns nothing and is counted in the final wealth.
"""

import math
import sys
from datetime import date

import roundtrip_grid as rg

Q = rg.json.loads(rg.QUOTES.read_text())
X = rg.json.loads(rg.EXITS.read_text())
S0 = Q["spotRef"]
BY = {c["occ"]: c for c in Q["contracts"]}
PATHS = rg.paths(S0)
CAPITAL = 10_000.0
IV = next((a for a in sys.argv[1:] if a in ("flat", "rule2", "up")), "flat")
DEBT = float(sys.argv[sys.argv.index("debt") + 1]) if "debt" in sys.argv else 0.25
MARGIN = 0.05 if "near" in sys.argv else 0.0  # "near" admits calls within 5 points of the 200-point test

EXPCODE = {"27": "280121", "28": "290119"}
EXPDATE = {"27": date(2028, 1, 21), "28": date(2029, 1, 19)}
ROLE = {
    "27": {"itm": [(15, 1)], "atm": [(25, 1)], "otm": [(40, 1)], "far": [(75, 1)], "spm": [(25, 1), (75, -1)], "spw": [(40, 1), (140, -1)]},
    "28": {"itm": [(15, 1)], "atm": [(25, 1)], "otm": [(40, 1)], "far": [(90, 1)], "spm": [(25, 1), (75, -1)], "spw": [(40, 1), (90, -1)],
           "sp30": [(30, 1), (75, -1)], "sp35": [(35, 1), (75, -1)], "sp40": [(40, 1), (75, -1)]},
}
PUTK = {("27", 85): {"atm": 85, "otm": 70}, ("27", 103): {"atm": 100, "otm": 85},
        ("28", 85): {"atm": 85, "otm": 70}, ("28", 103): {"atm": 90, "otm": 70}}
WEIGHTS = {"27": (0.30, 0.50, 0.20), "28": (0.35, 0.45, 0.20)}  # bear, base, bull (thesis.md)
HALF = {c["occ"]: min(0.05, 0.5 * (c["ask"] - c["bid"]) / c["mark"]) for c in Q["contracts"]}


CUSTOM = {}  # path id -> {"knots": [(date, spot)], "user": [dates]} for paths drawn on the chart (custom_path.py)


def knots_of(path):
    return PATHS[path] if path in PATHS else CUSTOM[path]["knots"]


def pre_dates(prog, path):
    """Dates on which the trigger is tested and positions are valued before the 2028 exits: Jun and Nov 2027, plus the
    chart user's own dates (before 2027-12-31 for the Jan 2028 programme, before 2028-06-30 for Jan 2029)."""
    if path not in CUSTOM:
        return rg.DATES27
    limit = rg.YE27 if prog == "27" else rg.J28
    return sorted(d for d in {rg.J27, rg.N27, *CUSTOM[path]["user"]} if rg.START < d < limit)


def val(mode, o, d, s, rule="rule2"):
    key = f"{mode}|{o}|{d}|{s:.2f}|{rule}"
    if mode == "expiry" and key not in X:  # the CLI's intrinsic value, for a spot we did not price
        k = int(o[-8:]) / 1000
        return max(s - k, 0.0) if o[-9] == "C" else max(k - s, 0.0)
    return X[key]["value"]


def legs(prog, role):
    return [(rg.occ(EXPCODE[prog], k), q) for k, q in ROLE[prog][role]]


def is_spread(prog, role):
    return len(ROLE[prog][role]) == 2


def cost1(prog, role):
    """Entry cost per share: ask for longs, bid for shorts."""
    return sum(BY[o]["ask"] * q if q > 0 else BY[o]["bid"] * q for o, q in legs(prog, role))


def lev(prog, role):
    return sum(q * BY[o]["delta"] for o, q in legs(prog, role)) * S0 / cost1(prog, role)


def mark(prog, role, d, s):
    return sum(q * val("sell", o, d, s) for o, q in legs(prog, role))


def held(prog, role, kn):
    se = rg.spot_on(kn, rg.YE27 if prog == "27" else rg.YE28)
    return sum(q * val("expiry", o, EXPDATE[prog], se, "-") for o, q in legs(prog, role))


def path_weights(prog):
    bear, base, bull = WEIGHTS[prog]
    w = {"SM": base, "SU": bull, "SB": 0.2 * bear}
    w.update({p: 0.2 * bear for p in PATHS if p.startswith("RT")})
    return w


def build(prog, rpct, bpct, rrec, brec):
    n, left = {}, 0.0
    for pct, rec in ((rpct, rrec), (bpct, brec)):
        for role, w in rec:
            unit = cost1(prog, role) * 100
            k = int(CAPITAL * pct * w // unit)
            n[role] = n.get(role, 0) + k
            left += CAPITAL * pct * w - k * unit
    return {"n": n, "shares": (CAPITAL * (1 - rpct - bpct) + left) / S0}


def simulate(cons, prog, pol, path, f):
    kn = knots_of(path)
    n, shares, cash, puts, fired, debt = dict(cons["n"]), cons["shares"], 0.0, [], None, 0.0
    for d in pre_dates(prog, path):
        s = rg.spot_on(kn, d)
        if pol["trigger"] and fired is None and s >= pol["trigger"]:
            fired = d
            if pol["sale"]:
                for role in n:
                    if not is_spread(prog, role) and n[role]:
                        k = -(-n[role] // 2)
                        cash += k * 100 * mark(prog, role, d, s)
                        n[role] -= k
            if pol["puts"]:
                ratio, kind, fund = pol["puts"]
                notional = shares * s + sum(n[r] * 100 * mark(prog, r, d, s) for r in n)
                m = int(ratio * notional / s / 100 + 0.5)
                po = rg.occ(EXPCODE[prog], PUTK[(prog, pol["trigger"])][kind], "P")
                c = val("sell", po, d, s, IV) * 100 * (1 + HALF[po])
                m = min(m, int((cash if fund == "proceeds" else shares * s) // c)) if c > 0 else 0
                if m > 0:
                    if fund == "proceeds":
                        cash -= m * c
                    else:
                        shares -= m * c / s
                    puts.append((po, m))
        if d == rg.N27:
            wealth = cash + shares * s + sum(n[r] * 100 * mark(prog, r, d, s) for r in n) + sum(m * 100 * val("sell", po, d, s, IV) for po, m in puts)
            need = f * max(0.0, wealth - CAPITAL)
            target = need
            take = min(cash, need)
            cash -= take
            need -= take
            for role in sorted(n, key=lambda r: -lev(prog, r)):
                unit = 100 * mark(prog, role, d, s)
                if need <= 1e-9 or unit <= 0 or not n[role]:
                    continue
                k = min(n[role], math.ceil(need / unit))
                pay = min(need, k * unit)
                need -= pay
                cash += k * unit - pay
                n[role] -= k
            if need > 1e-9:
                k = min(shares, need / s)
                shares -= k
                need -= k * s
            debt = target - need
    if prog == "27":
        se = rg.spot_on(kn, rg.YE27)
        end = cash + shares * se + sum(n[r] * 100 * (held(prog, r, kn) if is_spread(prog, r) else mark(prog, r, rg.YE27, se)) for r in n)
        end += sum(m * 100 * val("sell", po, rg.YE27, se, IV) for po, m in puts)
    elif pol.get("exit") == "hold":  # nothing is sold in 2028: shares and calls ride to the Jan 2029 expiry
        se = rg.spot_on(kn, rg.YE28)
        end = cash + shares * se + sum(n[r] * 100 * held(prog, r, kn) for r in n)
        end += sum(m * 100 * val("expiry", po, EXPDATE[prog], se, "-") for po, m in puts)
    else:
        end = cash + sum(n[r] * 100 * held(prog, r, kn) for r in n if is_spread(prog, r))
        for d in rg.DATES28:
            sd = rg.spot_on(kn, d)
            end += 0.5 * (shares * sd + sum(n[r] * 100 * mark(prog, r, d, sd) for r in n if not is_spread(prog, r))
                          + sum(m * 100 * val("sell", po, d, sd, IV) for po, m in puts))
    return {"end": end, "debt": debt, "total": end + debt, "fired": fired}


def admitted(prog):
    """Outright calls whose base-case return beats the stock's by at least 200 points on both the steady and front paths."""
    out = {}
    kn = PATHS["SM"]
    dates = rg.DATES27 if prog == "27" else rg.DATES28
    front = float(rg.CASE27["base"] if prog == "27" else rg.CASE28["base"])
    for role in ROLE[prog]:
        if is_spread(prog, role):
            continue
        row = []
        for label, spot_of in (("steady", lambda d: rg.spot_on(kn, d)), ("front", lambda d: front)):
            c = sum(mark(prog, role, d, spot_of(d)) / cost1(prog, role) - 1 for d in dates) / 2
            st = sum(spot_of(d) / S0 - 1 for d in dates) / 2
            row.append((c, st))
        out[role] = row
    return out


def style(prog, rpct, bpct):
    return f"R{int(rpct * 100)}/B{int(bpct * 100)}/S{int(round((1 - rpct - bpct) * 100))}"


POLS = {"H0 hold": {"trigger": None, "sale": False, "puts": None}}
for T in (85, 103):
    POLS[f"H1 sell half @${T}"] = {"trigger": T, "sale": True, "puts": None}
    for r in (0.5, 1.0):
        for k in ("atm", "otm"):
            POLS[f"H2 sell half + {int(r * 100)}% {k} puts @${T}"] = {"trigger": T, "sale": True, "puts": (r, k, "proceeds")}
            POLS[f"H4 {int(r * 100)}% {k} puts only @${T}"] = {"trigger": T, "sale": False, "puts": (r, k, "shares")}


def expected(cons, prog, pol, f):
    w = path_weights(prog)
    res = {p: simulate(cons, prog, pol, p, f) for p in PATHS}
    ev = sum(w[p] * res[p]["total"] for p in PATHS) / CAPITAL - 1
    bear = sum(w[p] * res[p]["total"] for p in PATHS if p[1] == "B" or p.startswith("RT")) / sum(w[p] for p in PATHS if p[1] == "B" or p.startswith("RT")) / CAPITAL - 1
    dd = sum(w[p] * res[p]["debt"] for p in PATHS)
    return ev, bear, res["SM"]["total"] / CAPITAL - 1, res["SU"]["total"] / CAPITAL - 1, dd, res


def constructions(prog):
    adm = {r for r, row in admitted(prog).items() if all(c - st >= 2.0 - MARGIN for c, st in row)}
    rrecs = [[("atm", 1.0)], [("atm", 0.5), ("otm", 0.5)], [("otm", 0.5), ("far", 0.5)], [("otm", 1.0)]]
    brecs = [[("spm", 1.0)], [("spm", 0.7), ("far", 0.3)], [("spm", 0.5), ("spw", 0.5)]]
    brecs += [[(role, 1.0)] for role in ("sp30", "sp35", "sp40") if role in ROLE[prog]]  # B4-B6: Jan 2029 30/75, 35/75, 40/75
    out = {"all stock": ({"n": {}, "shares": CAPITAL / S0}, None)}
    for rp in (0.2, 0.3, 0.4, 0.5, 0.6):
        rem = 1 - rp
        for bp in (rem * 0.25, rem * 0.5, rem * 0.75):
            for i, rr in enumerate(rrecs):
                if any(role not in adm for role, _ in rr):
                    continue
                for j, br in enumerate(brecs):
                    out[f"{style(prog, rp, bp)} R{i + 1} B{j + 1}"] = (build(prog, rp, bp, rr, br), (rr, br))
    return adm, out


PICK = ["H0 hold", "H1 sell half @$85", "H1 sell half @$103", "H2 sell half + 50% atm puts @$85", "H4 50% atm puts only @$85"]


def line(tag, cn, e):
    return f"  {tag:34} {cn:26} E {e[0]:+7.0%}  bear {e[1]:+6.0%}  base {e[2]:+6.0%}  bull {e[3]:+7.0%}  debt ${e[4]:6,.0f}"


def header(prog):
    name = "Jan 2028 options (valued 2027-12-31)" if prog == "27" else "Jan 2029 options (sold Jun/Nov 2028)"
    print(f"\n{'=' * 8} Programme {prog}: {name}; puts IV {IV}; debt {DEBT:.0%} of the gain on 2027-11-30; spot {S0}")
    print("200-point test (call return less stock return, base case, scale-out sale; steady path / already-there path):")
    for role, row in admitted(prog).items():
        (c1, s1), (c2, s2) = row
        ok = all(c - st >= 2.0 - MARGIN for c, st in row)
        print(f"  {role:4} ${ROLE[prog][role][0][0]:<4}: {(c1 - s1) * 100:+6.0f} pts / {(c2 - s2) * 100:+6.0f} pts  {'PASS' if ok else 'fail'}")


def frontier(prog):
    header(prog)
    adm, cons = constructions(prog)
    print(f"  admitted for the return book: {sorted(adm)}; {len(cons)} constructions")
    for pn in PICK:
        pol = POLS[pn]
        rows = [(expected(c, prog, pol, DEBT), cn) for cn, (c, _) in cons.items()]
        stock = next(r for r in rows if r[1] == "all stock")
        print(f"\n {pn}  (E = expected total return incl. debt paid; bear = mean of bear paths)")
        print(line("all stock", "", stock[0]))
        for floor in (0.4, 0.6, 0.8, 1.0, 1.2, 1.5):
            ok = [r for r in rows if r[0][1] >= floor]
            if ok:
                b = max(ok, key=lambda r: r[0][0])
                print(line(f"best with bear >= {floor:+.0%}", b[1], b[0]))


def detail(prog, names):
    header(prog)
    adm, cons = constructions(prog)
    for cn in names:
        c, rec = cons[cn]
        print(f"\n {cn}: contracts {c['n']}, {c['shares']:.0f} shares")
        for pn, pol in POLS.items():
            if not (pn in PICK or "100%" in pn and "@$85" in pn and "H2" in pn):
                continue
            print(line(pn, "", expected(c, prog, pol, DEBT)))


def pathtable(prog, names, pols):
    """Per path: debt paid on 2027-11-30 and final wealth, in dollars, for 10%, 25% and 50% of the gain."""
    header(prog)
    adm, cons = constructions(prog)
    for cn in names:
        c, _ = cons[cn]
        print(f"\n {cn}: contracts {c['n']}, {c['shares']:.0f} shares   (debt $ / final wealth $ / total return incl. debt)")
        for pn in pols:
            print(f"  {pn}")
            for p in PATHS:
                row = []
                for f in (0.10, 0.25, 0.50):
                    r = simulate(c, prog, POLS[pn], p, f)
                    row.append(f"{r['debt']:7,.0f} / {r['end']:8,.0f} / {r['total'] / CAPITAL - 1:+6.0%}")
                print(f"    {p:7} fired {str(simulate(c, prog, POLS[pn], p, 0.25)['fired'] or '-'):10} " + " | ".join(row))


if __name__ == "__main__":
    if "pathtable" in sys.argv:
        names = [a.replace("_", " ").replace("-", "/") for a in sys.argv[1:] if a.startswith("R")]
        pathtable("27" if "27" in sys.argv else "28", names, ["H0 hold", "H1 sell half @$85"])
    elif "detail" in sys.argv:
        names = [a for a in sys.argv[1:] if a.startswith("R")]
        prog = "27" if "27" in sys.argv else "28"
        detail(prog, [a.replace("_", " ").replace("-", "/") for a in names])
    else:
        for prog in ("28", "27"):
            frontier(prog)
