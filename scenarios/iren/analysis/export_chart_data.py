"""Export the round-trip builds as JSON for the /prototype/roundtrip chart page.

Usage (from the repo root): python3 scenarios/iren/analysis/export_chart_data.py
Writes data/chart-data-27-2026-10-26.json and data/chart-data-28-2026-10-26.json. Standard library only; makes no CLI calls.

It reuses the engine in roundtrip_report.py. For each top-contender build, policy, debt share and path it records the value
of every leg (shares, each call or spread sleeve, puts, banked proceeds) on each valuation date, plus the events. Every trace is
checked against the engine's own simulate(): the legs, banked cash and debt paid must add up to its total to the dollar, or the
export stops.

Values are post-trade holdings at each date. "unit" is the return on one share or contract against its entry cost, as if held.
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.argv = [sys.argv[0], "flat", "near"]  # puts at flat IV; admit the Jan 2028 $40 near-miss (see roundtrip-results.md)
import roundtrip_report as r  # noqa: E402

rg = r.rg
DATA = Path(__file__).resolve().parents[1] / "data"
DEBTS = (0.0, 0.10, 0.25, 0.50)
POLICIES = [
    ("H0 hold", "Hold (no price trigger)"),
    ("H1 sell half @$85", "Sell half at $85"),
    ("H1 sell half @$103", "Sell half at $103"),
    ("H2 sell half + 50% atm puts @$85", "Sell half at $85 + 50% ATM puts"),
    ("H2 sell half + 100% atm puts @$85", "Sell half at $85 + 100% ATM puts"),
    ("H4 50% atm puts only @$85", "50% ATM puts only at $85"),
]
EXITS = [("hold", "Hold to the Jan 2029 expiry"), ("scale", "Sell half in Jun 2028 and half in Nov 2028")]  # Jan 2029 programme only


def exits_for(prog):
    return [e for e, _ in EXITS] if prog == "28" else ["hold"]  # the Jan 2028 programme ends 2027-12-31 whichever


def post_dates(prog, path):
    """Dates after the 2027 trigger window and before the final one: the 2028 sales dates plus the user's own dates."""
    if prog == "27":
        return []
    user = r.CUSTOM[path]["user"] if path in r.CUSTOM else []
    return sorted({rg.J28, rg.N28, *[d for d in user if rg.J28 < d < rg.YE28]})


def timeline(prog, path):
    """Every date a trace records, in order: entry, the 2027 dates, the 2028 dates, then the end."""
    return [rg.START, *r.pre_dates(prog, path), *post_dates(prog, path), rg.YE27 if prog == "27" else rg.YE28]
PATH_LABEL = {
    "SB": "Straight to the bear case ($32, then $46)",
    "SM": "Straight to the base case ($103, then $164)",
    "SU": "Straight to the bull case ($230, then $343)",
    "RT85J": "Up to $85 in June 2027, then down",
    "RT85N": "Up to $85 in November 2027, then down (stress)",
    "RT103J": "Up to $103 in June 2027, then down",
    "RT103N": "Up to $103 in November 2027, then down (stress)",
}
ROLE_ORDER = ["itm", "atm", "otm", "far", "spm", "spw", "sp30", "sp35", "sp40"]


def iso(d):
    return d.isoformat()


def leg_label(prog, role):
    exp = "Jan 2028" if prog == "27" else "Jan 2029"
    ks = [k for k, _ in r.ROLE[prog][role]]
    return f"{exp} ${ks[0]} call" if len(ks) == 1 else f"{exp} {ks[0]}/{ks[1]} call spread"


def style_of(name):
    if name == "all stock":
        return "Baseline"
    rp, bp, sp = (int(x[1:]) for x in name.split()[0].split("/"))
    if rp >= 50:
        return "Return-heavy"
    if bp >= 45:
        return "Barbell-heavy"
    if sp >= 50:
        return "Stock-heavy"
    return "Balanced"


