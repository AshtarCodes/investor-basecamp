# `schwab option price` CLI

Type: task
Status: ready-for-agent

Blocked by: [16](16-pricing-engine-package.md), [17](17-engine-rate-and-dividend-inputs.md) (builds on [06](06-pricing-inputs-and-models.md), [ADR 0001](../../../docs/adr/0001-own-pricing-model.md) and [ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md))

## Goal

Add `pnpm schwab option price` — orchestrate Schwab quotes, reprice with **our** model, optionally run expiry or pre-expiry sale P&amp;L scenarios. Live runs **always** call the API (no `--fetch` flag). Schwab mark/greeks sit beside our outputs for cross-check (tolerance, not equality).

**v1 contract identity:** Path A (`--symbol`) only. Path B is deferred (see implementation phases).

## What it adds over `schwab get`

`get` returns one raw JSON slice. This command:

- Resolves the contract (OCC on v1; composed flags → OCC later).
- Pulls option + underlying + chain fields needed for IV/rate.
- Emits structured JSON: shared **`contract`** + **`schwab`**, mode-specific **`results.*`**, provenance on inputs.
- Computes **T** to settlement per issue 06 (equity: 4:00 pm ET on expiry; AM SPX: 9:30 am ET).
- Optional **`--mode expiry`** / **`sell`** / **`both`** without hand math.

## Domain vocabulary

Use CLI terms from [tools/schwab/GLOSSARY.md](../../../tools/schwab/GLOSSARY.md) (listed in [GLOSSARY-MAP.md](../../../GLOSSARY-MAP.md)).

## Contract identity (one source of truth)

**Path A (v1):** `--symbol '<OCC>'` — copy from TOS/positions.

**Path B (later):** `--underlying TICKER --exp YYYY-MM-DD --strike N --call|--put` — CLI resolves/builds OCC (chain lookup or formatter), then quotes.

Expiry for pricing is **always** taken from parsed symbol or `--exp`. There is **no `--until`**.

## Remaining life (one input, two encodings)

Every mode that uses **T** shares a single concept: **remaining life** from a valuation or **exit instant** through contract settlement.

| Encoding | Flag | Effect |
| --- | --- | --- |
| **Days** | **`--dte`** | Set remaining life directly (stress or exact). |
| **Date** | **`--as-of`** | Set the **exit instant** ( **`sell`** ) or **valuation instant** ( **`theoretical`** ); **T** = settlement − that instant. |

**If both are set, `--dte` wins** — the date does not also define **T**. The winning encoding is used everywhere the model needs remaining life.

### Exit instant (`sell`)

**`--expected-spot` (required)** is the underlying at the **exit instant**:

- **`--as-of` only:** exit instant = that date (default **now**).
- **`--dte` only:** exit instant = contract settlement minus that remaining life (same instant the date encoding would imply).
- **Both:** **`--dte` wins** for remaining life / exit instant; **`--expected-spot`** is still stock at that exit instant.
- **Exit before now:** on a live run, a past **`--as-of`**, or a **`--dte`** larger than the real remaining life, is an error; use **`--offline`** with aligned inputs.

### Valuation instant (`theoretical`)

- **Live runs:** **`--as-of` must be now** (default). A past or future calendar **`--as-of` without `--offline`** is an **error** — use **`--dte`** for time stress, **`sell`** for dated exit + stock level, or **`--offline`** for point-in-time fair value.
- **T** from **`--dte`** or from settlement − **`--as-of`** (when **`--as-of`** is now).
- **S₀** for the model is **today’s** underlying (or **`--spot`** / quote on the happy path). Changing **T** via **`--dte`** does **not** move **S₀** unless **`--offline`** with aligned inputs.

### `expiry`

No model, no **T**. **`--as-of`** / **`--dte`** ignored for pricing. **`--expected-spot`** is **terminal spot** at contract expiration only.

## Live vs historical inputs

| Mode | Live default inputs | Point-in-time fair value or exit |
| --- | --- | --- |
| **`theoretical`** | Today’s spot, IV, rate from Schwab; **T** from calendar or **`--dte`** | **`--offline`** + **`--spot`**, **`--vol`**, **`--rate`**, and **`--as-of`** (or **`--dte`**) aligned to that day |
| **`sell`** | Today’s IV, rate, div from Schwab; **S** at exit = **`--expected-spot`**; **T** from exit instant → expiry | **`--offline`** + aligned inputs (v1) |
| **`expiry`** | No model; no vol | Same |

