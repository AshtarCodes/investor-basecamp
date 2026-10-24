# Schwab API observations

Empirical notes from live captures on 2026-10-23 (extended same day: futures, **`$DXY`**, Schwab **FX** legs, **`pnpm schwab macro dxy`**). Captures live under `.local/schwab/captures/` (gitignored). Placeholders below avoid real balances and quantities in git.

**DXY learnings (index):** TOS **`$DXY`** ≠ Trader API index symbol; **spot** ICE level **works** via six **`EUR/USD`-style** quotes + ICE formula; **history** does **not** (index, `/DX`, or FX `pricehistory` empty). Policy and sources: **[external-market-data.md](./external-market-data.md)**.

Primary capture set: `20261023T140603Z_*` through `20261023T140605Z_*` (IREN equity + `IREN  261023P00022000` short put).

## Short option position (`averagePrice`, quantity, total cost)

**Capture:** `20261023T140603Z_accounts-positions.json` (margin account with the short put).

| Field | Path (typical) | Observation |
| --- | --- | --- |
| Short size | `positions[].shortQuantity` | `10.0` contracts; `longQuantity` `0.0`; `quantity` absent/`null`. |
| Average premium | `positions[].averagePrice` | `0.26337` on the short leg (matches `taxLotAverageShortPrice`). |
| Rounded avg | `positions[].averageShortPrice` | `0.27` (rounded display vs tax lot). |
| Market value | `positions[].marketValue` | `-10.0` (negative while short; reflects mark, not full notional). |
| Multiplier | quote `reference.multiplier` | `100.0` (standard equity options). |

**Signed total cost (engine rule of thumb):** treat `averagePrice` as **premium per share of underlying** (not per contract). For shorts, cost basis is a **credit**:  
`-shortQuantity × averagePrice × multiplier` → `-10 × 0.26337 × 100 ≈ -$263.37` credit. Use `taxLotAverageShortPrice` when present for lot-level cost.

## Balances and Net Liquidation Value

**Captures:** `20261023T140603Z_accounts-positions.json`; **`20261024T002828Z_accounts-positions.json`** (re-pull).

| Account kind | `securitiesAccount.type` | NLV field |
| --- | --- | --- |
| All **three** linked accounts (2026-10-23 and 2026-10-24) | **`MARGIN` only** | **`currentBalances.liquidationValue`** |

**Cash / IRA:** No `CASH` or `IRA` `securitiesAccount.type` in either pull. If you add those account types later, re-run `capture` or `get /trader/v1/accounts?fields=positions` and confirm NLV on the same path (expect `liquidationValue` on `currentBalances`).

**Net liquidation:** use `securitiesAccount.currentBalances.liquidationValue` (matches `aggregatedBalance.currentLiquidationValue` on the same account object). Also present on `initialBalances.liquidationValue` / `projectedBalances` but **current** is the live NLV for sync.

Other useful balance paths: `currentBalances.equity`, `longOptionMarketValue`, `shortOptionMarketValue` (negative when short options), `buyingPower`, `maintenanceRequirement`, `cashBalance` (small cash sleeve inside margin accounts, e.g. **87.59** on one account — not a separate cash account type).

## Option symbol format

**Captures:** positions + `20261023T140603Z_option-quote.json` + chain.

| Item | Value |
| --- | --- |
| API symbol | `IREN  261023P00022000` (root, **two spaces**, OCC date/strike encoding) |
| Uniform symbol | Same string on `instrument.uniformSymbol` |
| Description | `IREN LTD 10/23/2026 $22 Put` |
| Underlying | `instrument.underlyingSymbol` → `IREN` |
| Settlement | quote `reference.settlementType` → `P` (physical); `exerciseType` → `A` (American) |
| Index roots (SPX/XSP) | **No index options in positions**; chain probes below. |

### Index options (SPX / XSP) — chain probe, not held

**Positions:** No SPX, SPXW, or XSP option lines in accounts pulls (2026-10-23 / 2026-10-24).

**API chain (live GET, 2026-10-24):**

| Underlying param | Chain status | Sample OCC | Settlement / exercise |
| --- | --- | --- | --- |
| **`$SPX`** | `SUCCESS`, `assetMainType: INDEX` | **`SPXW  261023C07625000`** (weekly root **SPXW**, **two spaces**) | From chain row sample: index AM-style deliverable `$SPX`; check `settlementType` / `exerciseType` per row in capture |
| **`$XSP`** | `SUCCESS` | **`XSP   261023P00763000`** (**three spaces** after `XSP`) | **`settlementType: P`**, **`exerciseType: E`** (European) on sample put |

