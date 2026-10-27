"""Price a price path drawn on the /prototype/roundtrip chart, with the pricing engine's batch mode, and trace every build along it.

Usage (from the repo root; the chart's server function runs this):
  python3 scenarios/iren/analysis/custom_path.py --programme 28 --points '[["2027-03-31", 90], ["2027-09-30", 60]]' --out result.json
Each point is a (date, IREN price). The path starts at the 2026-10-26 spot, runs geometrically between the points, and stays at
the last price afterwards. Prints "PROGRESS done total" lines while it prices, then writes the result JSON to --out.

The engine is the one behind the other chart data (roundtrip_report.py, export_chart_data.py): the same builds, trigger rules,
exits and debt payment, so a custom path is comparable with the seven stored ones. The chart's builds are read from the stored
chart-data file. Two differences from the stored paths, both because the user chooses the dates:
  - the trigger (sell half, puts) is tested on every user date, and on 2027-06-30 and 2027-11-30, before 2028-06-30;
  - the user's dates after that are valuation points only (nothing is sold on them).
Prices come from the pricing engine's batch mode (packages/pricing-engine, the `pricing-worker` process), not from one
`schwab option price` call each: per contract one request with the stored Mark, spot and rate from the 2026-10-26 quotes file,
and one Shock per (date, spot, IV rule) wanted. The Mark-implied IV is solved by the engine, and each rule's volatility is
applied to that (an absolute shift). Against the CLI's 756 stored valuations this differs by 0.03% at the median, at most
$0.08 a share. A path takes about a second; nothing is cached, and the stored paths' CLI values are never mixed in.
"""

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, time as dtime
from zoneinfo import ZoneInfo

REAL_ARGV = sys.argv[1:]
sys.argv = [sys.argv[0], "flat", "near"]  # same setup as export_chart_data.py; the real arguments are parsed below
import export_chart_data as ecd  # noqa: E402

r = ecd.r
rg = r.rg
ROOT = rg.DATA.parents[2]  # the repo root, where `uv run --project packages/pricing-engine` is run from
NY = ZoneInfo("America/New_York")
PATH = "CU"
TRIGGERS = (85, 103)


def needs(prog, builds, dates):
    """key -> (occ, date, spot, rule): the 'sell' valuations a trace along this path asks for."""
    kn = r.knots_of(PATH)
    roles = {leg["id"] for b in builds for leg in b["legs"]}
    calls = {rg.occ(r.EXPCODE[prog], k) for role in roles for k, _ in r.ROLE[prog][role]}
    final = dates[-1]
    out = {}

    def add(o, d, rule):
        s = rg.spot_on(kn, d)
        out[f"sell|{o}|{d}|{s:.2f}|{rule}"] = (o, d, s, rule)

    for d in dates[1:]:
        if prog == "28" and d == final:
            continue  # valued at expiry, which is intrinsic and needs no call
        for o in sorted(calls):
            add(o, d, "rule2")
    for level in TRIGGERS:
        fire = next((d for d in r.pre_dates(prog, PATH) if rg.spot_on(kn, d) >= level), None)
        if fire is None:
            continue
        o = rg.occ(r.EXPCODE[prog], r.PUTK[(prog, level)]["atm"], "P")
        for d in dates:
            if d >= fire and not (prog == "28" and d == final):
                add(o, d, r.IV)
    return out


def exit_instant(d):
    """The CLI's `--as-of <date>`: 4 pm New York on that date."""
    return datetime.combine(d, dtime(16, 0), NY)


def sourced(value):
    return {"value": value, "from": "stored 2026-10-26 quote"}


def batch(contracts):
    """One `batch` request to a pricing worker; returns its per-contract answers in order."""
    request = {"id": "custom-path", "type": "batch", "iv_shift_mode": "absolute", "contracts": contracts}
    worker = subprocess.run(
        ["uv", "run", "--project", "packages/pricing-engine", "pricing-worker", "--workers", "4"],
        input=json.dumps(request) + "\n", cwd=ROOT, capture_output=True, text=True,
    )
    lines = [json.loads(line) for line in worker.stdout.splitlines() if line.startswith("{")]
    answer = next((m for m in lines if m.get("id") == "custom-path"), None)
    if answer is None or not answer["ok"]:
        detail = answer["error"] if answer else worker.stderr[-400:]
        raise SystemExit(f"pricing worker failed: {detail}")
    return answer["result"]["contracts"]


