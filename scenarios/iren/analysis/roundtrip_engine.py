"""Run a Build on a Price Path, priced from a Quote Set: the v2 engine behind /prototype/roundtrip.

Standard library only. The pricer is passed in, so this module does no I/O: `roundtrip_run.py` prices through the pricing
engine's batch worker, and the v1 regression test prices from the 2026-10-26 CLI cache. Terms are GLOSSARY.md's: Build,
Sleeve, Leg, Price Path, Action, Quote Set.

Rules (.scratch/iren-roundtrip-chart/plan-v2-one-timeline-and-my-builds.md):
  path: starts at the Quote Set's spot on the day it was taken, geometric between its points, flat after the last one.
    Points dated on or before that day are skipped.
  actions: Sell X% sells X% of what is left in each option Sleeve, rounded half up to whole contracts; the money sits as
    cash at 0% ("sell_cash") or buys shares at that point's price ("sell_shares"). Shares are never sold by an Action.
  entry: ask for long Legs, bid for short ones. Shares take whatever the Sleeves don't use.
  expiry: a Sleeve still held is sold on the weekday before its expiry at model value, and the money buys shares that day.
  debt: on 2027-11-30, debt x max(0, wealth - budget) is paid from cash first, then option Sleeves (highest leverage
    first, whole contracts, any excess to cash), then shares. Leverage is delta x spot over entry cost, from the Quote Set.
  end: the later of the path's last point and the last expiry sale. Everything is in shares or cash by then.
"""

import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

DEBT_DATE = date(2027, 11, 30)


def _day(iso: str) -> date:
    return date.fromisoformat(iso[:10])


def spot_on(knots: list, d: date) -> float:
    """Geometric between knots, in cents, and flat after the last one (v1's roundtrip_grid.spot_on)."""
    for (d0, s0), (d1, s1) in zip(knots, knots[1:]):
        if d <= d1:
            return round(s0 * (s1 / s0) ** ((d - d0).days / (d1 - d0).days), 2)
    return knots[-1][1]


def quote_day(quotes: dict) -> date:
    """The New York date the Quote Set was taken: the path's start."""
    return datetime.fromisoformat(quotes["takenAt"]).astimezone(NY).date()


def sale_date(expiry: str) -> str:
    """The weekday before an expiry, when a Leg still held is sold. Exchange holidays are not modelled."""
    d = _day(expiry) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def leg_key(leg: dict) -> tuple:
    return (leg["expiry"], float(leg["strike"]), leg["kind"])


def quote_of(quotes: dict, leg: dict) -> dict | None:
    return next((q for q in quotes["contracts"] if leg_key(q) == leg_key(leg)), None)


def entry_cost(quotes: dict, sleeve: dict) -> float:
    """Per share of one contract: ask for long Legs, bid for short ones."""
    total = 0.0
    for leg in sleeve["legs"]:
        q = quote_of(quotes, leg)
        total += leg["side"] * (q["ask"] if leg["side"] > 0 else q["bid"])
    return total


def leg_label(leg: dict) -> str:
    """'Jan 2028 $40 call'."""
    month = _day(leg["expiry"]).strftime("%b %Y")
    return f"{month} ${float(leg['strike']):g} {'call' if leg['kind'] == 'C' else 'put'}"


def unpriceable(build: dict, quotes: dict) -> str | None:
    """Why this Build can't be run on this Quote Set, or None: a Leg expired or not listed, or a cost over budget."""
    start = quote_day(quotes)
    for sl in build["sleeves"]:
        for leg in sl["legs"]:
            if _day(sale_date(leg["expiry"])) <= start:
                return f"{leg_label(leg)} expired"
            q = quote_of(quotes, leg)
            if q is None:
                return f"{leg_label(leg)} is not listed"
            if q["bid"] is None or q["ask"] is None or q["mark"] is None:
                return f"{leg_label(leg)} has no bid or ask"
    over = sum(sl["contracts"] * entry_cost(quotes, sl) * 100 for sl in build["sleeves"]) - build["budget"]
    return f"over budget by ${over:,.0f}" if over > 0.005 else None


def leverage(quotes: dict, sleeve: dict) -> float:
    delta = sum(leg["side"] * (quote_of(quotes, leg)["delta"] or 0.0) for leg in sleeve["legs"])  # no delta: last for debt
    return delta * quotes["spot"] / entry_cost(quotes, sleeve)