Use **`$SPX`** / **`$XSP`** (URL **`%24SPX`**) on `/chains`, not bare `SPX`. OCC strings must come from chain output (spacing differs: **SPXW** two spaces, **XSP** three).

## Asset types and pricing gaps

**Capture:** accounts-positions.

| `instrument.assetType` | Seen | Notes |
| --- | --- | --- |
| `EQUITY` | Yes | Includes NYSE/NASDAQ and some OTC tickers (e.g. `FLTCF`, `KRKNF`). |
| `OPTION` | Yes | Vanilla equity options; `type` `VANILLA`, `putCall` `CALL`/`PUT`. |

v1 quotes were not attempted here for every exotic line; OTC / low-priced names may need separate quote checks before assuming sync can mark them.

## IV and greeks (quote vs chain vs TOS)

**Captures:** `20261023T140603Z_option-quote.json`, `20261023T140605Z_option-chain.json`.

| Source | `volatility` | Notes |
| --- | --- | --- |
| `/quotes` on the contract | ~`284.66` | Same order of magnitude as chain strike row (~`287.06` on the 22 put). |
| Chain row for 22 put | ~`287.06` | Per-contract `volatility` on the strike. |
| Chain **header** | `29.0` | Much lower; treat as **underlying**-level vol, not the contract IV. |

Greeks on quote for the 0-DTE put (example): `delta` ≈ `-0.014`, `mark`/`lastPrice` `0.01`.

### TOS spot-check (held contract)

**Symbol (long in account):** `IREN  270115C00055000` (TOS shorthand **EN270115C55** — IREN 15 Jan 27 $55 call).

**Schwab `/quotes` (same stale `quoteTime` **2026-10-23T20:00:01Z** on re-fetch 2026-10-24):**

| Field | API (`/quotes`) | TOS (screenshot ~2026-10-23 session) | Notes |
| --- | --- | --- | --- |
| **Last** | **0.38** | **0.38** | Match |
| **Bid** | **0.38** | **0.38** | Match (TOS “Bid X” **J**) |
| **Ask** | **0.46** | **0.46** | Match (TOS “Ask X” **M**) |
| **Mark** | **0.42** | *(not shown)* | API mark = mid; TOS header shows **last**, not mark |
| **Day change** | net ≈ **-0.14** | **-0.14** / **-26.92%** | Consistent |
| **Volume** | **50** (prior pull) | **50** | Match |
| **Open / high / low** | **0.48 / 0.55 / 0.38** | **0.48 / 0.55 / 0.38** | Match |

**Greeks / IV (API only — not in screenshot panel):**

| Field | API |
| --- | --- |
| `volatility` | **~103.12** |
| `delta` | **~0.089** |
| `gamma` | **~0.0131** |
| `theta` | **~-0.0119** |
| `vega` | **~0.0192** |

**Conclusion:** **Last, bid, ask, and session OHLC/volume align** between Trader API and TOS for this contract. **Imp vol and greeks were not visible** in the shared TOS quote row — use TOS **Analyze → Option Theoreticals & Greeks** (or equivalent) once if you need numeric IV/delta parity; for v1 pricing marks, **prefer `mark` or mid of bid/ask** and expect **last** to match TOS when the quote is fresh.

## Dividend fields (equity quote)

**Capture:** `20261023T140604Z_equity-quote.json` for `IREN`.

| Field | Path | Value (IREN) |
| --- | --- | --- |
| `divAmount` | `fundamental.divAmount` | `0.0` |
| `divPayAmount` | `fundamental.divPayAmount` | `0.0` |
| `divYield` | `fundamental.divYield` | `0.0` |
| `divFreq` | `fundamental.divFreq` | `0` |
| `nextDivExDate` | not populated on this symbol | absent/`null` |

**IREN (20261023T140604Z):** all dividend fields zero (see table above).

**Portfolio scan (2026-10-24):** Quotes on held tickers (IREN, CIFR, HOOD, ASTS, MP, …) showed **`divYield` 0** — **no dividend-paying equity among current holdings**. Dividend field **units and shape** come from **SATA** (held-style name with non-zero div) and **SPY** (ETF reference capture below).

