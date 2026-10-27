"""Price IREN call contracts at the thesis cases and at a stress grid, using the live schwab CLI.

Usage (from the repo root):
  python3 scenarios/iren/analysis/construction_grid.py snapshot   # live quotes, Mark-implied IV, delta
  python3 scenarios/iren/analysis/construction_grid.py run        # one `option price --mode sell` per contract x spot x IV rule
Standard library only. Every price comes from `pnpm schwab option price` online; nothing is run offline.
Calls are throttled (about 80 a minute) to stay under Schwab's rate limit, and cached, so a rerun only fills gaps.

Exit dates are the thesis year-ends (2027-12-31 and 2028-12-29). Exit IV is either flat at the contract's
Mark-implied IV (iv-rules.md Rule 1) or shifted by the spot move (Rule 2), held between 60% and 130%.
"""

import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(__file__).resolve().parents[1] / "data"
QUOTES = DATA / "leap-quotes-2026-10-26.json"
EXITS = DATA / "leap-exit-values-2026-10-26.json"

# (expiry code, strikes). Jan 2028 only reaches the 2027 year-end; Jan 2029 reaches both.
CONTRACTS = {
    "280121": [25, 40, 75, 100],
    "290119": [15, 25, 40, 60, 75, 90],
}
HORIZONS = {
    "2027": {"date": "2027-12-31", "expiries": ["280121", "290119"], "thesis": {"bear": 32, "base": 103, "bull": 230}},
    "2028": {"date": "2028-12-29", "expiries": ["290119"], "thesis": {"bear": 46, "base": 164, "bull": 343}},
}
STRESS_MOVES = [-0.50, -0.30, 0.0, 0.50]  # Rule 4 points that bear on the downside, flat, and a mid rally

# iv-rules.md Rule 2: (spot move, vol points added), linear in between, held at the ends.
SHIFTS = [(-0.40, 15), (-0.20, 8), (0.0, 0), (0.20, -5), (0.50, -10), (1.00, -15)]
IV_FLOOR, IV_CAP = 60.0, 130.0


def rule2_shift(move: float) -> float:
    if move <= SHIFTS[0][0]:
        return SHIFTS[0][1]
    for (x0, y0), (x1, y1) in zip(SHIFTS, SHIFTS[1:]):
        if move <= x1:
            return y0 + (y1 - y0) * (move - x0) / (x1 - x0)
    return SHIFTS[-1][1]


def rule2_vol(iv0: float, move: float) -> float:
    return min(IV_CAP, max(IV_FLOOR, iv0 + rule2_shift(move)))


_gate = threading.Lock()
_last = [0.0]


def cli(*args: str) -> dict:
    with _gate:  # one launch every 0.75s across all workers
        wait = _last[0] + 0.75 - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
    for attempt in range(3):
        out = subprocess.run(["pnpm", "schwab", "option", "price", *args], cwd=ROOT, capture_output=True, text=True)
        text = out.stdout[out.stdout.find("{") :] if "{" in out.stdout else ""
        if out.returncode == 0 and text:
            return json.loads(text)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"cli failed: {args}\n{out.stdout[-300:]}\n{out.stderr[-300:]}")


def occ(expiry: str, strike: float) -> str:
    return f"IREN  {expiry}C{int(strike * 1000):08d}"


def snapshot() -> None:
    jobs = [(e, k) for e, ks in CONTRACTS.items() for k in ks]

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
    spot_ref = q["spotRef"]
    cache = json.loads(EXITS.read_text()) if EXITS.exists() else {}
    jobs = []
    for h, hz in HORIZONS.items():
        spots = {f"{n}": s for n, s in hz["thesis"].items()}
        spots.update({f"{m:+.0%}": round(spot_ref * (1 + m), 2) for m in STRESS_MOVES})
        for c in q["contracts"]:
            if c["expiry"] not in hz["expiries"]:
                continue
            for label, s in spots.items():
                move = s / spot_ref - 1
                for rule, vol in (("flat", c["iv"]), ("rule2", rule2_vol(c["iv"], move))):
                    key = f"{h}|{c['occ']}|{label}|{rule}"
                    if key not in cache:
                        jobs.append((key, c["occ"], hz["date"], s, vol))
    print(f"{len(jobs)} calls to make")

    def one(job):
        key, sym, date, s, vol = job
        d = cli("--symbol", sym, "--mode", "sell", "--as-of", date, "--expected-spot", str(s), "--vol", f"{vol:.4f}")
        return key, {"spot": s, "vol": round(vol, 4), "value": d["results"]["sell"]["saleProceeds"]}

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
