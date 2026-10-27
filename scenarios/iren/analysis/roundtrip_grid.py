"""Price calls and puts along straight and round-trip IREN paths with the live schwab CLI, saving every raw response.

Usage (from the repo root):
  python3 scenarios/iren/analysis/roundtrip_grid.py snapshot   # live quotes for the calls and puts used, raw responses kept
  python3 scenarios/iren/analysis/roundtrip_grid.py run        # `option price --mode sell|expiry` per contract x date x spot x IV
Standard library only. Every price is an online `pnpm schwab option price` call (nothing offline), throttled and cached by
construction_grid.cli. Every raw JSON response is appended to data/raw/roundtrip-cli-responses-2026-10-26.jsonl.gz.

Paths (spot by calendar date, geometric between knots; knots are (date, spot)):
  SB, SM, SU: straight to the 2027 bear, base, bull value by 2027-12-31, then to the 2028 value by 2028-12-29.
  RT<level><J|N>: up to the level ($85 or $103) on 2027-06-30 (J) or 2027-11-30 (N), then down to the 2027 bear by
  2027-12-31, then to the 2028 bear by 2028-12-29.
Exit IV for calls is Rule 2 (iv-rules.md). Puts are priced under three IV assumptions: rule2, flat, and up (flat + 10 points).
"""

import gzip
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import construction_grid as cg
from construction_grid import cli, rule2_vol

DATA = Path(__file__).resolve().parents[1] / "data"
QUOTES = DATA / "roundtrip-quotes-2026-10-26.json"
EXITS = DATA / "roundtrip-exit-values-2026-10-26.json"
RAW_TMP = DATA / "raw" / "roundtrip-cli-responses-2026-10-26.jsonl"
RAW_GZ = DATA / "raw" / "roundtrip-cli-responses-2026-10-26.jsonl.gz"

START, J27, N27, YE27 = date(2026, 10, 26), date(2027, 6, 30), date(2027, 11, 30), date(2027, 12, 31)
J28, N28, YE28 = date(2028, 6, 30), date(2028, 11, 30), date(2028, 12, 29)
DATES27, DATES28 = [J27, N27], [J28, N28]
CASE27 = {"bear": 32, "base": 103, "bull": 230}
CASE28 = {"bear": 46, "base": 164, "bull": 343}
LEVELS = (85, 103)
IV_UP = 10.0

CALLS = {"280121": [15, 25, 40, 75, 100, 140], "290119": [15, 25, 30, 35, 40, 60, 75, 90]}  # 30, 35 added for the 30/75, 35/75, 40/75 spreads
PUTS = {"280121": [70, 85, 100], "290119": [70, 85, 90]}


def occ(expiry: str, strike: float, kind: str = "C") -> str:
    return f"IREN  {expiry}{kind}{int(strike * 1000):08d}"


def paths(s0: float) -> dict:
    out = {
        "SB": [(START, s0), (YE27, CASE27["bear"]), (YE28, CASE28["bear"])],
        "SM": [(START, s0), (YE27, CASE27["base"]), (YE28, CASE28["base"])],
        "SU": [(START, s0), (YE27, CASE27["bull"]), (YE28, CASE28["bull"])],
    }
    for lv in LEVELS:
        for tag, d in (("J", J27), ("N", N27)):
            out[f"RT{lv}{tag}"] = [(START, s0), (d, lv), (YE27, CASE27["bear"]), (YE28, CASE28["bear"])]
    return out


def spot_on(knots: list, d: date) -> float:
    for (d0, s0), (d1, s1) in zip(knots, knots[1:]):
        if d <= d1:
            return round(s0 * (s1 / s0) ** ((d - d0).days / (d1 - d0).days), 2)
    return knots[-1][1]


def vol_for(rule: str, iv0: float, s: float, s0: float) -> float:
    if rule == "flat":
        return iv0
    if rule == "up":
        return iv0 + IV_UP
    return rule2_vol(iv0, s / s0 - 1)


_raw_lock = threading.Lock()


def call_cli(key: str, *args: str) -> dict:
    d = cli(*args)
    with _raw_lock, open(RAW_TMP, "a") as f:
        f.write(json.dumps({"key": key, "args": list(args), "response": d}) + "\n")
    return d