**SPY (20261024T002829Z_equity-quote.json)** — reference ETF, not a position:

| Field | Path | Example (SPY) |
| --- | --- | --- |
| `divAmount` | `fundamental.divAmount` | **7.55534** (annualized total style) |
| `divPayAmount` | `fundamental.divPayAmount` | **1.88883** (per payment) |
| `divYield` | `fundamental.divYield` | **0.97729** (~**percent**, not decimal 0.01) |
| `divFreq` | `fundamental.divFreq` | **4** (quarterly) |
| `nextDivExDate` | `fundamental.nextDivExDate` | **`2026-12-18T00:00:00Z`** |
| `nextDivPayDate` | `fundamental.nextDivPayDate` | **`2027-02-01T00:00:00Z`** |
| Also | `divExDate`, `divPayDate`, `declarationDate` | ISO date strings |

**SPY option + chain capture:** `20261024T002827Z`–`002829Z` (option `SPY   261102C00762000`). Full **`option-chain`** request returned **502** once; chain fields re-probed via ad-hoc `get` (see pricing section).

**SATA (20261023T145756Z_equity-quote.json):**

| Field | Path | Example value |
| --- | --- | --- |
| `divAmount` | `fundamental.divAmount` | `13.0032` |
| `divPayAmount` | `fundamental.divPayAmount` | `0.05` |
| `divYield` | `fundamental.divYield` | `13.24694` (percent-style magnitude in API) |
| `divFreq` | `fundamental.divFreq` | `0` |
| Ex / pay dates | `divExDate`, `divPayDate`, `nextDivExDate`, `nextDivPayDate` | ISO timestamps, e.g. `2026-10-22T00:00:00Z` |

SATA capture set: `20261023T145755Z`–`145757Z`. Option leg used **`SATA  261120C00100000`** (Nov 2026 $100 call from chain; not a reported position in the accounts pull).

## Option chain: `volatility`, `interestRate`, time

**Capture:** `20261023T140605Z_option-chain.json`.

| Field | Where | Observation |
| --- | --- | --- |
| `interestRate` | Chain **root** only | `4.043` (no per-strike `interestRate` on contracts in this payload). |
| `volatility` | Root vs strike | Root `29.0` (underlying); strike rows carry contract IV (hundreds for near-zero 0-DTE puts). |
| `dividendYield` | Chain root | `0.0` for IREN. |
| Days to expiry | Exp map key + contract | Keys like `2026-10-23:0` (`date:days`); contract `daysToExpiration` `0` for same-day expiry. Suffix `:0`, `:7`, `:29`, … increments with calendar expiries — **time-of-day not represented** in the integer DTE field (0-DTE on expiry day). |

**Rate source / day count:** single chain-level `interestRate` suggests one rate applied across expiries in this response; cannot confirm expiry-dependent rates or day-count convention from this pull alone.

**Re-probe (2026-10-24):** IREN and SPY chains — root **`interestRate` ~4.032–4.043**; **per-contract `interestRate` is `null`** on strike rows. Root **`volatility` ~29.0** (underlying) vs contract IV on rows (e.g. SPY call **~15.5** at 10 DTE; IREN **~109–198** depending on expiry). Exp map keys remain **`YYYY-MM-DD:DTE`** (e.g. `2026-11-02:10`); integer **`daysToExpiration`** on contract matches suffix — **no intraday fraction** in DTE.

## Price history

**Capture:** `20261023T140604Z_equity-price-history.json`.

Daily candles returned for `symbol` IREN with `periodType=year`, `period=1`, `frequencyType=daily`, `frequency=1`. Candle objects include at least `open`, `high`, `low`, `close`, `volume`, `datetime` (epoch ms).

## Long call spreads (per-leg API)

Schwab v1 returns **one quote object per OCC symbol**. There is no combined spread ticker in `/marketdata/v1/quotes`; the engine must fetch each leg and combine marks, greeks, and cost itself.

**Captures:** `.local/schwab/captures/20261023T-spread-iren-quotes.json`, `20261023T-spread-sata-quotes.json`, `20261023T-spread-asst-quotes.json`, positions in `_pos_spread.json` / `_pos_asst.json` (2026-10-23 pull).

### IREN — Jan 15 2027 bull call (40 / 55)