**IV default (CLI):** **Mark-implied IV**, the same as the portfolio app ([07](07-how-should-shocks-behave.md)): solved through our model from the contract's **Mark**, so `theoretical` at now reproduces the mark by construction and `sell` / `--dte` start from the app's base. Schwab's `volatility` is **Schwab IV**, shown in `crossCheck` only and never fed into our model ([ADR 0001](../../../docs/adr/0001-own-pricing-model.md)). The rate is the Treasury.gov curve at the expiry; the chain `interestRate` is a flagged fallback and a `crossCheck` field.

## Modes (`--mode`)

| Mode | Question | Uses pricing model? |
| --- | --- | --- |
| **`theoretical`** | Fair value **now** (live) or at **`--offline`** valuation instant. | Yes — BS / LR |
| **`expiry`** | **Hold to expiration:** intrinsic if stock = **`--expected-spot`** at expiry. | No — intrinsic only |
| **`sell`** | **Sell before expiration:** model value at **exit instant** if stock = **`--expected-spot`** then; sale P&amp;L vs **Entry**. | Yes — BS / LR at exit |
| **`both`** | **`theoretical`** + **`expiry`** in one JSON. | Mixed |

### `expiry` (hold to expiration)

- **`--expected-spot` (required):** **terminal spot** — underlying at **contract expiry**.
- **No `--vol`** — not used.
- **Output:** intrinsic per share, **net P&amp;L** vs **Entry**, **`breakevenSpot`** (closed form: call **K + entry**, put **K − entry** per share).

### `sell` (before expiration)

Scenario: at the **exit instant**, underlying is **`--expected-spot`**. You **sell** at **our model price** with **T** = remaining life from that instant to settlement.

**Inputs:**

| Input | Required? | Live default |
| --- | --- | --- |
| **`--expected-spot`** | **Yes** | — (scenario stock at exit instant) |
| **`--vol`** | Optional | **Mark-implied IV** (constant σ from exit → expiry) |
| **`--rate`** | Optional | Treasury.gov curve at the expiry (chain `interestRate` is a flagged fallback) |
| Dividends | Optional flags | Discrete schedule from the quote (see **Dividends** in the decisions table) |
| Exit instant | Optional | **`--as-of` = now** or **`--dte`** only (see **Remaining life**) |

**Not required on happy path:** **`--spot`** — the model uses **`--expected-spot`** as **S** at exit, not today’s quote unless you set them equal.

**Output:** **`saleProceeds`** (our value per share at exit), **net P&amp;L** = proceeds − **Entry**, optional greeks at exit. **No `breakevenSpot` in v1** (inverse solve deferred).

**Relation to `theoretical`:** **`sell`** with exit **now**, **`--expected-spot` = live underlying mark** ≈ same option value as **`theoretical`**, framed as sale P&amp;L vs mark **Entry**.

### P&amp;L baseline — **`--entry`**

**Net P&amp;L** = (intrinsic at expiry **or** **`saleProceeds`**) − **Entry** per share.

| Situation | Entry |
| --- | --- |
| **`--entry` provided** | Your fill / tax lot (per share). |
| **Live, no `--entry`** | **Schwab `mark`**. `"entry": { "from": "schwab-mark" }`. |
| **`--offline`, no `--entry`** | **Error** — pass **`--entry`**. |

**`--entry`** never overrides model inputs; P&amp;L baseline only. Not Position **Total Cost** / `averagePrice`.

### `--expected-spot` meaning

| Mode | **`--expected-spot` is…** |
| --- | --- |
| **`expiry`** | **Terminal spot** at **contract expiration** |
| **`sell`** | Underlying at the **exit instant** |
| **`both`** | **Required** — used for the **`expiry`** block only; **`theoretical`** ignores it |

**`--spot`:** **`theoretical`** only — **S₀** at valuation (live default from quote when valuation is now).

## Flags (v1)

| Flag | Required? | Description |
| --- | --- | --- |
| `--symbol` | **Required** (v1) | OCC contract (Path A). |
| `--offline` | Optional | No API; need inputs below for **`theoretical`** / **`sell`**. |
| `--spot` | **If `--offline`** (`theoretical`) | S₀ at valuation; live fills from quote. |
| `--vol` | **If `--offline`** (`theoretical` / `sell`) | σ override; live default **Mark-implied IV**. |
| `--vol-unit` | Optional | `percent` (default) or `decimal`. |
| `--rate` | **If `--offline`** (`theoretical` / `sell`) | % override; live default Treasury curve at the expiry. |
| `--dte` | Optional | Remaining life (stress or exact); wins over date encoding. |
| `--as-of` | Optional | **`theoretical`:** valuation instant (live: **now** only); **`sell`:** exit date (default now ET). |
| `--expected-spot` | **If `expiry`, `sell`, or `both`** | See table above. |
| `--entry` | Optional | P&amp;L **Entry** per share; **live default = Schwab mark**. |
| `--contracts` | Optional | Count for dollars (default 1, ×100). |
| `--mode` | Optional | `theoretical` \| `expiry` \| `sell` \| `both` (default `theoretical`). |
| `--model` | Optional | `auto` \| `american` \| `european` (default `auto`). |
| `--no-div` | Optional | Force zero dividends. |
| `--div-yield` | Optional | Continuous yield override (%). |