def snapshot() -> None:
    """Quote every contract. If a quotes file exists, quote only the contracts missing from it and keep the rest (and spotRef)."""
    old = json.loads(QUOTES.read_text()) if QUOTES.exists() else None
    have = {c["occ"] for c in old["contracts"]} if old else set()
    if not old:
        RAW_TMP.unlink(missing_ok=True)
    jobs = [(e, k, "C") for e, ks in CALLS.items() for k in ks] + [(e, k, "P") for e, ks in PUTS.items() for k in ks]
    jobs = [j for j in jobs if occ(*j) not in have]

    def one(job):
        e, k, kind = job
        d = call_cli(f"snapshot|{occ(e, k, kind)}", "--symbol", occ(e, k, kind))
        return {
            "occ": occ(e, k, kind), "expiry": e, "strike": k, "kind": kind,
            "bid": d["schwab"]["bid"], "ask": d["schwab"]["ask"], "mark": d["schwab"]["mark"],
            "spot": d["inputs"]["spot"]["value"], "iv": d["inputs"]["vol"]["value"],
            "rate": d["inputs"]["rate"]["value"], "delta": d["results"]["theoretical"]["ours"]["greeks"]["delta"],
            "quoteTime": d["schwab"]["quoteTime"],
        }

    with ThreadPoolExecutor(3) as ex:
        rows = list(ex.map(one, jobs))
    if old:
        rows = old["contracts"] + rows
        spot = old["spotRef"]
    else:
        spot = sum(r["spot"] for r in rows) / len(rows)
    QUOTES.write_text(json.dumps({"spotRef": round(spot, 2), "contracts": rows}, indent=1) + "\n")
    print(f"{len(jobs)} contracts quoted ({len(rows)} in file), spotRef {spot:.2f} -> {QUOTES.name}")


def needs(q: dict) -> dict:
    """key -> (mode, occ, date, spot, rule, iv0). Everything the report may ask for."""
    s0 = q["spotRef"]
    iv = {c["occ"]: c["iv"] for c in q["contracts"]}
    ps = paths(s0)
    need = {}

    def add(mode, o, d, s, rule):
        key = f"{mode}|{o}|{d}|{s:.2f}|{rule}"
        need[key] = (mode, o, d, s, rule, iv[o])

    calls = {e: [occ(e, k) for k in ks] for e, ks in CALLS.items()}
    puts = {e: [occ(e, k, "P") for k in ks] for e, ks in PUTS.items()}
    for name, kn in ps.items():
        for d in DATES27:
            for e in calls:
                for o in calls[e]:
                    add("sell", o, d, spot_on(kn, d), "rule2")
        for o in calls["280121"]:
            add("sell", o, YE27, spot_on(kn, YE27), "rule2")
        for d in DATES28:
            for o in calls["290119"]:
                add("sell", o, d, spot_on(kn, d), "rule2")
    for d in DATES28:  # "already there" spot for the 200-point test
        for o in calls["290119"]:
            add("sell", o, d, float(CASE28["base"]), "rule2")
    for case, s in CASE27.items():
        for o in calls["280121"]:
            add("expiry", o, date(2028, 1, 21), float(s), "-")
    for case, s in CASE28.items():
        for o in calls["290119"]:
            add("expiry", o, date(2029, 1, 19), float(s), "-")
    # puts: bought where a trigger fires, valued again later on the same path
    for name, kn in ps.items():
        for lv in LEVELS:
            fire = next((d for d in DATES27 if spot_on(kn, d) >= lv), None)
            if fire is None:
                continue
            for rule in ("rule2", "flat", "up"):
                for e in puts:
                    for o in puts[e]:
                        add("sell", o, fire, spot_on(kn, fire), rule)
                        if fire == J27:
                            add("sell", o, N27, spot_on(kn, N27), rule)
                for o in puts["280121"]:
                    add("sell", o, YE27, spot_on(kn, YE27), rule)
                for d in DATES28:
                    for o in puts["290119"]:
                        add("sell", o, d, spot_on(kn, d), rule)
    return need


def run() -> None:
    q = json.loads(QUOTES.read_text())
    s0 = q["spotRef"]
    cache = json.loads(EXITS.read_text()) if EXITS.exists() else {}
    todo = [(k, v) for k, v in needs(q).items() if k not in cache]
    print(f"{len(needs(q))} valuations needed, {len(todo)} to make")

    def one(item):
        key, (mode, o, d, s, rule, iv0) = item
        if mode == "expiry":
            r = call_cli(key, "--symbol", o, "--mode", "expiry", "--expected-spot", str(s))
            return key, {"value": r["results"]["expiry"]["intrinsic"]}
        vol = vol_for(rule, iv0, s, s0)
        r = call_cli(key, "--symbol", o, "--mode", "sell", "--as-of", str(d), "--expected-spot", str(s), "--vol", f"{vol:.4f}")
        return key, {"vol": round(vol, 4), "value": r["results"]["sell"]["saleProceeds"]}

    with ThreadPoolExecutor(3) as ex:
        for i, (key, rec) in enumerate(ex.map(one, todo), 1):
            cache[key] = rec
            if i % 25 == 0:
                EXITS.write_text(json.dumps(cache, indent=1) + "\n")
                print(f"  {i}/{len(todo)}")
    EXITS.write_text(json.dumps(cache, indent=1) + "\n")
    with open(RAW_TMP, "rb") as src, gzip.open(RAW_GZ, "wb") as dst:
        dst.write(src.read())
    print(f"{len(cache)} valuations -> {EXITS.name}; raw responses -> {RAW_GZ.name}")


if __name__ == "__main__":
    {"snapshot": snapshot, "run": run}[sys.argv[1] if len(sys.argv) > 1 else "snapshot"]()