| Leg | Symbol | Role in vertical | Quote `mark` (per share) | `delta` | DTE |
| --- | --- | --- | --- | --- | --- |
| Long | `IREN  270115C00040000` | Lower strike call | `1.385` | `0.241` | `84` |
| Short | `IREN  270115C00055000` | Higher strike call | `0.475` | `0.097` | `84` |
| Underlying | `IREN` | — | `25.37` | — | — |

**Spread mark (synthetic):** `long mark − short mark` → **`0.91` per share** → **`$91` per 1×1 spread** (`multiplier` `100` on both legs).

**Spread delta (synthetic):** `0.144` (sum of leg deltas with short leg subtracted).

**Positions vs spread:** Accounts list **separate long lines** for each strike (no spread asset type). Example long `$40` leg: `longQuantity` `2` and `1` on two accounts, `averagePrice` / `taxLotAverageLongPrice` ≈ `10.33`–`10.38` (entry premium per share, not spread net). Long `$55` leg: `12` contracts, `averagePrice` ≈ `9.67`. **No `shortQuantity` on the 55 call** in this pull — Schwab positions reflect individual legs, not a linked vertical order.

### SATA — Nov 20 2026 bull call (95 / 100)

| Leg | Symbol | Role | Quote `mark` | `delta` | DTE |
| --- | --- | --- | --- | --- | --- |
| Long | `SATA  261120C00095000` | Lower strike | `3.30` | `0.685` | `28` |
| Short | `SATA  261120C00100000` | Higher strike | `0.025` | `0.037` | `28` |
| Underlying | `SATA` | — | `97.555` | — | — |

**Spread mark:** **`3.275` per share** → **`$327.50` per 1×1 spread**.

**Positions:** No SATA option lines in the accounts pull (equity-only or unheld); spread pricing is from quotes only.

**Liquidity note:** Deep OTM SATA strikes can show **non-monotonic marks** (e.g. 100/105 pair had short leg mark above long); prefer near-the-money verticals (95/100) when sampling.

### ASST — Nov 20 2026 bull call (29 / 29.5)

| Leg | Symbol | Role | Quote `mark` | `delta` | DTE |
| --- | --- | --- | --- | --- | --- |
| Long | `ASST  261120C00029000` | Lower strike ($29) | `3.525` | `0.580` | `28` |
| Short | `ASST  261120C00029500` | Higher strike ($29.50) | `3.275` | `0.555` | `28` |
| Underlying | `ASST` | — | `29.47` | — | — |

**Spread mark:** **`0.25` per share** → **`$25` per 1×1 spread** (tight $0.50-wide vertical near the money).

**Spread delta (synthetic):** **`0.025`**.

**Positions:** **Equity only** in the accounts pull (multiple long `ASST` stock lines across margin accounts; no ASST option legs). Spread marks are **quotes-only**, same pattern as SATA.

## VIX and index options

**Captures (2026-10-23):** `.local/schwab/captures/20261023T-vix-chain-sample.json` (chain); live pulls for `$VIX` quote, `$VIX` price history, and sample option `VIX   261118C00030000`. No VIX/VIXY positions in accounts pull.

### Symbol cheat sheet

| Goal | Symbol param | Works? |
| --- | --- | --- |
| Index spot / mark | **`$VIX`** | Yes (`assetMainType` `INDEX`) |
| Plain `VIX` | `VIX` | **No** — `invalidSymbols` |
| Option chain | **`$VIX`** | Yes (`isIndex` `true`) |
| Chain with `VIX` | `VIX` | **No** — HTTP 400 invalid parameter |
| Tradable vol ETF | `VIXY` | Yes — **`EQUITY` / ETF**, not the index |

CLI: URL-encode `$` as `%24` (e.g. `symbols=%24VIX`, `chains?symbol=%24VIX`).

### Index quote vs equity quote

**`$VIX` quote (INDEX):** `reference.exchangeName` `Index`, `reference.optionable` `true`, `reference.ethOptionEligible` `true`. Quote has `lastPrice` / `mark` / OHLC; **`totalVolume` `0`**; no equity-style bid/ask on the index line in the pull. Fundamentals are zeroed (`eps`, `divYield`, etc.).

**Price history:** `GET .../pricehistory?symbol=%24VIX&...` returns candles with **`volume: 0`** on every bar (index, not share volume).

### Option chain (index)

