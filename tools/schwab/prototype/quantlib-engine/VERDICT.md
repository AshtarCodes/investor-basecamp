# QuantLib as the pricing engine: verdict

Question: can QuantLib (via `uv`) be the pricing engine ADR 0001 describes, run as a Python process the server calls?

Verdict (2026-10-24): **go**, with intraday time and the worker protocol still open. Recorded in `docs/adr/0007-pricing-engine-is-a-python-worker.md`.

Run: `cd tools/schwab/prototype/quantlib-engine && uv run python spike.py`. Throwaway code; no tests.

| Check | Result |
| --- | --- |
| Install / import | `uv add` 1.3 s; import ~1 s cold, 0.05 s warm (QuantLib 1.44) |
| Haug BSM oracle (60/65, T=0.25, r=8%, σ=30%) | closed form 2.1334; QuantLib analytic equals closed form at the same T (whole-day T=91/365 gives 2.1276) |
| American call, no dividends (IREN 55C, S=25.37, σ=103%) | FD 0.4346 vs BSM 0.4347 |
| American put, two $0.80 cash dividends (S=100, K=105, σ=30%) | FD cash-drop 10.9854 (200x400), 10.9861 (800x1600); no dividends 10.14 |
| Leisen-Reimer on spot minus PV(divs) | n=101 10.960, n=201 11.018 (about 3 cents either side of FD) |
| Mark-implied IV (brentq on FD) | 11-19 ms per solve |
| Greeks | engine delta/gamma/theta match bump-and-reprice; vega by bump; rho untested |
| 50 positions x 100 Shocks (5,000 reprices) | 2.17 s at FD 100x200; ~0.8 s at 50x100 (same accuracy, 0.16 ms/price); 0.30 s on a 14-process fork pool |
| 50 base IV solves | 0.26 s |

Not tested: intraday time to the settlement instant (QuantLib dates are whole days), JSON round-trip through a persistent worker, European index options on a parity forward, VIX Black-76, Shocks that cross a dividend date.

## Follow-up: exact minutes to the settlement instant (`spike_intraday.py`)

Verdict (2026-10-24): **pass**. QuantLib dates are whole days, so the engine uses a virtual clock. It maps true time `[0, T]` onto `N` whole days (N = 3650), then rescales `σ' = σ√(T/T_ql)`, `r' = r·T/T_ql` and each dividend time by `N/T`. That leaves σ²T, rT and r/σ² unchanged.

| Check | Result |
| --- | --- |
| European, T from 3.5 hours to 2 years, calls and puts | worst error vs closed-form BSM at exact T: 2.9e-14 |
| American, no dividends, T of 3.5 hours, 1.5 days, 30 days, vs 4000-step CRR at exact T | FD 400x800 within 0.04 cent; FD 100x200 within 0.1 cent (grid error, not time error) |
| American put with two cash dividends, N of 730, 3650 and 36500 | 10.44151, 10.44167, 10.44172: stable to 0.02 cent |
| 0-DTE put with an ex-date inside the last day, same three N | 1.63411 each |
| Cost, FD 100x200 | 0.48 ms/price at N=3650, 0.58 ms at N=36500 (includes object build) |

Dividend ex-times round to the nearest virtual day (about 24 seconds at N=3650 for a one-day option), which is far inside any quote precision.