def run(build: dict, path: dict, quotes: dict, debt: float, value, trace: bool = False) -> dict:
    """One Build on one Price Path. `value(leg, date, spot)` is a Leg's model value per share; `debt` is the share of the
    gain paid out on the debt date. With `trace`, it also records the holdings after each date's trades (which values
    every Leg still held on every date) and what each leg added to the end result."""
    start = quote_day(quotes)
    s0 = quotes["spot"]
    points = sorted((p for p in path["points"] if _day(p["date"]) > start), key=lambda p: p["date"])
    if not points:
        raise ValueError(f"path {path['id']} has no point after {start}")
    actions = {_day(p["date"]): p for p in points if p["action"] != "hold"}
    knots = [(start, s0), *((_day(p["date"]), float(p["price"])) for p in points)]
    sleeves = build["sleeves"]
    sold_on = {sl["id"]: _day(min(sale_date(leg["expiry"]) for leg in sl["legs"])) for sl in sleeves}
    end = max([knots[-1][0], *sold_on.values()])
    pays_debt = debt > 0 and start < DEBT_DATE <= end
    timeline = sorted({*(d for d, _ in knots[1:]), *sold_on.values(), end, *([DEBT_DATE] if pays_debt else [])})

    n = {sl["id"]: sl["contracts"] for sl in sleeves}
    unit_cost = {sl["id"]: entry_cost(quotes, sl) * 100 for sl in sleeves}
    shares = (build["budget"] - sum(n[i] * unit_cost[i] for i in n)) / s0
    cash, paid = 0.0, 0.0
    events = []
    realized = {i: 0.0 for i in n}  # proceeds of every contract sold, however the money was used
    stock_cost, stock_sold = shares * s0, 0.0  # what the shares cost, entry plus reinvested; what debt sold of them
    rec = {"dates": [], "spot": [], "legs": {k: [] for k in ("stock", *n, "cash", "debt", "total")}, "unit": {k: [] for k in ("stock", *n, "total")}}

    def record(d, s):
        rec["dates"].append(d.isoformat())
        rec["spot"].append(s)
        rec["legs"]["stock"].append(shares * s)
        rec["unit"]["stock"].append(s / s0 - 1)
        held = 0.0
        for sl in sleeves:
            i = sl["id"]
            per = unit_cost[i] if d == start else worth(sl, d, s) if n[i] else None
            rec["legs"][i].append(n[i] * per if per is not None else 0.0)
            rec["unit"][i].append(per / unit_cost[i] - 1 if per is not None and unit_cost[i] else None)
            held += n[i] * per if per is not None else 0.0
        total = shares * s + held + cash + paid
        rec["legs"]["cash"].append(cash)
        rec["legs"]["debt"].append(paid)
        rec["legs"]["total"].append(total)
        rec["unit"]["total"].append(total / build["budget"] - 1)

    def worth(sl, d, s):
        return 100 * sum(leg["side"] * value(leg, d, s) for leg in sl["legs"])

    if trace:
        record(start, s0)
    for d in timeline:
        s = spot_on(knots, d)
        if d in actions:
            act = actions[d]
            pct = int(act["sellPct"])
            sold, got = 0, 0.0
            for sl in sleeves:
                k = (n[sl["id"]] * pct + 50) // 100
                if k:
                    got += k * worth(sl, d, s)
                    realized[sl["id"]] += k * worth(sl, d, s)
                    sold += k
                    n[sl["id"]] -= k
            if act["action"] == "sell_cash":
                cash += got
            else:
                shares += got / s
                stock_cost += got
            events.append({"date": d.isoformat(), "type": "action", "action": act["action"], "pct": pct, "contracts": sold, "amount": got})
        if pays_debt and d == DEBT_DATE:
            wealth = cash + shares * s + sum(n[sl["id"]] * worth(sl, d, s) for sl in sleeves)
            need = debt * max(0.0, wealth - build["budget"])
            target = need
            take = min(cash, need)
            cash -= take
            need -= take
            for sl in sorted(sleeves, key=lambda x: -leverage(quotes, x)):
                unit = worth(sl, d, s)
                if need <= 1e-9 or unit <= 0 or not n[sl["id"]]:
                    continue
                k = min(n[sl["id"]], math.ceil(need / unit))
                pay = min(need, k * unit)
                need -= pay
                cash += k * unit - pay
                realized[sl["id"]] += k * unit
                n[sl["id"]] -= k
            if need > 1e-9:
                k = min(shares, need / s)
                shares -= k
                stock_sold += k * s
                need -= k * s
            paid = target - need
            if paid > 0:
                events.append({"date": d.isoformat(), "type": "debt", "pct": debt, "amount": paid})
        for sl in sleeves:
            if sold_on[sl["id"]] == d and n[sl["id"]]:
                got = n[sl["id"]] * worth(sl, d, s)
                shares += got / s
                stock_cost += got
                realized[sl["id"]] += got
                events.append({"date": d.isoformat(), "type": "expiry", "sleeve": sl["id"], "contracts": n[sl["id"]], "amount": got})
                n[sl["id"]] = 0
        if trace:
            record(d, s)
    wealth = cash + shares * spot_on(knots, end)
    out = {"total": wealth + paid, "wealth": wealth, "debt": paid, "end": end.isoformat(), "events": events}
    if trace:
        rec["contrib"] = {"stock": shares * spot_on(knots, end) + stock_sold - stock_cost, **{i: realized[i] - sl["contracts"] * unit_cost[i] for sl in sleeves for i in [sl["id"]]}}
        if abs(rec["legs"]["total"][-1] - out["total"]) > 0.5 or abs(sum(rec["contrib"].values()) - (out["total"] - build["budget"])) > 1.0:
            raise AssertionError(f"trace of {build['id']} on {path['id']} does not add up to its total")  # v1's to-the-dollar check
        out["trace"] = rec
    return out
