# External market data (when Schwab is not enough)

The app uses **Schwab Trader API** for positions, equity/ETF quotes, equity options, **`$VIX`**, **CME-style futures** where entitled (`/BZ`, `/BTC`, `/ZN`, etc.), and **computed ICE USDX spot** from six **FOREX** legs. Some **macro reference** series appear in thinkorswim but **do not return usable index quotes or history** on our API token. Those need a **documented third-party source** (or a Schwab entitlement change + retest).

This file is the checklist. Update it when Schwab coverage or product choices change.

## Summary table

| Instrument | TOS / intent | Schwab Trader API (our pulls) | External? | Preferred source |
| --- | --- | --- | --- | --- |
| **ICE U.S. Dollar Index (spot)** | **`$DXY`** ~100 scale | **Index symbol invalid**; **spot via 6 FX + formula OK** (`macro dxy`) | **Cross-check only** | Same Schwab token for spot; **ICE / Blocklens / Yahoo** for license or history |
| **ICE USDX history (daily)** | **`$DXY` chart** | **`$DXY` history empty**; **FX `pricehistory` empty** | **Yes** | **Yahoo `DX-Y.NYB`** (dev) or **ICE / Blocklens** (prod) — **not** six-leg Yahoo rebuild |
| **U.S. Dollar Index futures** | **`/DX`** | **`/quotes` invalid**; **`/pricehistory` empty** | **Yes** (until futures MD entitled) | **ICE / FinzData `DX`** (paid) or retest Schwab after entitlement |
| **Schwab FX (ICE basket legs)** | — | **`EUR/USD` … `USD/CHF`** quotes **`FOREX`/GFT** | **No** (for spot compute) | Use **`BASE/QUOTE`** only |
| **Bloomberg Galaxy Bitcoin Index** | **`$BTC`** | Quote **zeros**; chain **empty** | **Only if you need this index** | Not required if you use Schwab **`/BTC`** future or **`IBIT`/`BITO`** |
| **Dow Jones FXCM Dollar Index** | — | **`$USDOLLAR`** quote ~12808; **history empty** | **No** (wrong index) | — |
| **Dynex Capital** | — | Ticker **`DX`** is **equity** | **Never** for DXY | — |
| **Equities & ETFs** | AAPL, UUP, … | **OK** quotes + history | **No** | — |
| **Equity & ETF options** | OCC symbols | **OK** | **No** | — |
| **`$VIX` + VIX options** | Vol index | **OK** | **No** | — |
| **Commodity / crypto / rates futures** | `/BZ`, `/BTC`, `/ZN` | **OK** on **resolved** contract (e.g. `/BZZ26`) | **No** (for our use) | — |
| **SPX / XSP index options** | Portfolio risk | **Not verified** | **TBD** | Retest Schwab `$SPX` / chains when needed |

## ICE DXY — sources and methods

Consumers must read **`method`** and **`source`** on macro output:

| `method` | `source` | Meaning |
| --- | --- | --- |
| **`ice-formula`** | **`schwab-fx`** | USDX computed from six Schwab **`mark`**s (production spot path on Schwab token) |
| **`index-series`** (planned) | **`yahoo`** | Daily bars from **`DX-Y.NYB`** chart API |
| **`index-series`** | **`ice`** / **`blocklens`** | Licensed feed when keyed |

### Spot: Schwab FX + ICE formula (v1)

- **CLI:** `pnpm schwab macro dxy`
- **Request:** one quotes call — `EUR/USD`, `USD/JPY`, `GBP/USD`, `USD/CAD`, **`USD/SEK`**, `USD/CHF` (URL-encode **`/`**).
- **Formula:** `USDX = 50.14348112 × EURUSD^−0.576 × USDJPY^0.136 × GBPUSD^−0.119 × USDCAD^0.091 × USDSEK^0.042 × USDCHF^0.036`
- **Gates:** all six legs; **`mark` > 0** on each; leg **`quoteTime`** spread ≤ **60 s**; **`marketOpen`** false during FX weekend close (Fri 17:00 – Sun 17:00 NY) — frozen marks are valid.
- **Cross-check:** Yahoo **`DX-Y.NYB`** within **≤ 2 bp** when fetched in the **same minute** (smoke **0.64 bp** on 2026-10-23). “Match ICE exactly” is not testable without ICE’s fixing feed; this cross-check is the regression bar.
- **Details:** [observations.md](./observations.md) (FX encoding, history limits); [DXY_FROM_FX_VERDICT.md](../../tools/schwab/prototype/DXY_FROM_FX_VERDICT.md).