Chain root fields observed: `isIndex` **`true`**, `assetMainType` **`INDEX`**, `underlyingPrice` tracks index (~`18.94` in pull), `interestRate` **`4.043`** (chain root, same pattern as IREN), header `volatility` **`29.0`** (not contract IV).

Exp map keys still `YYYY-MM-DD:days` (e.g. `2026-11-18:26`).

### Option symbol format (VIX vs equity)

| Item | Equity (e.g. IREN) | VIX index option |
| --- | --- | --- |
| Spaces after root in OCC | **Two** (`IREN  261023P…`) | **Three** (`VIX   261118C00030000`) |
| Chain / quote `symbol` | Same spacing as quotes | Must match chain output exactly |
| `reference.underlying` | Ticker e.g. `IREN` | **`$VIX`** |
| `underlyingAssetType` | `EQUITY` | **`INDEX`** |
| `deliverables` | e.g. `100 IREN` | **`100 $VIX(Cash)`** |
| `exerciseType` (sample) | `A` (American) common on equity | **`E`** (European) on sample $30 call |
| `settlementType` | `P` physical on equity sample | **`A`** on chain row (index AM-style — confirm in TOS for product) |
| `expirationType` | `W` / standard | **`W`** on sample (weekly complex) |

Always take OCC strings from **`/chains`** or **`/quotes`** responses; do not guess spacing.

### Sample contract quote (Nov 18 2026 $30 call)

Symbol: `VIX   261118C00030000`. Underlying index **`18.94`**. Option **`mark` `0.82`**, **`delta` `0.211`**, contract **`volatility` ~`159`** (index option IV scale — not comparable to ~100% equity IV without context). Chain header **`volatility` `29.0`** is not this contract’s IV (same lesson as IREN chain header vs strike row).

Greeks present on quote: `delta`, `gamma`, `theta`, `vega`, `rho`, `theoreticalOptionValue`, `moneyIntrinsicValue` (negative when OTM on index).

### Scope limits

- This is **CBOE VIX index + listed VIX options**, not **`/VX` futures**.
- **VIXY** (and similar) are separate **ETF** underlyings; use equity endpoints and normal two-space OCC if optionable.
- **SPX / XSP** not observed in this capture set; expect same `$`-prefixed index pattern to be likely but unverified here.

## Futures, crypto, and dollar macro (`/BZ`, `/BTC`, `$DXY`, `/ZN`)

**Captures (2026-10-23):** live quote pulls; `.local/schwab/captures/20261023T-btc-index-chain-sample.json` (`$BTC` chain). No positions in these products in accounts pull.

### Summary table

| You asked for | Quote param | Resolves to | `assetMainType` | Options chain |
| --- | --- | --- | --- | --- |
| Brent `/BZ` | **`/BZ`** | Active contract e.g. **`/BZZ26`** | **`FUTURE`** | **400** — not on `/BZ` |
| Brent | `BZ` alone | **`BZ`** (Kanzhun ADR) | `EQUITY` | Wrong symbol |
| Bitcoin `/BTC` | **`/BTC`** | Active e.g. **`/BTCV26`** | **`FUTURE`** | **400** on `/BTC` |
| Bitcoin index | **`$BTC`** | **`$BTC`** | **`INDEX`** | **200** but **empty** maps |
| Bitcoin ETFs | `IBIT`, `BITO`, `BTC` | same ticker | `EQUITY` / ETF | Use equity `/chains` if needed |
| Dollar **`$DXY`** (ICE cash index) | `$DXY`, `DXY`, `/DXY`, `DX-Y.NYB`, … | — | **Invalid / wrong** in pull | **400** on some roots |
| Dollar **`/DX`** (ICE futures) | **`/DX`**, `/DXZ26`, … | — | **`invalidSymbols`** on quotes | **400** on `/DX` chain |
| **ICE basket FX spots** | **`EUR/USD`**, **`USD/JPY`**, … (six legs) | same | **`FOREX`** / GFT | N/A (compute USDX) |
| Dollar proxy ETF | **`UUP`**, `UDN`, `USDU` | ETF | `EQUITY` | ETF options if `optionable` |
| 10Y **`/ZN`** | **`/ZN`** | Active e.g. **`/ZNZ26`** | **`FUTURE`** | **400** on `/ZN` |
| 10Y | `ZN` alone | — | **invalid** | — |

