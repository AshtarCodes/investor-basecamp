"""Price IREN call contracts sold early on a rally (June or November), or held to expiry, with the live schwab CLI.

Usage (from the repo root):
  python3 scenarios/iren/analysis/early_sale_grid.py snapshot   # live quotes, Mark-implied IV, delta
  python3 scenarios/iren/analysis/early_sale_grid.py run        # `option price --mode sell` and `--mode expiry` per contract x date x case
Standard library only. Every price is an online `pnpm schwab option price` call (nothing offline), throttled and cached
by construction_grid.cli, so a rerun only fills gaps.

Two programmes, both starting at today's spot S0:
  27: Jan 2028 options sold 2027-06-30 or 2027-11-30, or held to 2028-01-21; thesis year-end is 2027-12-31.
  28: Jan 2029 options sold 2028-06-30 or 2028-11-30, or held to 2029-01-19; thesis year-end is 2028-12-29.
The thesis gives year-end spots only. The spot on a sale date is one of two paths to the same case:
  interp: geometric interpolation by calendar days (S0 to the 2027 case value, then that to the 2028 case value);
  front:  the rally has already arrived, so the spot is the full year-end case value on the sale date.
Exit IV is flat at the Mark-implied IV (Rule 1) or shifted by the move from S0 (Rule 2; front is Rule 2 only).
Held to expiry, the spot at expiry is the year-end case value, and the value is intrinsic.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from construction_grid import cli, occ, rule2_vol

DATA = Path(__file__).resolve().parents[1] / "data"
QUOTES = DATA / "early-sale-quotes-2026-10-26.json"
EXITS = DATA / "early-sale-exit-values-2026-10-26.json"
START = date(2026, 10, 26)

THESIS = {"27": {"bear": 32, "base": 103, "bull": 230}, "28": {"bear": 46, "base": 164, "bull": 343}}
PROGRAMMES = {
    "27": {"expiry": "280121", "strikes": [15, 25, 40, 75, 100, 140], "start": START, "ye": date(2027, 12, 31),
           "dates": [date(2027, 6, 30), date(2027, 11, 30)]},
    "28": {"expiry": "290119", "strikes": [15, 25, 40, 60, 75, 90], "start": date(2027, 12, 31), "ye": date(2028, 12, 29),
           "dates": [date(2028, 6, 30), date(2028, 11, 30)]},
}


def sale_spot(prog: str, case: str, d: date, path: str, spot0: float) -> float:
    end = THESIS[prog][case]
    if path == "front":
        return float(end)
    p = PROGRAMMES[prog]
    begin = spot0 if prog == "27" else THESIS["27"][case]
    f = (d - p["start"]).days / (p["ye"] - p["start"]).days
    return round(begin * (end / begin) ** f, 2)


def snapshot() -> None:
    jobs = [(p["expiry"], k) for p in PROGRAMMES.values() for k in p["strikes"]]

    def one(job):
        e, k = job
        d = cli("--symbol", occ(e, k))
        return {
            "occ": occ(e, k), "expiry": e, "strike": k,
            "bid": d["schwab"]["bid"], "ask": d["schwab"]["ask"], "mark": d["schwab"]["mark"],
            "spot": d["inputs"]["spot"]["value"], "iv": d["inputs"]["vol"]["value"],
            "rate": d["inputs"]["rate"]["value"], "delta": d["results"]["theoretical"]["ours"]["greeks"]["delta"],
            "quoteTime": d["schwab"]["quoteTime"],
        }

    with ThreadPoolExecutor(3) as ex:
        rows = list(ex.map(one, jobs))
    spot = sum(r["spot"] for r in rows) / len(rows)
    QUOTES.write_text(json.dumps({"spotRef": round(spot, 2), "contracts": rows}, indent=1) + "\n")
    print(f"{len(rows)} contracts, spotRef {spot:.2f} -> {QUOTES.name}")


def run() -> None:
    q = json.loads(QUOTES.read_text())
    spot0 = q["spotRef"]
    cache = json.loads(EXITS.read_text()) if EXITS.exists() else {}
    jobs = []
    for prog, p in PROGRAMMES.items():
        for c in (c for c in q["contracts"] if c["expiry"] == p["expiry"]):
            for case in ("bear", "base", "bull"):
                key = f"{prog}|{c['occ']}|expiry|{case}"
                if key not in cache:
                    jobs.append(("expiry", key, c["occ"], None, THESIS[prog][case], None))
                for d in p["dates"]:
                    for path, rules in (("interp", ("flat", "rule2")), ("front", ("rule2",))):
                        s = sale_spot(prog, case, d, path, spot0)
                        for rule in rules:
                            vol = c["iv"] if rule == "flat" else rule2_vol(c["iv"], s / spot0 - 1)
                            key = f"{prog}|{c['occ']}|{d}|{case}|{path}|{rule}"
                            if key not in cache:
                                jobs.append(("sell", key, c["occ"], d, s, vol))
    print(f"{len(jobs)} calls to make")

    def one(job):
        mode, key, sym, d, s, vol = job
        if mode == "expiry":
            r = cli("--symbol", sym, "--mode", "expiry", "--expected-spot", str(s))
            return key, {"spot": s, "value": r["results"]["expiry"]["intrinsic"]}
        r = cli("--symbol", sym, "--mode", "sell", "--as-of", str(d), "--expected-spot", str(s), "--vol", f"{vol:.4f}")
        return key, {"spot": s, "vol": round(vol, 4), "value": r["results"]["sell"]["saleProceeds"]}

    with ThreadPoolExecutor(3) as ex:
        for i, (key, rec) in enumerate(ex.map(one, jobs), 1):
            cache[key] = rec
            if i % 25 == 0:
                EXITS.write_text(json.dumps(cache, indent=1) + "\n")
                print(f"  {i}/{len(jobs)}")
    EXITS.write_text(json.dumps(cache, indent=1) + "\n")
    print(f"{len(cache)} exit values -> {EXITS.name}")


if __name__ == "__main__":
    {"snapshot": snapshot, "run": run}[sys.argv[1] if len(sys.argv) > 1 else "snapshot"]()
