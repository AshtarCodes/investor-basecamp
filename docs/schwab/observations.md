# Schwab API observations

Empirical notes from live captures on 2026-10-23. Captures live under `.local/schwab/captures/` (gitignored). Placeholders below avoid real balances and quantities in git.

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

**Capture:** same accounts-positions file; three accounts returned.

| Account kind | `securitiesAccount.type` | NLV field |
| --- | --- | --- |
| All three in this pull | `MARGIN` only | No `CASH` or `IRA` types in this capture. |

**Net liquidation:** use `securitiesAccount.currentBalances.liquidationValue` (matches `aggregatedBalance.currentLiquidationValue` on the same account object). Also present on `initialBalances.liquidationValue` / `projectedBalances` but **current** is the live NLV for sync.

Other useful balance paths: `currentBalances.equity`, `longOptionMarketValue`, `shortOptionMarketValue` (negative when short options), `buyingPower`, `maintenanceRequirement`.

## Option symbol format

**Captures:** positions + `20261023T140603Z_option-quote.json` + chain.

| Item | Value |
| --- | --- |
| API symbol | `IREN  261023P00022000` (root, **two spaces**, OCC date/strike encoding) |
| Uniform symbol | Same string on `instrument.uniformSymbol` |
| Description | `IREN LTD 10/23/2026 $22 Put` |
| Underlying | `instrument.underlyingSymbol` → `IREN` |
| Settlement | quote `reference.settlementType` → `P` (physical); `exerciseType` → `A` (American) |
| Index roots (SPX/XSP) | **Not present** in this capture; only equity underlyings observed. |

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

Greeks on quote for the 0-DTE put (example): `delta` ≈ `-0.014`, `mark`/`lastPrice` `0.01`. **thinkorswim comparison not run in this session** — verify side-by-side on the same symbol and session time before trusting IV for models.

## Dividend fields (equity quote)

**Capture:** `20261023T140604Z_equity-quote.json` for `IREN`.

| Field | Path | Value (IREN) |
| --- | --- | --- |
| `divAmount` | `fundamental.divAmount` | `0.0` |
| `divPayAmount` | `fundamental.divPayAmount` | `0.0` |
| `divYield` | `fundamental.divYield` | `0.0` |
| `divFreq` | `fundamental.divFreq` | `0` |
| `nextDivExDate` | not populated on this symbol | absent/`null` |

**Gap:** ticket asked for a **dividend-paying** holding; this capture used IREN (no dividend in API). Re-run `capture` with a dividend payer you hold (e.g. `--equity` on a position with non-zero `divYield`) to fill that row.

## Option chain: `volatility`, `interestRate`, time

**Capture:** `20261023T140605Z_option-chain.json`.

| Field | Where | Observation |
| --- | --- | --- |
| `interestRate` | Chain **root** only | `4.043` (no per-strike `interestRate` on contracts in this payload). |
| `volatility` | Root vs strike | Root `29.0` (underlying); strike rows carry contract IV (hundreds for near-zero 0-DTE puts). |
| `dividendYield` | Chain root | `0.0` for IREN. |
| Days to expiry | Exp map key + contract | Keys like `2026-10-23:0` (`date:days`); contract `daysToExpiration` `0` for same-day expiry. Suffix `:0`, `:7`, `:29`, … increments with calendar expiries — **time-of-day not represented** in the integer DTE field (0-DTE on expiry day). |

**Rate source / day count:** single chain-level `interestRate` suggests one rate applied across expiries in this response; cannot confirm expiry-dependent rates or day-count convention from this pull alone.

## Price history

**Capture:** `20261023T140604Z_equity-price-history.json`.

Daily candles returned for `symbol` IREN with `periodType=year`, `period=1`, `frequencyType=daily`, `frequency=1`. Candle objects include at least `open`, `high`, `low`, `close`, `volume`, `datetime` (epoch ms).

## Redaction

Captures redact only JSON `accountNumber` values to `REDACTED:8-digits` so large numeric fields (`totalVolume`, etc.) stay valid JSON.