Futures roots use a **leading slash** in `reference.product` (e.g. `product: "/BZ"`). Request **`/BZ`**, **`/BTC`**, **`/ZN`** on quotes; API returns the **front/active contract symbol** (month code in key, e.g. `/BZZ26`, `/BTCV26`, `/ZNZ26`).

### Futures quote shape (Brent, Bitcoin, ZN)

Common fields on **`assetMainType: FUTURE`** (distinct from equity quotes):

| Field | `/BZZ26` (Brent) | `/BTCV26` (Bitcoin) | `/ZNZ26` (10Y note) |
| --- | --- | --- | --- |
| `reference.product` | `/BZ` | `/BTC` | `/ZN` |
| `reference.exchangeName` | `XNYM` | `XCME` | `XCBT` |
| `reference.futureMultiplier` | `1000` | (see quote; CME BTC) | `1000` |
| `reference.futurePriceFormat` | `D,D` (decimal) | decimal | **`3,32`** (32nds) |
| `quote.openInterest` | yes | yes | yes |
| `quote.futurePercentChange` | yes | yes | yes |
| `quote.tick` / `tickAmount` | `0.01` / `10` | `5` / `25` | (treasury tick semantics) |
| `quote.settleTime` / `futureSettlementPrice` | yes | yes | yes |

**Price history:** works on **resolved contract** symbols (`/BZZ26`, `/BTCV26`, `/ZNZ26`) — daily candles returned; futures **`volume`** populated (unlike `$VIX` index).

**Do not** use bare `BZ` for crude — it is an unrelated **ADR**.

### Bitcoin: futures vs index vs ETF

1. **`/BTC` futures** — normal CME-style futures quote (bid/ask, volume, OI). Use for tradable BTC macro mark aligned with futures session.
2. **`$BTC` index** — `Bloomberg Galaxy Bitcoin Index`. Quote line was **all zeros** / null mark in pull; `optionable: false`. Chain call returned **`SUCCESS`** but **`callExpDateMap` / `putExpDateMap` empty** — no listed options on this index in API.
3. **ETFs** (`IBIT`, `BITO`, `BTC` Grayscale Mini) — standard **`EQUITY` / ETF** quotes with fundamentals; use for spot-ETF exposure and equity option chains.

### US Dollar Index (`$DXY` / ICE DXY)

**thinkorswim vs Trader API:** TOS can show **`$DXY`** (ICE U.S. Dollar Index) as a **reference chart** (~100 scale). The **Trader API** used by this CLI is **not** delivering that series in our pulls.

| Endpoint | Symbol | Result |
| --- | --- | --- |
| **`/quotes`** | **`$DXY`** | **`invalidSymbols`** — no current price object |
| **`/pricehistory`** | **`$DXY`** | Request accepted; **`empty: true`**, **0 candles** |
| **`/quotes`** | `DXY`, `/DXY`, `$DX`, `/DX`, `DX-Y.NYB`, … | Invalid or wrong instrument |
| **`/quotes`** | **`DX`** | **Dynex Capital REIT** (`EQUITY`) — not the dollar index |
| **`/instruments`** | `$DXY`, `/DX` | **Empty** `{}` / no match |
| **`/quotes`** | **`$USDOLLAR`** | **Different index** — “Dow Jones FXCM Dollar Index”, ~`12808` (not ICE DXY scale); **price history also empty** |
| **`/quotes`** + history | **`UUP`** | **ETF** proxy; tradable; history **works** (252 daily bars in pull) |

Schwab’s **futures** product list names **U.S. Dollar Index futures** as **`/DX`** (ICE, $1k multiplier). **`/DX`** and resolved contracts (e.g. `/DXZ26`) were **`invalidSymbols`** on **`/quotes`** here — likely **missing futures/ICE market-data entitlement** on the API app or account, not necessarily “symbol wrong.”

**`/DX` price history (retest):** `GET .../pricehistory?symbol=%2FDX&periodType=year&period=1&frequencyType=daily&frequency=1` returns **`symbol: "/DX"`, `empty: true`, 0 candles** — same for `/DXZ26`, `/DXH26`, `/DXM26`. The API accepts the symbol but ships **no series**. Do **not** use bare **`DX`** for futures history: that returns **252 bars** of **Dynex Capital (`EQUITY`)** (~`13`→`11`), not dollar futures.

**Bottom line (index symbols):** Trader API does **not** serve **`$DXY`** or **`/DX`** like TOS. **Spot ICE level** can still be derived from **six FX quotes** (below). **DXY history** does **not** come from Schwab index or FX history probes (below). Retest **`$DXY` / `/DX`** after index/futures market-data entitlement changes.