def price(todo):
    """Fill r.X with the batch engine's sale value for each wanted valuation (overriding any stored CLI value)."""
    by_occ = {}
    for key, (o, d, s, rule) in todo:
        by_occ.setdefault(o, []).append((key, d, s, rule))
    base = {}
    for o in by_occ:
        q = r.BY[o]
        right = "call" if q["kind"] == "C" else "put"
        expiry = f"20{q['expiry'][:2]}-{q['expiry'][2:4]}-{q['expiry'][4:]}"
        base[o] = {
            "contract": {"root": "IREN", "expiry": expiry, "strike": q["strike"], "right": right, "exercise": "american"},
            "valuation": q["quoteTime"], "spot": sourced(q["spot"]), "rate": sourced(q["rate"] / 100), "mark": sourced(q["mark"]),
        }
    # first the Mark-implied IV of each contract (a zero Shock), then the real Shocks, with each rule's vol as a shift from it
    zero = {"spot_move": 0, "iv_shift": 0, "days_forward": 0}
    ivs = batch([{"request": base[o], "shocks": [zero]} for o in by_occ])
    shocks = {}
    vols = {}
    for (o, items), first in zip(by_occ.items(), ivs):
        iv = first["iv"]["value"]
        q = r.BY[o]
        qt = datetime.fromisoformat(q["quoteTime"])
        shocks[o] = []
        for key, d, s, rule in items:
            vol = rg.vol_for(rule, iv * 100, s, r.S0) / 100 if iv is not None else 0.0
            vols[key] = vol * 100
            shocks[o].append({"spot_move": s / q["spot"] - 1, "iv_shift": vol - iv if iv is not None else 0.0, "days_forward": (exit_instant(d) - qt).total_seconds() / 86400})
    priced = batch([{"request": base[o], "shocks": shocks[o]} for o in by_occ])
    for (o, items), answer in zip(by_occ.items(), priced):
        if not answer["ok"]:
            raise SystemExit(f"pricing worker failed for {o}: {answer['error']}")
        for (key, *_), amount in zip(items, answer["prices"]):
            r.X[key] = {"vol": round(vols[key], 4), "value": amount}
    print(f"PROGRESS {len(todo)} {len(todo)}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--programme", choices=("27", "28"), required=True)
    ap.add_argument("--points", required=True, help='JSON [["YYYY-MM-DD", price], ...]')
    ap.add_argument("--out", required=True)
    args = ap.parse_args(REAL_ARGV)
    prog = args.programme
    points = sorted((date.fromisoformat(d), round(float(p), 2)) for d, p in json.loads(args.points))
    if not points or any(not (rg.START < d <= rg.YE28) or p <= 0 for d, p in points):
        raise SystemExit("points must be dated after 2026-10-26 and by 2028-12-29, with a positive price")
    knots = [(rg.START, r.S0), *points]
    r.CUSTOM[PATH] = {"knots": knots, "user": [d for d, _ in points]}

    stored = json.loads((rg.DATA / f"chart-data-{prog}-2026-10-26.json").read_text())
    builds = stored["builds"]
    _, cons = r.constructions(prog)
    dates = ecd.timeline(prog, PATH)

    wanted = needs(prog, builds, dates)
    todo = list(wanted.items())  # everything is priced by the batch, so no stored CLI value is mixed into the path
    print(f"PROGRESS 0 {len(todo)}", flush=True)
    price(todo)

    runs = {}
    for b in builds:
        c, _ = cons[b["name"]]
        for pn, _ in ecd.POLICIES:
            for ex in ecd.exits_for(prog):
                pol = {**r.POLS[pn], "exit": ex}
                for f in ecd.DEBTS:
                    runs[f"{b['id']}|{pn}~{ex}|{f:.2f}"] = ecd.make_run(c, prog, pol, PATH, f, f"{b['name']} {pn}~{ex} f={f}")
    spots = [rg.spot_on(r.knots_of(PATH), d) for d in dates]
    result = {
        "programme": prog,
        "dates": [ecd.iso(d) for d in dates],
        "path": {"label": "Your price points", "weight": 0, "stress": False, "spot": spots},
        "userDates": [ecd.iso(d) for d, _ in points],
        "runs": runs,
    }
    with open(args.out, "w") as f:
        json.dump(result, f, separators=(",", ":"))
    print(f"DONE {len(runs)} runs, {len(dates)} dates", flush=True)


if __name__ == "__main__":
    main()
