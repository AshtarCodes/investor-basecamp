# PROTOTYPE verdict: ICE DXY from Schwab FX quotes

**Question:** Can we compute ICE USDX from six FX pairs, and does Schwab return those quotes (especially USD/SEK)?

**Date:** 2026-10-23 (live probes via `pnpm schwab get`)

## Schwab forex symbol format

| Encoding tried | Example | Result |
| --- | --- | --- |
| **`BASE/QUOTE`** (URL: `%2F`) | `EUR%2FUSD`, `USD%2FSEK` | **Works** — `assetMainType: FOREX`, GFT spot, `mark` / bid / ask |
| Concatenated | `EURUSD`, `USDJPY` | **`invalidSymbols`** |
| Leading slash + concat | `/EURUSD` | **`invalidSymbols`** |
| `$` prefix | `$EURUSD` | **`invalidSymbols`** |

**Working request (all six in one call):**

```text
GET /marketdata/v1/quotes?symbols=EUR%2FUSD,USD%2FJPY,GBP%2FUSD,USD%2FCAD,USD%2FSEK,USD%2FCHF
```

**USD/SEK:** quotes successfully (`USD/SEK`, mark ~9.94 in session pull). `isTradable: false` on reference (spot reference, not a stock).

## FX price history probe (step 1)

```text
GET /marketdata/v1/pricehistory?symbol=EUR%2FUSD&periodType=month&period=1&frequencyType=daily&frequency=1
```

**Result:** `{"symbol":"EUR/USD","empty":true,"candles":[]}` — **no bars** (consistent with schwab-py docs: history for equities/ETFs only).

**History branch (v1+):** daily USDX history must **`source: yahoo`**, symbol **`DX-Y.NYB`** via chart API — **not** six-leg Yahoo FX rebuild (mixed close conventions). Spot level remains **`method: ice-formula`**, **`source: schwab-fx`** via `pnpm schwab macro dxy`.

## Sample Schwab stdout (truncated)

```json
{"EUR/USD":{"assetMainType":"FOREX","symbol":"EUR/USD","quote":{"mark":1.119445,...}}, ...}
{"USD/SEK":{"assetMainType":"FOREX","symbol":"USD/SEK","quote":{"mark":9.94052,...}}, ...}
```

Failed:

```json
{"errors":{"invalidSymbols":["EURUSD"]}}
```

## Computed USDX vs reference

ICE formula (same as TOS):

`USDX = 50.14348112 × EURUSD^−0.576 × USDJPY^0.136 × GBPUSD^−0.119 × USDCAD^0.091 × USDSEK^0.042 × USDCHF^0.036`

### Early prototype snapshots (different minutes)

| Metric | Value |
| --- | --- |
| **Computed USDX (Schwab marks)** | **101.7976** |
| **Yahoo `DX-Y.NYB`** | **101.796** |
| **Delta** | **+0.0016** (~**0.16 bp**) |

These show the formula and symbol map are not broken; they are not a validation harness.

### Smoke: `pnpm schwab macro dxy` vs Yahoo (same minute, ≤ 2 bp)

| Field | Value |
| --- | --- |
| **Schwab `value`** | **101.8005** |
| **Schwab `fetchedAt`** | **2026-10-23T19:23:15.606466+00:00** |
| **Schwab `asOf` (oldest leg)** | **2026-10-23T19:23:15.750000+00:00** |
| **Yahoo `DX-Y.NYB`** | **101.794** |
| **Yahoo fetched** | **2026-10-23T19:23:15.511667+00:00** |
| **Gap** | **0.64 bp** |
| **`legSpreadSec`** | **0.101** |
| **Tolerance** | **≤ 2 bp** — **pass** |

Criterion for regression: **within 2 bp of `DX-Y.NYB` when both are fetched in the same minute**, not “match ICE exactly” (ICE fixing feed unknown).

## CLI v1

```bash
pnpm schwab macro dxy
```

Output includes **`method`**: `ice-formula`, **`source`**: `schwab-fx`, all six legs, **`legSpreadSec`**, **`marketOpen`** (false during FX weekend close Fri 17:00 – Sun 17:00 America/New_York).

Logic: `schwab_cli/usdx.py` (tests offline in `tests/test_usdx.py`). Prototype script is a thin wrapper only.

## Recommendation

| Approach | Viable? | Notes |
| --- | --- | --- |
| **Schwab `$DXY` / `/DX`** | **No** (today) | Still invalid/empty per [observations.md](../../../docs/schwab/observations.md) |
| **Compute from Schwab FX (spot)** | **Yes** | Single quotes call, all six legs including **USD/SEK**; **`mark`** on every leg |
| **Yahoo `DX-Y.NYB` (spot check / history)** | **Yes (dev / reference)** | Cross-check spot; **history when Schwab FX history empty** |
| **UUP × k** | Interim | Correlated level proxy, not ICE formula |

Do not rely on concat tickers (`EURUSD`). **`/DX` futures** is a different series from the cash index — keep out of `macro dxy`.