def trace(cons, prog, pol, path, f):
    """Replicates r.simulate(), recording post-trade holdings at each timeline date."""
    kn = r.knots_of(path)
    hold_exit = prog == "28" and pol.get("exit") == "hold"
    n, shares, cash, puts, fired, debt_cum = dict(cons["n"]), cons["shares"], 0.0, [], None, 0.0
    cost_unit = {role: r.cost1(prog, role) * 100 for role in n}
    legs = {"stock": [], **{role: [] for role in n}, "puts": [], "cash": [], "debt": [], "total": []}
    unit = {k: [] for k in legs}
    events = []
    put_cost_unit = None
    realized = {"stock": 0.0, **{role: 0.0 for role in n}, "puts": 0.0}
    cost_basis = {"stock": shares * r.S0, **{role: n[role] * cost_unit[role] for role in n}, "puts": 0.0}

    def put_value(d, s, final=False):
        if final and hold_exit:
            return sum(m * 100 * r.val("expiry", po, r.EXPDATE[prog], s, "-") for po, m in puts)
        return sum(m * 100 * r.val("sell", po, d, s, r.IV) for po, m in puts)

    def record(d, s, frac=1.0, final=False):
        """frac is the share of shares, outright calls and puts still held; spreads are held to expiry whatever frac is."""
        hold = {"stock": shares * s * frac}
        unit["stock"].append(s / r.S0 - 1)
        for role in n:
            spread = r.is_spread(prog, role)
            if final and (spread or hold_exit):
                per = r.held(prog, role, kn)
            elif frac == 0.0 and not spread:
                per = None  # sold; no valuation on this date
            elif d == rg.START:
                per = r.cost1(prog, role)
            else:
                per = r.mark(prog, role, d, s)
            hold[role] = 0.0 if per is None else n[role] * 100 * per * (1.0 if spread else frac)
            unit[role].append(None if per is None or not cost_unit[role] else per * 100 / cost_unit[role] - 1)
        live = bool(puts) and d != rg.START and frac > 0
        hold["puts"] = put_value(d, s, final) * frac if live else 0.0
        unit["puts"].append(put_value(d, s, final) / sum(m * put_cost_unit for _, m in puts) - 1 if live and put_cost_unit else None)
        for k, v in hold.items():
            legs[k].append(v)
        legs["cash"].append(cash)
        unit["cash"].append(None)
        legs["debt"].append(debt_cum)
        unit["debt"].append(None)
        total = sum(hold.values()) + cash + debt_cum
        legs["total"].append(total)
        unit["total"].append(total / r.CAPITAL - 1)

    record(rg.START, r.S0)
    for d in r.pre_dates(prog, path):
        s = rg.spot_on(kn, d)
        if pol["trigger"] and fired is None and s >= pol["trigger"]:
            fired = d
            events.append({"date": iso(d), "type": "trigger", "label": f"IREN reaches ${s:,.0f} (trigger ${pol['trigger']})"})
            if pol["sale"]:
                got = 0.0
                for role in n:
                    if not r.is_spread(prog, role) and n[role]:
                        k = -(-n[role] // 2)
                        got += k * 100 * r.mark(prog, role, d, s)
                        realized[role] += k * 100 * r.mark(prog, role, d, s)
                        n[role] -= k
                cash += got
                if got:
                    events.append({"date": iso(d), "type": "sale", "label": "Sell half of the outright calls", "amount": round(got)})
            if pol["puts"]:
                ratio, kind, fund = pol["puts"]
                notional = shares * s + sum(n[x] * 100 * r.mark(prog, x, d, s) for x in n)
                m = int(ratio * notional / s / 100 + 0.5)
                po = rg.occ(r.EXPCODE[prog], r.PUTK[(prog, pol["trigger"])][kind], "P")
                c = r.val("sell", po, d, s, r.IV) * 100 * (1 + r.HALF[po])
                m = min(m, int((cash if fund == "proceeds" else shares * s) // c)) if c > 0 else 0
                if m > 0:
                    cost_basis["puts"] += m * c
                    if fund == "proceeds":
                        cash -= m * c
                    else:
                        shares -= m * c / s
                        realized["stock"] += m * c
                    puts.append((po, m))
                    put_cost_unit = c
                    strike = int(po[-8:]) / 1000
                    events.append({"date": iso(d), "type": "puts", "label": f"Buy {m} x Jan {2028 if prog == '27' else 2029} ${strike:.0f} puts", "amount": round(m * c)})
        if d == rg.N27:
            wealth = cash + shares * s + sum(n[x] * 100 * r.mark(prog, x, d, s) for x in n) + put_value(d, s)
            need = f * max(0.0, wealth - r.CAPITAL)
            target = need
            take = min(cash, need)
            cash -= take
            need -= take
            for role in sorted(n, key=lambda x: -r.lev(prog, x)):
                unit_val = 100 * r.mark(prog, role, d, s)
                if need <= 1e-9 or unit_val <= 0 or not n[role]:
                    continue
                k = min(n[role], r.math.ceil(need / unit_val))
                pay = min(need, k * unit_val)
                need -= pay
                cash += k * unit_val - pay
                realized[role] += k * unit_val
                n[role] -= k
            if need > 1e-9:
                k = min(shares, need / s)
                shares -= k
                realized["stock"] += k * s
                need -= k * s
            paid = target - need
            debt_cum += paid
            if paid > 0:
                events.append({"date": iso(d), "type": "debt", "label": f"Pay debt ({f:.0%} of the gain)", "amount": round(paid)})
        record(d, s)
    if prog == "27":
        se = rg.spot_on(kn, rg.YE27)
        record(rg.YE27, se, final=True)
    else:
        frac = 1.0
        for d in post_dates(prog, path):
            sd = rg.spot_on(kn, d)
            if d in rg.DATES28 and not hold_exit:  # the two scale-out sales; any other date is only a valuation
                v = shares * sd + sum(n[x] * 100 * r.mark(prog, x, d, sd) for x in n if not r.is_spread(prog, x)) + put_value(d, sd)
                cash += 0.5 * v
                realized["stock"] += 0.5 * shares * sd
                for x in n:
                    if not r.is_spread(prog, x):
                        realized[x] += 0.5 * n[x] * 100 * r.mark(prog, x, d, sd)
                realized["puts"] += 0.5 * put_value(d, sd)
                frac -= 0.5
                events.append({"date": iso(d), "type": "sale", "label": "Sell half of what is left", "amount": round(0.5 * v)})
            record(d, sd, frac=frac)
        record(rg.YE28, rg.spot_on(kn, rg.YE28), frac=frac if hold_exit else 0.0, final=True)
    contrib = {k: realized[k] + legs[k][-1] - cost_basis[k] for k in realized}
    return legs, unit, events, contrib


def round_list(xs, nd):
    return [None if x is None else round(x, nd) for x in xs]


FEATURED = {  # the builds discussed in roundtrip-results.md, always exported
    "28": ["R60/B20/S20 R3 B2", "R40/B30/S30 R2 B2", "R30/B52/S18 R3 B1", "R20/B20/S60 R1 B2",
           # the Jan 2029 30/75, 35/75 and 40/75 spreads (B4-B6) beside the 25/75 (B1) in two discussed mixes
           "R30/B52/S18 R3 B4", "R30/B52/S18 R3 B5", "R30/B52/S18 R3 B6",
           "R40/B30/S30 R2 B4", "R40/B30/S30 R2 B5", "R40/B30/S30 R2 B6"],
    "27": ["R60/B30/S10 R4 B2", "R30/B17/S52 R4 B2", "R20/B20/S60 R4 B1"],
}


def select_builds(prog, cons):
    pols = [p for p, _ in POLICIES]
    seen = {}
    for pn in pols:
        rows = sorted(((r.expected(c, prog, r.POLS[pn], 0.25), cn) for cn, (c, _) in cons.items()), key=lambda x: -x[0][0])
        best_bear = -9.0
        for e, cn in rows:
            if e[1] > best_bear + 1e-9:
                best_bear = e[1]
                seen[cn] = seen.get(cn, 0) + 1
    h0 = {cn: r.expected(cons[cn][0], prog, r.POLS["H0 hold"], 0.25)[0] for cn in seen}
    ranked = sorted(seen, key=lambda cn: (-seen[cn], -h0[cn]))
    picked = [cn for cn in FEATURED[prog] if cn in cons]
    for cn in ranked:
        if len(picked) >= (16 if prog == "28" else 12):
            break
        if cn not in picked and cn != "all stock":
            picked.append(cn)
    return picked + ["all stock"]


def make_run(c, prog, pol, path, f, label):
    """One build, policy (with its exit), debt share and path: the traced legs, checked against r.simulate() to the dollar."""
    legs, unit, events, contrib = trace(c, prog, pol, path, f)
    sim = r.simulate(c, prog, pol, path, f)
    if abs(legs["total"][-1] - sim["total"]) > 0.5:
        raise SystemExit(f"trace mismatch {label} {path}: {legs['total'][-1]:.2f} vs {sim['total']:.2f}")
    if abs(sum(contrib.values()) - (sim["total"] - r.CAPITAL)) > 1.0:
        raise SystemExit(f"contribution mismatch {label} {path}: {sum(contrib.values()):.2f} vs {sim['total'] - r.CAPITAL:.2f}")
    return {"contrib": {k: round(v) for k, v in contrib.items()}, "legs": {k: round_list(v, 0) for k, v in legs.items()},
            "unit": {k: round_list(v, 3) for k, v in unit.items() if k not in ("cash", "debt")},
            "events": events, "total": round(sim["total"]), "end": round(sim["end"]), "debt": round(sim["debt"])}


def build_id(name):
    return name.replace(" ", "_").replace("/", "-")


def export(prog):
    adm, cons = r.constructions(prog)
    strict = {role for role, row in r.admitted(prog).items() if all(c - st >= 2.0 for c, st in row)}
    names = select_builds(prog, cons)
    weights = r.path_weights(prog)
    out = {
        "meta": {"spot": r.S0, "capital": r.CAPITAL, "programme": prog, "putIv": r.IV, "generated": "2026-10-26",
                 "source": "scenarios/iren/data/roundtrip-*-2026-10-26.json via roundtrip_report.py"},
        "dates": [iso(d) for d in timeline(prog, "SM")],
        "policies": [{"id": p, "label": lbl} for p, lbl in POLICIES],
        "exits": [{"id": e, "label": lbl} for e, lbl in EXITS] if prog == "28" else [],
        "paths": {p: {"label": PATH_LABEL[p], "weight": round(weights[p], 4), "stress": p.endswith("N"),
                      "spot": [rg.spot_on(r.PATHS[p], d) for d in timeline(prog, p)],
                      "knots": [[iso(d), s] for d, s in r.PATHS[p][1:]]} for p in r.PATHS},
        "builds": [],
        "runs": {},
    }
    for cn in names:
        c, _ = cons[cn]
        build = {
            "id": build_id(cn), "name": cn, "style": style_of(cn), "featured": cn in FEATURED[prog],
            "shares": round(c["shares"], 1), "capitalShares": round(c["shares"] * r.S0),
            "legs": [{"id": role, "label": leg_label(prog, role), "n": c["n"][role], "unitCost": round(r.cost1(prog, role) * 100),
                      "spread": r.is_spread(prog, role),
                      "test200": ("pass" if role in strict else "near" if role in adm else "fail") if not r.is_spread(prog, role) else None}
                     for role in ROLE_ORDER if role in c["n"] and c["n"][role]],
            "metrics": {},
        }
        for pn, _ in POLICIES:
            for ex in exits_for(prog):
                pol = {**r.POLS[pn], "exit": ex}
                key = f"{pn}~{ex}"  # the chart's policy id: the trigger rule, then how 2028 ends
                build["metrics"][key] = {}
                for f in DEBTS:
                    e = r.expected(c, prog, pol, f)
                    build["metrics"][key][f"{f:.2f}"] = {"E": round(e[0], 4), "bear": round(e[1], 4), "base": round(e[2], 4), "bull": round(e[3], 4), "debt": round(e[4])}
                    out["runs"][f"{build['id']}|{key}|{f:.2f}"] = {p: make_run(c, prog, pol, p, f, f"{cn} {key} f={f}") for p in r.PATHS}
        out["builds"].append(build)
    path = DATA / f"chart-data-{prog}-2026-10-26.json"
    path.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print(f"programme {prog}: {len(out['builds'])} builds, {len(out['runs'])} runs -> {path.name} ({path.stat().st_size / 1e6:.2f} MB)")
    for b in out["builds"]:
        m = b["metrics"]["H0 hold~scale" if prog == "28" else "H0 hold~hold"]["0.25"]
        print(f"  {b['name']:28} {b['style']:14} E {m['E']:+7.0%} bear {m['bear']:+6.0%} base {m['base']:+6.0%} legs {[(x['id'], x['n']) for x in b['legs']]} shares {b['shares']:.0f}")


if __name__ == "__main__":
    for prog in ("28", "27"):
        export(prog)