### History (daily)

| Approach | Works? | Notes |
| --- | --- | --- |
| Schwab **`$DXY` / `/DX` history** | **No** | Empty candles |
| Schwab **FX `pricehistory`** → formula | **No** | `EUR/USD` probe **empty**; history likely equities/ETFs only |
| **Yahoo `DX-Y.NYB` chart** | **Yes (dev/reference)** | Use **index series**; drop null bars; handle `chart.error`; partial last bar |
| **Six Yahoo FX dailies → formula** | **Avoid** | Mixed close conventions; won’t match ICE dailies |
| **`UUP` on Schwab** | **Yes** | **ETF proxy** history, not ICE level |

### Authoritative (production-grade)

- **ICE Data Indices / ICE Data API** — official **DXY**. Commercial; same family as TOS **`$DXY`**. [ICE currency indices catalog](https://developer.ice.com/fixed-income-data-services/catalog/ice-data-indices-currency-indices).

### API aggregators (needs paid account/key)

- **Blocklens** — **`DX-Y.NYB`**, field `dxy`, daily via `GET /v1/macro/markets` ([docs](https://docs.blocklens.co/metrics/macro/macro-dxy)). **Free tier has no API access** — deprioritized until a paid key exists.
- Other paid macro/FX vendors (Polygon, Refinitiv, etc.) — evaluate when picking a single macro provider.

### Unofficial / dev-only (no key; fragile)

- **Yahoo Finance chart API** — **`DX-Y.NYB`**, spot and daily. Aligned with TOS (~**101.795** vs **101.796** on 2026-10-23). **Not licensed for production**; rate limits and breakage risk. Capture: `.local/schwab/captures/_dxy_yahoo.json` (gitignored).

```bash
curl -A 'Mozilla/5.0' 'https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1d&range=5d'
```

### Schwab ETF fallback (same trend, wrong level)

- **`UUP`** — full Schwab history; **`DXY ≈ k × UUP_mark`**, **`k ≈ 3.52`**. See [observations.md](./observations.md#dxy-proxy-interim-uup-invesco-db-us-dollar-bullish). Use when you need **ETF** history on Schwab only; prefer **`macro dxy`** for **spot ICE level** on the same token.

### Not ICE DXY

- **FRED `DTWEXBGS`** — trade-weighted broad dollar; **different** index.
- **`UUP` / `UDN` / `USDU`** — investable ETFs; **~0.82 daily return correlation** with ICE, not same level.
- **`/DX` futures** — different product from **cash USDX**; do not feed **`macro dxy`**.

## Recommended v1 policy

1. **Positions & marks for things you hold** → **Schwab only** (equities, options, entitled futures).
2. **ICE DXY macro reference (no trade)** → **Spot:** `pnpm schwab macro dxy` (**`ice-formula` / `schwab-fx`**). **History:** Yahoo **`DX-Y.NYB`** daily until **ICE or Blocklens** is keyed — **not** Schwab FX history, **not** six-leg Yahoo FX rebuild.
3. **Revisit Schwab** for **`$DXY` / `/DX`** after **index/futures market-data** entitlements change.
4. **New “TOS shows it but API empty” symbols** → add a row here before building sync logic.
5. **Macro commands** always emit **`method`** and **`source`**.

## Related

- Empirical Schwab behavior: [observations.md](./observations.md)
- Schwab dev CLI: [tools/schwab/README.md](../../tools/schwab/README.md)
