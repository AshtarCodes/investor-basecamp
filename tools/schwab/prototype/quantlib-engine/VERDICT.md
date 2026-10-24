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