**Deferred (not v1):** Path B flags (`--underlying`, `--exp`, `--strike`, `--call`/`--put`), sweeps (`--sweep`, `--sigma`, …).

Removed from earlier drafts: `--fetch`, `--compare-schwab`, `--until`, **`asOfAppliesTo`**.

## Agreed decisions (conversation + grill)

| Topic | Decision |
| --- | --- |
| **API** | Live runs **always** fetch Schwab; **`--offline`** only for tests / explicit inputs. No **`--fetch`**. Live **`expiry`** runs fetch too, even with **`--entry`**, so the **`schwab`** block is always present and the OCC symbol is checked against a real contract. |
| **Output** | Shared **`contract`** + **`schwab`**; **`results.theoretical`** / **`results.expiry`** / **`results.sell`** as applicable. **`crossCheck`** (replaces the earlier `gapVsMark`) only under **`theoretical`** and **`both`**'s theoretical section. |
| **Contract v1** | Path A **`--symbol`** only. Path B later. No **`--until`**. |
| **Remaining life** | One input: **`--dte`** or date via **`--as-of`**; **`--dte` wins** if both set; same **T** everywhere in formulas. |
| **Live `theoretical` + date** | Past/future **`--as-of`** without **`--offline`** → **error**. Time stress on live → **`--dte`**. No **`asOfAppliesTo`**. |
| **Default mode** | **`theoretical`** when `--mode` omitted. |
| **`both`** | **`theoretical`** + **`expiry`** only (not **`sell`**). **`--expected-spot` required** (expiry block); no default to live underlying. |
| **`--entry`** | P&amp;L **Entry** for **`expiry`** / **`sell`**; live default **Schwab mark** (buy-at-mark / not-held scenarios); never a model input; not **Total Cost**. |
| **Vol** | **`expiry`:** unused. **`theoretical`** / **`sell`:** live default **Mark-implied IV**; optional **`--vol`**. Constant σ through remaining life. Same as the app ([07](07-how-should-shocks-behave.md)). Schwab IV appears only in `crossCheck`. |
| **Dividends** | **`theoretical`** / **`sell`:** discrete cash dividends in v1. With `divFreq` 4, the schedule comes from `nextDivExDate` and `divPayAmount`, projected every 3 months to expiry, and the JSON names the projection rule. `divFreq` 0 with `divYield` above 0 (SATA's case): continuous yield from `divYield` (percent), a warning, and `divTreatment: "continuous-yield"`. All dividend fields zero: none. **`expiry`:** ignores div flags. |
| **Rate** | Treasury.gov daily par curve interpolated to the expiry, continuous compounding, `from: "treasury-gov"`. Schwab's chain `interestRate` (about 4.04, root only, source unknown) matched no Treasury tenor on 2026-10-23 (4.11 at 1 month, 4.22 at 3 months), so it is a flagged fallback and a `crossCheck` field. |
| **Engine** | Python package ([16](16-pricing-engine-package.md) core, [17](17-engine-rate-and-dividend-inputs.md) rate and dividends, [ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md)); the CLI imports it. Exact minutes to the **Settlement instant** come from the engine's virtual clock. |
| **Cross-check** | `crossCheck`: IV gap in vol points (ours minus Schwab IV), our value at Schwab IV, and the difference from the **Mark** and from Schwab's `theoreticalOptionValue`. Tolerance, not equality. |
| **`--spot`** | **`theoretical`** only. **`sell`** uses **`--expected-spot`** at exit instant. |
| **`sell` + past exit** | Live **`sell`** with an exit instant before now (a past **`--as-of`**, or **`--dte`** larger than the real remaining life) is an **error** that points to **`--offline`**, the same rule as **`theoretical`**. **`--dte`** above the real remaining life stays allowed under **`theoretical`** as a stress. |
| **Breakeven** | **`expiry`:** **`breakevenSpot`** closed form. **`sell`:** omit v1. |
| **Sweeps** | Out of v1 spec (portfolio **Scenario** grid owns grid shocks). |
| **Glossary** | [tools/schwab/GLOSSARY.md](../../../tools/schwab/GLOSSARY.md) + [GLOSSARY-MAP.md](../../../GLOSSARY-MAP.md). |
| **Live happy path** | **`pnpm schwab option price --symbol '<OCC>'`** only for **`theoretical`**. |

## Live happy path

```bash
pnpm schwab option price --symbol 'IREN  270115C00055000'
```

Hold to expiry (no vol):

```bash
pnpm schwab option price --symbol 'IREN  270115C00055000' \
  --mode expiry --expected-spot 50
```

Sell before expiry (stock at $40 on exit date; vol defaults from chain):

```bash
pnpm schwab option price --symbol 'IREN  270115C00055000' \
  --mode sell --as-of 2026-06-30 --expected-spot 40
```

Theoretical time stress (today’s spot/IV; pretend 120 days left):

```bash
pnpm schwab option price --symbol 'IREN  270115C00055000' --dte 120
```

Sell with remaining-life encoding only (exit instant = settlement − 120d; stock at that instant):

```bash
pnpm schwab option price --symbol 'IREN  270115C00055000' \
  --mode sell --dte 120 --expected-spot 40
```

## Output (sketch)

**`theoretical`:**

```json
{
  "contract": { "occ": "...", "underlying": "IREN", "expiry": "2027-01-15", "strike": 55, "putCall": "CALL" },
  "schwab": { "mark": 0.42, "bid": 0.38, "ask": 0.46, "volatility": 103.12 },
  "timeToExpiry": { "years": 0.54, "minutes": 283680 },
  "inputs": {
    "spot": { "value": 25.37, "from": "schwab-quote" },
    "vol": { "value": 102.76, "from": "mark-implied" },
    "rate": { "value": 4.22, "from": "treasury-gov" }
  },
  "results": {
    "theoretical": {
      "ours": { "model": "leisen-reimer", "value": 0.42, "greeks": {} },
      "crossCheck": { "ivGapVolPts": -0.36, "ourValueAtSchwabIv": 0.43, "vsMark": 0.01, "vsSchwabTheoretical": 0.0 }
    }
  }
}
```

**`both`:** shared **`contract`**, **`schwab`**, **`inputs`**; **`results.theoretical`** (with **`crossCheck`**) and **`results.expiry`** (intrinsic, **`netPnL`**, **`breakevenSpot`**, **`entry`** provenance).

Every run carries provenance on fields (`from`: `schwab-*` vs `cli`).

## Models and tests

Pricing, IV solving and greeks live in the [engine package](16-pricing-engine-package.md); the Treasury rate and the dividend projection are in [17](17-engine-rate-and-dividend-inputs.md). The CLI adds the path dependency on the engine to `tools/schwab/pyproject.toml`. This issue owns orchestration, the Schwab fetch and the JSON shape.

- **American** equity/ETF: finite-difference cash-drop with discrete dividends ([ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md)); the Leisen–Reimer cross-check is inside the engine's tests.
- **European** index (XSP, SPXW): per [ADR 0001](../../../docs/adr/0001-own-pricing-model.md).
- Engine oracles (Haug BSM, closed-form fractional T, CRR reference) are in 16. Here: tests on a fixed quote fixture that assert the JSON shape and provenance.
- Schwab cross-check: cents tolerance; document near ex-div and long-dated gaps.

## Implementation phases

1. Spec + OCC parse + remaining-life math through the engine's virtual clock (tests, no network).
2. **`expiry`** + **`sell`** modes + **`--entry`** + **`breakevenSpot`** on **`expiry`** only.
3. Live orchestration (always fetch quote, chain, and the underlying's fundamentals) + JSON shape + `crossCheck`.
4. Path B (compose flags → OCC), README.

## Open decisions

- Path B OCC resolution: chain-first vs local formatter (implementer choice, phase 4).

## Prototype pointer

Schwab `/chains` ANALYTICAL probe and verdict: branch `prototype/schwab-analytical-chain` (commit 7e4964f), `tools/schwab/prototype/ANALYTICAL_CHAIN_VERDICT.md`. Relevant here: overrides work for one expiry per call only, vol is flat, and Schwab's IV, theoretical value and mark did not reproduce each other in a Saturday SPY snapshot. Re-run in market hours before using Schwab's side-by-side as a tolerance reference.

QuantLib engine spike and verdict: branch `prototype/quantlib-engine` (commit eaefea7), `tools/schwab/prototype/quantlib-engine/VERDICT.md`. Go; the engine is a Python package the CLI imports and the server runs as a worker ([ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md), built in [16](16-pricing-engine-package.md)). Exact minutes to the settlement instant passed on the virtual clock.