### Schwab FX spot quotes (ICE USDX basket legs)

Schwab returns **GFT spot** **`FOREX`** quotes for all **six ICE USDX legs** in **one** `/marketdata/v1/quotes` call when symbols use **`BASE/QUOTE`** with a slash (URL-encode **`/`** as **`%2F`**).

**Working request:**

```text
GET /marketdata/v1/quotes?symbols=EUR%2FUSD,USD%2FJPY,GBP%2FUSD,USD%2FCAD,USD%2FSEK,USD%2FCHF
```

| Encoding | Example | Result |
| --- | --- | --- |
| **`BASE/QUOTE`** | `EUR/USD`, **`USD/SEK`** | **Quote OK** — `mark`, bid/ask, `quoteTime` (ms epoch) |
| Concatenated | `EURUSD`, `USDJPY` | **`invalidSymbols`** |
| Slash + concat | `/EURUSD` | **`invalidSymbols`** |
| `$` prefix | `$EURUSD` | **`invalidSymbols`** |

**Sample fields (EUR/USD):** `assetMainType: FOREX`, `reference.exchangeName: GFT`, `reference.isTradable: false`, `quote.mark`, `quote.quoteTime`, `quote.bidPrice` / `askPrice`.

**USD/SEK:** quotes in live pulls (~9.94); was the main unknown leg — **confirmed**.

### Computed ICE USDX from Schwab FX (`pnpm schwab macro dxy`)

**Formula (ICE cash index, same as TOS `$DXY`):**

```text
USDX = 50.14348112 × EURUSD^−0.576 × USDJPY^0.136 × GBPUSD^−0.119 × USDCAD^0.091 × USDSEK^0.042 × USDCHF^0.036
```

Each rate is the **Schwab `mark`** on the matching **`BASE/QUOTE`** symbol. Implementation: `tools/schwab/src/schwab_cli/usdx.py`; CLI emits JSON with **`method: ice-formula`**, **`source: schwab-fx`** (provenance for consumers — distinct from fetched external series).

**Quote gates (v1):**

- **All six legs** required; partial set must **fail** (name missing legs).
- **Same price field on every leg:** `mark` (must be **> 0**).
- **Leg `quoteTime` spread** ≤ **60 s** or fail (typical live spread ~**0.1 s**).
- **FX weekend close** (Fri **17:00** – Sun **17:00** America/New_York): still emit level with **`marketOpen: false`** (frozen marks, not an error).

**Validation vs external (not vs unknowable ICE fixing feed):** Cross-check **`DX-Y.NYB`** (Yahoo chart API) when both are fetched in the **same minute**; target **≤ 2 bp** gap.

| Smoke (2026-10-23, same minute) | Value |
| --- | --- |
| Schwab computed (`macro dxy`) | **101.8005** |
| Yahoo `DX-Y.NYB` | **101.794** |
| Gap | **0.64 bp** |
| `legSpreadSec` | **0.101** |

Earlier snapshots at different times (e.g. **101.7976** vs **101.796**, ~**0.16 bp**) only prove the formula/symbol map are wired correctly — not a regression harness.

**Verdict file:** [tools/schwab/prototype/DXY_FROM_FX_VERDICT.md](../../tools/schwab/prototype/DXY_FROM_FX_VERDICT.md).

### DXY price history (what works on Schwab)

| Path | Symbol | Result |
| --- | --- | --- |
| Index | **`$DXY`** | **`empty: true`**, 0 candles |
| Futures | **`/DX`**, `/DXZ26`, … | **`empty: true`**, 0 candles |
| **FX spot** | **`EUR/USD`** (daily, 1 month probe) | **`empty: true`**, 0 candles |
| ETF proxy | **`UUP`** | **Works** — daily bars on Schwab |

**Implications:**

- **Cannot** build a historical ICE USDX series by applying the ICE formula to **Schwab FX history** (FX **`pricehistory`** appears unsupported; aligns with common Schwab docs: history for **equities/ETFs**).
- **Do not** rebuild daily DXY from **six Yahoo FX closes** — 24h FX “daily close” conventions differ by leg; series will **not** match ICE daily values.
- **Interim daily history:** fetch **`DX-Y.NYB`** index from Yahoo chart API (dev/reference) or **ICE / Blocklens** when licensed. **`/DX` futures** is a **different series** from the cash index — keep out of cash DXY sync.

