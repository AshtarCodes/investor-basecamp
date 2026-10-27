"""Run Builds on Price Paths from a live Quote Set: the JSON entry point the /prototype/roundtrip server calls.

Usage (from the repo root): python3 scenarios/iren/analysis/roundtrip_run.py < request.json > result.json
Request: {"quoteSet": {...}, "builds": [...], "paths": [...], "debts": [0, 0.1, 0.25, 0.5]}, shaped as roundtrip_engine.run
takes them. Result: {"runs": {"<build>|<path>|<debt>": run with trace}, "unpriceable": {"<build>": reason}}.

Every value comes from the pricing engine's batch worker (packages/pricing-engine, `pricing-worker`), in one worker session:
first a zero Shock per contract for its Mark-implied IV, then one Shock per (date, spot) the runs ask for, at Rule 2's exit
IV (iv-rules.md) applied to that IV. Values are on the Quote Set's own Marks, spot and rates. The database is never read.
"""

import json
import subprocess
import sys
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import roundtrip_engine as eng
from construction_grid import rule2_vol

ROOT = Path(__file__).resolve().parents[3]
NY = ZoneInfo("America/New_York")


def wanted(builds: list, paths: list, quotes: dict) -> set:
    """Every (leg key, date, spot) a traced run asks for. A dry run values everything at 0, which sells nothing for the debt,
    so it holds at least as much as a priced run and asks for a superset."""
    asks = set()

    def note(leg, d, s):
        asks.add((eng.leg_key(leg), d, s))
        return 0.0

    for b in builds:
        for p in paths:
            eng.run(b, p, quotes, 0.25, note, trace=True)
    return asks


class WorkerFailed(Exception):
    """The worker died or answered `internal`: worth one retry with a new worker (pricing-engine AGENTS.md)."""


class Worker:
    """One `pricing-worker` process, spoken to a line at a time."""

    def __init__(self):
        cmd = ["uv", "run", "--project", "packages/pricing-engine", "pricing-worker"]
        self.proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.ask_id = 0
        self._line()  # the ready line

    def _line(self) -> dict:
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise WorkerFailed("the pricing worker exited")
            if line.startswith("{"):
                return json.loads(line)

    def batch(self, contracts: list) -> list:
        self.ask_id += 1
        request = {"id": self.ask_id, "type": "batch", "iv_shift_mode": "absolute", "contracts": contracts}
        try:
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError as error:
            raise WorkerFailed("the pricing worker exited") from error
        answer = self._line()
        if not answer["ok"]:
            error = answer["error"]
            if error.get("code") == "internal":
                raise WorkerFailed(error.get("message", "internal"))
            raise SystemExit(f"pricing worker failed: {error}")
        return answer["result"]["contracts"]

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except (BrokenPipeError, subprocess.TimeoutExpired):
            self.proc.kill()


def sourced(value):
    return {"value": value, "from": "quote set"}


def price_all(asks: set, quotes: dict) -> dict:
    """(leg key, date, spot) -> value per share, from the batch worker."""
    by_leg = {}
    for key, d, s in sorted(asks):
        by_leg.setdefault(key, []).append((d, s))
    if not by_leg:
        return {}
    base = {}
    for key in by_leg:
        q = eng.quote_of(quotes, {"expiry": key[0], "strike": key[1], "kind": key[2]})
        base[key] = {
            "contract": {"root": quotes.get("symbol", "IREN"), "expiry": key[0], "strike": key[1], "right": "call" if key[2] == "C" else "put", "exercise": "american"},
            "valuation": q["quoteTime"], "spot": sourced(q["spot"]), "rate": sourced(q["rate"] / 100), "mark": sourced(q["mark"]),
        }
    try:
        priced = _session(base, by_leg, quotes)
    except WorkerFailed:
        priced = _session(base, by_leg, quotes)  # once more, with a new worker; a second failure is the request's
    out = {}
    for (key, items), answer in zip(by_leg.items(), priced):
        if not answer["ok"]:
            raise SystemExit(f"pricing worker failed for {key}: {answer['error']}")
        for (d, s), amount in zip(items, answer["prices"]):
            out[(key, d, s)] = amount
    return out


def _session(base: dict, by_leg: dict, quotes: dict) -> list:
    """One worker: a zero Shock per contract for its Mark-implied IV, then the wanted Shocks at Rule 2's exit IV."""
    worker = Worker()
    try:
        zero = {"spot_move": 0, "iv_shift": 0, "days_forward": 0}
        ivs = worker.batch([{"request": base[k], "shocks": [zero]} for k in by_leg])
        shocks = {}
        for (key, items), first in zip(by_leg.items(), ivs):
            if not first["ok"]:
                raise SystemExit(f"pricing worker failed for {key}: {first['error']}")
            iv = first["iv"]["value"]
            q = eng.quote_of(quotes, {"expiry": key[0], "strike": key[1], "kind": key[2]})
            qt = datetime.fromisoformat(q["quoteTime"])
            shocks[key] = []
            for d, s in items:
                shift = rule2_vol(iv * 100, s / quotes["spot"] - 1) / 100 - iv if iv is not None else 0.0
                at = datetime.combine(d, time(16, 0), NY)  # a date means 4 pm New York, as in the CLI
                shocks[key].append({"spot_move": s / q["spot"] - 1, "iv_shift": shift, "days_forward": max(0.0, (at - qt).total_seconds() / 86400)})
        return worker.batch([{"request": base[k], "shocks": shocks[k]} for k in by_leg])
    finally:
        worker.close()


def rounded(xs, nd):
    return [None if x is None else round(x, nd) for x in xs]


def slim(r: dict) -> dict:
    t = r["trace"]
    return {
        "total": round(r["total"]), "wealth": round(r["wealth"]), "debt": round(r["debt"]), "end": r["end"],
        "events": [{**e, "amount": round(e["amount"])} for e in r["events"]],
        "dates": t["dates"], "spot": t["spot"],
        "legs": {k: rounded(v, 0) for k, v in t["legs"].items()}, "unit": {k: rounded(v, 3) for k, v in t["unit"].items()},
        "contrib": {k: round(v) for k, v in t["contrib"].items()},
    }


def main():
    req = json.load(sys.stdin)
    quotes, paths = req["quoteSet"], req["paths"]
    unpriceable = {b["id"]: why for b in req["builds"] if (why := eng.unpriceable(b, quotes))}
    builds = [b for b in req["builds"] if b["id"] not in unpriceable]
    start = eng.quote_day(quotes)
    paths = [p for p in paths if any(date.fromisoformat(pt["date"][:10]) > start for pt in p["points"])]
    values = price_all(wanted(builds, paths, quotes), quotes)

    def value(leg, d, s):
        return values[(eng.leg_key(leg), d, s)]

    runs = {}
    for b in builds:
        for p in paths:
            for f in req["debts"]:
                runs[f"{b['id']}|{p['id']}|{f:.2f}"] = slim(eng.run(b, p, quotes, f, value, trace=True))
    json.dump({"runs": runs, "unpriceable": unpriceable}, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
