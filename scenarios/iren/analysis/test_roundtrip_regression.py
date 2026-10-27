"""The v2 engine against v1 (roundtrip_report.simulate) on the 2026-10-26 quotes and CLI values: plan-v2 step 2, the gate.

Run from the repo root: uv run --project packages/pricing-engine pytest scenarios/iren/analysis

v2 prices from v1's own cache here, so any difference is the engine's. Only runs whose rules v2 expresses the same way are
compared, which leaves out three rule changes the plan made on purpose:
  - an Action sells every option Sleeve, spreads too; v1's half-sale sold outright calls only. So the half-sale runs use
    each build without its spread Sleeves (their money in shares instead);
  - an Action never sells shares; v1's "scale" 2028 exit sold half of the shares in Jun and half in Nov 2028, so no
    scale run is compared (this includes spec.md's +674%, which is the scale exit; its hold exit is +768%);
  - a Leg is held to the weekday before its expiry; v1's Jan 2028 programme valued everything on 2027-12-31. Its runs
    are expressed as a path that ends on 2027-12-31 with Sell 100% -> cash that day, on builds without spreads.
Where v2 sells the day before expiry, v1 has no value, so this test uses the CLI's expiry value (intrinsic), which is what
v1 held to.
"""

import sys

import pytest

sys.argv = [sys.argv[0], "flat", "near"]  # v1's setup for the chart export (export_chart_data.py)
import export_chart_data as ecd  # noqa: E402
import roundtrip_engine as eng  # noqa: E402
import roundtrip_report as v1  # noqa: E402

rg = v1.rg
TOLERANCE = 25.0  # dollars on $10,000 (plan-v2, step 2)


def iso_expiry(code: str) -> str:
    return f"20{code[:2]}-{code[2:4]}-{code[4:]}"


QUOTES = {
    "takenAt": "2026-10-26T12:00:00-04:00",
    "spot": v1.S0,
    "contracts": [{**c, "expiry": iso_expiry(c["expiry"])} for c in v1.Q["contracts"]],
}
SELL = {}
for key, rec in v1.X.items():
    mode, occ, d, s, rule = key.split("|")
    if mode == "sell" and rule == "rule2":
        SELL.setdefault((occ, d), []).append((float(s), rec["value"]))


def cached_value(leg, d, s):
    """v1's CLI value for this Leg, at the nearest cached spot within 5 cents (adding a point rounds the path to cents)."""
    if d.isoformat() >= eng.sale_date(leg["expiry"]):
        return max(s - leg["strike"], 0.0) if leg["kind"] == "C" else max(leg["strike"] - s, 0.0)
    occ = rg.occ(leg["expiry"][2:].replace("-", ""), leg["strike"], leg["kind"])
    near = min(SELL[(occ, d.isoformat())], key=lambda c: abs(c[0] - s))
    assert abs(near[0] - s) <= 0.05, f"no cached value for {occ} on {d} at {s}"
    return near[1]


def as_build(prog, cons):
    expiry = iso_expiry(v1.EXPCODE[prog])
    sleeves = [
        {"id": role, "contracts": n, "legs": [{"expiry": expiry, "strike": k, "kind": "C", "side": q} for k, q in v1.ROLE[prog][role]]}
        for role, n in cons["n"].items()
        if n
    ]
    return {"id": "v1", "budget": v1.CAPITAL, "sleeves": sleeves}


def as_path(name, actions=(), end=None):
    """A v1 path as a Price Path: its knots as points, plus a point for each (date, action, percent)."""
    knots = v1.PATHS[name]
    points = {d: {"date": d.isoformat(), "price": s, "action": "hold", "sellPct": None} for d, s in knots[1:] if end is None or d <= end}
    for d, action, pct in actions:
        points[d] = {"date": d.isoformat(), "price": rg.spot_on(knots, d), "action": action, "sellPct": pct}
    return {"id": name, "weight": 0, "points": list(points.values())}


def without_spreads(prog, cons):
    freed = sum(n * v1.cost1(prog, role) * 100 for role, n in cons["n"].items() if v1.is_spread(prog, role))
    return {"n": {role: n for role, n in cons["n"].items() if not v1.is_spread(prog, role)}, "shares": cons["shares"] + freed / v1.S0}


def exported(prog):
    _, cons = v1.constructions(prog)
    return [(name, cons[name][0]) for name in ecd.select_builds(prog, cons)]


def compare(prog, policy, builds):
    """Every build x path x debt share: v1's total against v2's on the same rules. Returns the misses."""
    pol = {**v1.POLS[policy], "exit": "hold"}
    misses = []
    for name, cons in builds:
        for p in v1.PATHS:
            for f in ecd.DEBTS:
                old = v1.simulate(cons, prog, pol, p, f)
                actions = [(old["fired"], "sell_cash", 50)] if old["fired"] and pol["sale"] else []
                end = None
                if prog == "27":
                    end = rg.YE27
                    actions.append((rg.YE27, "sell_cash", 100))
                new = eng.run(as_build(prog, cons), as_path(p, actions, end), QUOTES, f, cached_value)
                if abs(new["total"] - old["total"]) > TOLERANCE:
                    misses.append((name, p, f, round(old["total"]), round(new["total"])))
    return misses


def test_holding_to_the_jan_2029_expiry_matches_v1_for_every_exported_build():
    assert compare("28", "H0 hold", exported("28")) == []


@pytest.mark.parametrize("policy", ["H1 sell half @$85", "H1 sell half @$103"])
def test_selling_half_at_a_trigger_matches_v1_on_builds_without_spreads(policy):
    assert compare("28", policy, [(n, without_spreads("28", c)) for n, c in exported("28")]) == []


@pytest.mark.parametrize("policy", ["H0 hold", "H1 sell half @$85", "H1 sell half @$103"])
def test_the_jan_2028_programme_matches_v1_as_a_sale_on_2027_12_31(policy):
    assert compare("27", policy, [(n, without_spreads("27", c)) for n, c in exported("27")]) == []


def test_the_return_heavy_build_reproduces_its_v1_figures_when_held_to_expiry():
    # chart-data-28-2026-10-26.json, "R60/B20/S20 R3 B2", "H0 hold~hold", debt 25%: E +768.05%, bear +35.32%
    _, cons = v1.constructions("28")
    b = as_build("28", cons["R60/B20/S20 R3 B2"][0])
    weights = v1.path_weights("28")
    totals = {p: eng.run(b, as_path(p), QUOTES, 0.25, cached_value)["total"] for p in v1.PATHS}
    expected = sum(weights[p] * totals[p] for p in totals) / v1.CAPITAL - 1
    bear_paths = [p for p in totals if p != "SM" and p != "SU"]
    bear = sum(weights[p] * totals[p] for p in bear_paths) / sum(weights[p] for p in bear_paths) / v1.CAPITAL - 1
    assert expected == pytest.approx(7.6805, abs=0.0001)
    assert bear == pytest.approx(0.3532, abs=0.0001)
    assert round(totals["SM"]) == 83_312