### DXY proxy (interim): **`UUP`** (Invesco DB US Dollar Bullish)

**When to use:** Schwab **history** or display when you accept **ETF level** (not ICE formula). **Preferred spot level on Schwab token:** **`pnpm schwab macro dxy`** (computed USDX), not **`UUP × k`**, unless you intentionally want an investable proxy.

**Why UUP still matters:** Schwab **`/quotes` + `/pricehistory` work** on **`UUP`**; standard **long-dollar** ETF (not inverse **`UDN`**, not different methodology **`USDU`**). **`USDU`** had a higher and noisier DXY/ETF ratio in calibration.

**Trend:** Daily **returns** on **UUP** vs **ICE DXY** (`DX-Y.NYB`, external series for calibration) showed **~0.82 correlation** over ~501 aligned sessions (2024–2026) — directionally similar, not identical (fees, DB index ≠ ICE, ETF premium/discount).

**Level mapping (ICE DXY from UUP mark):** Multiplicative factor tracks **spot** well in the current regime:

```text
DXY_ICE ≈ k × UUP_mark
```

| Calibration | `k` | Example @ `UUP` ≈ 28.95 |
| --- | --- | --- |
| Your TOS ICE **`$101.796`** ÷ Schwab **`UUP` 28.9495** (2026-10-23) | **`3.5163`** | **`101.80`** |
| Same day Yahoo **`DX-Y.NYB` ~101.79** ÷ **`UUP` 28.90** (prior close) | **`3.516`** | — |
| 60-session median ratio (recent) | **`3.531`** | ~102.2 |
| 2y mean ratio (drifts; ETF/index basis) | **`3.587`** | ~103.9 |

**Recommendation (interim ETF path):** Map display with **`k ≈ 3.52`** (`k = DXY_ICE / UUP_mark` from TOS or external). **Spot on Schwab:** use **`macro dxy`**. **History / license:** see **[external-market-data.md](./external-market-data.md)**.

Optional linear model (worse at today’s spot): `DXY_hat ≈ 2.36 + 3.50 × UUP`. Prefer external ICE or **`k × UUP`** interim.

**Captures:** `.local/schwab/captures/_uup_hist.json`, `_dxy_yahoo.json` (external calibration only, gitignored).

### Treasury **`/ZN`**

- Request **`/ZN`** → active **`/ZNZ26`** (Dec-2026 10-Year note future in pull).
- Prices use **32nd-style** formatting (`futurePriceFormat: 3,32`); e.g. **`lastPrice` ~`106.125`**, **`futureSettlementPrice` ~`106.40625`**.
- **`/ZB`** (30-year bond future) behaves similarly (`/ZBZ26`).
- No options chain on `/ZN` root (400); treasury options would be a different product symbol if supported at all.

### Engine rules (from this pull)

1. Request `GET /marketdata/v1/quotes?symbols=...` with URL-encoded symbols (**`%24`** for `$`; **`%2F`** for `/` on futures roots).
2. **Futures roots** (`/BZ`, `/BTC`, `/ZN`): quote response key is the **concrete contract**; store `reference.product` for roll logic.
3. **Equity spreads:** two-space OCC; **VIX:** three-space OCC from chain (see VIX section).
4. Net mark for a 1×1 bull call: `mark_long − mark_short`; net delta: `delta_long − delta_short`.
5. Cost basis from positions: per-leg `averagePrice × quantity × multiplier`; no spread-level `averagePrice`.
6. **`$DXY` / `/DX` (ICE index symbols):** **`/quotes` invalid**; **`/pricehistory` empty**. **Spot ICE level:** six **`BASE/QUOTE`** FX quotes + ICE formula → **`pnpm schwab macro dxy`**. **FX `pricehistory`:** empty in probe — do not plan historical USDX from Schwab legs. Never map to equity **`DX`** (Dynex). **`/DX` futures** ≠ cash USDX.
7. **Macro JSON:** every macro command should expose **`method`** and **`source`** so consumers distinguish **computed** (`ice-formula` / `schwab-fx`) from **fetched** (`yahoo`, etc.).

## Redaction

Captures redact only JSON `accountNumber` values to `REDACTED:8-digits` so large numeric fields (`totalVolume`, etc.) stay valid JSON.
