"""Write the v2 chart's seed: v1's exported builds from both programmes as Builds, and the 11 Price Paths.

Usage (from the repo root): python3 scenarios/iren/analysis/export_seed.py
Writes data/roundtrip-v2-seed.json, which the /prototype/roundtrip server loads into its rt_ tables on first use. Standard
library only; no CLI calls.

Paths (plan-v2): the seven v1 thesis paths, holding until 2028, then Sell 50% -> cash on 2028-06-30 and Sell 100% -> cash
on 2028-11-30 (the 2028 prices are v1's path on those dates); and a "sell half" copy of each round trip that adds
Sell 50% -> cash on the date it reaches $85 (on v1's path from the 2026-10-26 spot). Weights: Base 45, Bull 20, 7 for
each bear-type path, 0 for the copies.
"""

import json
import sys
from datetime import timedelta

sys.argv = [sys.argv[0], "flat", "near"]  # v1's setup for the chart export
import export_chart_data as ecd  # noqa: E402
import roundtrip_report as r  # noqa: E402

rg = r.rg
OUT = rg.DATA / "roundtrip-v2-seed.json"
NAMES = {
    "SM": "Base", "SU": "Bull", "SB": "Bear",
    "RT85J": "$85 Jun 2027, then down", "RT85N": "$85 Nov 2027, then down",
    "RT103J": "$103 Jun 2027, then down", "RT103N": "$103 Nov 2027, then down",
}
WEIGHT = {"SM": 45, "SU": 20}
EXPIRY = {"27": "Jan 2028", "28": "Jan 2029"}


def point(d, price, action="hold", pct=None):
    return {"date": d.isoformat(), "price": round(price, 2), "action": action, "sellPct": pct}


def reaches(knots, level):
    d = rg.START
    while rg.spot_on(knots, d) < level:
        d += timedelta(days=1)
    return d


def paths():
    out = []
    for pid, name in NAMES.items():
        kn = r.PATHS[pid]
        pts = {d: point(d, s) for d, s in kn[1:]}
        pts[rg.J28] = point(rg.J28, rg.spot_on(kn, rg.J28), "sell_cash", 50)
        pts[rg.N28] = point(rg.N28, rg.spot_on(kn, rg.N28), "sell_cash", 100)
        desc = f"{ecd.PATH_LABEL[pid]}. v1 stored path: holds until 2028, sells half the options in Jun 2028 and the rest in Nov 2028."
        out.append({"key": pid, "name": name, "description": desc, "weight": WEIGHT.get(pid, 7), "points": sorted(pts.values(), key=lambda p: p["date"])})
        if pid.startswith("RT"):
            at = reaches(kn, 85)
            copy = dict(pts)
            copy[at] = point(at, max(85.0, rg.spot_on(kn, at)), "sell_cash", 50)
            out.append({
                "key": f"{pid}-half", "name": f"{name} · sell half at $85", "weight": 0,
                "description": f"{ecd.PATH_LABEL[pid]}, selling half the options when IREN first reaches $85 ({at:%b %d, %Y}).",
                "points": sorted(copy.values(), key=lambda p: p["date"]),
            })
    return out


def builds():
    out, seen = [], set()
    for prog in ("28", "27"):
        _, cons = r.constructions(prog)
        expiry = f"20{r.EXPCODE[prog][:2]}-{r.EXPCODE[prog][2:4]}-{r.EXPCODE[prog][4:]}"
        for name in ecd.select_builds(prog, cons):
            if name == "all stock":
                if name not in seen:
                    out.append({"key": "all-shares", "name": "All shares", "description": "Baseline: the whole budget in shares.", "budget": 10_000, "sleeves": []})
                seen.add(name)
                continue
            c, _ = cons[name]
            sleeves = [
                {"contracts": c["n"][role], "legs": [{"expiry": expiry, "strike": k, "kind": "C", "side": q} for k, q in r.ROLE[prog][role]]}
                for role in ecd.ROLE_ORDER
                if c["n"].get(role)
            ]
            note = " Discussed in roundtrip-results.md." if name in ecd.FEATURED[prog] else ""
            out.append({
                "key": f"{prog}-{ecd.build_id(name)}", "name": f"{name} · {EXPIRY[prog]}",
                "description": f"{ecd.style_of(name)}. v1 stored build.{note}", "budget": 10_000, "sleeves": sleeves,
            })
    return out


if __name__ == "__main__":
    seed = {"builds": builds(), "paths": paths()}
    OUT.write_text(json.dumps(seed, indent=1) + "\n")
    print(f"{len(seed['builds'])} builds, {len(seed['paths'])} paths -> {OUT.name}")
