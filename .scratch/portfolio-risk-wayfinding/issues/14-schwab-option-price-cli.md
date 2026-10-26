# `schwab option price` CLI

Type: task
Status: ready-for-agent

Blocked by: none. [16](16-pricing-engine-package.md), [17](17-engine-rate-and-dividend-inputs.md), [18](18-engine-worker.md) and [19](19-engine-worker-review-fixes.md) are resolved, so the engine is built (builds on [06](06-pricing-inputs-and-models.md), [ADR 0001](../../../docs/adr/0001-own-pricing-model.md) and [ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md)). Revised 2026-10-26 against what the engine actually does; see the comment at the bottom.

## Goal

Add `pnpm schwab option price` — orchestrate Schwab quotes, reprice with **our** model, optionally run expiry or pre-expiry sale P&amp;L scenarios. Live runs **always** call the API (no `--fetch` flag). Schwab mark/greeks sit beside our outputs for cross-check (tolerance, not equality).

**v1 contract identity:** Path A (`--symbol`) only. Path B is deferred (see implementation phases).

## What it adds over `schwab get`

`get` returns one raw JSON slice. This command:

- Resolves the contract (OCC on v1; composed flags → OCC later).
- Pulls option + underlying + chain fields needed for IV/rate.
- Emits structured JSON: shared **`contract`** + **`schwab`**, mode-specific **`results.*`**, provenance on inputs.
- Works out the **valuation instant** or **exit instant** from the flags and hands it to the engine, which owns **T**: the **Settlement instant** (4:00 pm ET for equity, ETF, SPXW and XSP; 9:30 am ET for AM SPX) and the calendar-minute **Remaining life** (issue 06).
- Optional **`--mode expiry`** / **`sell`** / **`both`** without hand math.

## How the CLI uses the engine

The CLI is the engine's first caller. It owns Schwab I/O, mapping Schwab payloads into engine inputs ([17](17-engine-rate-and-dividend-inputs.md) and the engine's `AGENTS.md` both leave that to callers), the instant arithmetic, the percent boundary and the JSON shape. The engine owns everything else: the Settlement instant, the virtual clock, model choice, Mark-implied IV, Greeks, flags and the residual.

**In-process, not the worker.** The CLI imports the engine ([ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md)); the worker is the server's. One contract needs no pool, and spawning the worker would cost a 0.6 s ready line and four processes for a single price. Import `pricing_engine` inside the `option price` handler, so `login` and `get` do not load QuantLib.

**Wiring.** Add `pricing-engine` to `tools/schwab/pyproject.toml` dependencies with `[tool.uv.sources] pricing-engine = { path = "../../packages/pricing-engine", editable = true }`, and regenerate `uv.lock`. Both projects are Python 3.13.

**Public names used:** `price`, `PriceRequest`, `PriceResult`, `settlement_instant`, `UnknownRootError`, `TreasuryCurves`, `project_dividends`, `parity_forward`, and from `pricing_engine.batch` `price_contract`, `BatchContract` and `Shock`. Add those last three to the engine's `__init__.py` `__all__` in this ticket; it is a one-line change and the committed schema does not move.

**Mapping from Schwab to a `PriceRequest`** (engine values are decimals; every one carries a `from` that the result echoes):

| Engine input | Source | Notes |
| --- | --- | --- |
| `contract` root, expiry, strike, right | The parsed OCC symbol | The CLI owns the parser (the engine has none). Strip the root's padding; XSP has three spaces, SPXW two. An unsupported root (NDX, RUT, VIX…) raises `UnknownRootError`; report it as a one-line error, never default it. |
| `contract.exercise` | Quote `exerciseType` (`E` or `A`) | ADR 0001: chosen per contract from `exerciseType`, never from whether the Underlying is an index. `--model` overrides. |
| `valuation` | Wall-clock now, `--as-of`, or settlement minus `--dte` | Computed in the CLI; see "Remaining life". |
| `spot` | The option quote's `underlyingPrice`, `from: schwab-option-quote` | Struck with the Mark, so the solved IV is not skewed by two snapshots. `theoretical`: today's price. `sell`: `--expected-spot`. The Underlying's own quote Mark is shown in the `schwab` block. |
| `mark` | The option quote's `mark`, `from: schwab-mark` | The engine solves the Mark-implied IV. |
| `volatility` | `--vol`, or the IV solved at today's inputs | A scenario never re-solves the IV at the shifted inputs; see the call plan. |
| `rate` | `TreasuryCurves(cache_dir=…).rate(valuation_date=today, expiry, fallback_percent=chain interestRate)` | `--rate` overrides, `from: cli`. The curve is read for the real now-to-expiry life and **held fixed** under `--dte` and `sell`, as the app holds it under days forward ([07](07-how-should-shocks-behave.md)). Cache on disk under `.local/schwab/` so each run starts warm. |
| `dividends`, `continuous_yield` | `project_dividends(...)` on the Underlying quote's `fundamental` block | Projected from **today** to the expiry; the engine drops any dividend before the valuation instant and flags `dividend_not_in_life`. See the decisions table for each rule. |
| `forward` | European index options: `parity_forward` from the call and put Marks at the same strike and expiry, the rate and the Remaining life | Needs the opposite right's Mark from the chain. In `sell`, the forward scales with spot, as the worker does. |
| `greeks`, `cross_check` | `greeks=True`; `cross_check=True` on American contracts only, both under `theoretical` at now | `cross_check` is the engine's own Leisen–Reimer tree. It is not Schwab's cross-check below. A batch contract refuses both, so scenarios carry neither. |

**Engine call plan.** The Mark-implied IV is always solved at **today's** inputs, so `theoretical` at now returns the Mark and a scenario starts from the app's base.

| Output | Engine calls |
| --- | --- |
| `theoretical` at now | `price(mark, greeks)` at now. |
| `theoretical --dte`, and `sell` | `price_contract(BatchContract(request with the Mark at now, [one Shock]), "absolute", Numerics())`. The Shock is `spot_move = expected_spot / spot − 1` (zero under `theoretical`), `iv_shift = 0`, and `days_forward` = days from now to the valuation or exit instant. Its first price is the answer; its `iv` and flags are echoed. |
| `crossCheck` | `price(volatility=Schwab IV ÷ 100)` at **now**, even under `--dte`, for `ourValueAtSchwabIv`. |
| Offline `theoretical` and `sell` | One `price(volatility=--vol)`; there is no Mark. |
| `expiry` | None. Intrinsic and `breakevenSpot` are closed form in the CLI. |

When the Mark has no IV (at or below intrinsic, or no bracket), `price()` returns `price: null`, `iv.reason` and `iv.residual`, and flags `no_iv`. The CLI reports that as is under `theoretical` at now. In a scenario (`sell`, `--dte`) `price_contract` carries the residual ([18](18-engine-worker.md)): the model value at σ = 0.01 plus the residual, never below zero, and plain intrinsic with no residual once the contract is past its Settlement instant. The CLI writes none of that logic. Schwab's IV is never the fallback ([ADR 0001](../../../docs/adr/0001-own-pricing-model.md)).

**Units.** Flags in and JSON out are percent (`--vol`, `--rate`, `--div-yield`, and the sketch below); everything between is the engine's decimals. Convert at the CLI boundary in one place. `--vol-unit` changes how `--vol` is read, never the output.

**Errors.** `UnknownRootError`, `TreasuryError` (no curve and no fallback), pydantic `ValidationError` and an exit instant at or after the Settlement instant each exit 1 with one line on stderr, through the `ValueError` family `cli.main` already catches. Engine `flags` (`no_iv`, `dividend_not_in_life`, `expired`, `hard_to_borrow`) go into the output next to a `warnings` list the CLI adds (rolled-forward ex-date, continuous-yield treatment, rate fallback, stale quote).

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
| **Days** | **`--dte`** | Set remaining life directly. At most the real remaining life. |
| **Date** | **`--as-of`** | Set the **exit instant** ( **`sell`** ) or **valuation instant** ( **`theoretical`** ); **T** = settlement − that instant. |

**If both are set, `--dte` wins** — the date does not also define **T**. The winning encoding is used everywhere the model needs remaining life.

**What the CLI hands the engine** is one timezone-aware `valuation` instant, because `price()` measures life from it to the Settlement instant. `--dte N` gives `valuation = settlement_instant(root, expiry) − N days` (fractions allowed). A date `--as-of` has no time of day, so it means **4:00 pm ET** that day (recommended; a full ISO datetime with an offset is also accepted). Default is the wall clock now. The engine counts calendar seconds in UTC, so a daylight saving change between the valuation and the expiry is already right. `--dte` may not exceed the real remaining life, because a larger one puts the valuation before now. A live run errors and points to `--offline`, the same rule as a past `--as-of`. A stress with more time than the contract has left is **deferred**: use a longer-dated contract. This also means a live scenario is always zero or more days forward of now, which the worker's batch accepts.

**Dividends under a moved valuation.** The schedule is projected from today, and the engine drops any dividend whose ex-date falls before the valuation instant, with the `dividend_not_in_life` flag. In `sell` that is right: `--expected-spot` is the stock after the ex-date. Under `theoretical --dte` the spot stays at today's cum-dividend level, so the price jumps by about delta times the dividend when the stress crosses an ex-date ([18](18-engine-worker.md)'s review measured 5.41 to 6.47 on a $2 dividend). The flag is the explanation; the CLI surfaces it.

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
| **`theoretical`** | Fair value **now** (live) or at **`--offline`** valuation instant. | Yes — the engine |
| **`expiry`** | **Hold to expiration:** intrinsic if stock = **`--expected-spot`** at expiry. | No — intrinsic only |
| **`sell`** | **Sell before expiration:** model value at **exit instant** if stock = **`--expected-spot`** then; sale P&amp;L vs **Entry**. | Yes — the engine, at exit |
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

**Output:** **`saleProceeds`** (our value per share at exit) and **net P&amp;L** = proceeds − **Entry**. **No Greeks at exit in v1**: the worker's batch returns prices only, and [20](20-engine-greeks-at-a-scenario-point.md) adds them to the engine. **No `breakevenSpot` in v1** (inverse solve deferred).

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
| `--offline` | Optional | No API and no Treasury fetch; need inputs below for **`theoretical`** / **`sell`**. Also needs **`--model`** (there is no `exerciseType` to read), and dividends default to none unless **`--div-yield`** is given, noted in `warnings`. |
| `--spot` | **If `--offline`** (`theoretical`) | S₀ at valuation; live fills from quote. |
| `--vol` | **If `--offline`** (`theoretical` / `sell`) | σ override; live default **Mark-implied IV**. |
| `--vol-unit` | Optional | `percent` (default) or `decimal`. Reads `--vol` only; output is always percent. |
| `--rate` | **If `--offline`** (`theoretical` / `sell`) | % override; live default Treasury curve at the expiry. |
| `--dte` | Optional | Remaining life, at most the real one (larger is an error live); wins over date encoding. |
| `--as-of` | Optional | **`theoretical`:** valuation instant (live: **now** only); **`sell`:** exit date (default now ET). |
| `--expected-spot` | **If `expiry`, `sell`, or `both`** | See table above. |
| `--entry` | Optional | P&amp;L **Entry** per share; **live default = Schwab mark**. |
| `--contracts` | Optional | Count for dollars (default 1, ×100). |
| `--mode` | Optional | `theoretical` \| `expiry` \| `sell` \| `both` (default `theoretical`). |
| `--model` | Optional (**required with `--offline`**) | `auto` \| `american` \| `european` (default `auto`). `auto` reads the quote's `exerciseType`; an override is for what-ifs. This sets the exercise style, not the engine's numerical model: the engine picks closed form, finite-difference cash drop or Black-Scholes-Merton itself and reports it as `ours.model`. |
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
| **Dividends** | **`theoretical`** / **`sell`:** discrete cash dividends in v1. With `divFreq` 4, the schedule comes from `nextDivExDate` and `divPayAmount`, projected every 3 months to expiry, and the JSON names the projection rule. `divFreq` 0 with `divYield` above 0 (SATA's case): continuous yield from `divYield` (percent), a warning, and `divTreatment: "continuous-yield"`. All dividend fields zero: none. **`expiry`:** ignores div flags. The CLI maps each `project_dividends` rule: `quarterly-from-next-ex-date` is discrete (`rolled_forward` adds a warning); `needs-continuous-yield` is the SATA case above; `none` and `none-before-expiry` are none, and the JSON names which; `unsupported-frequency` and `missing-ex-date` are an **error** that names the rule and points at `--no-div` or `--div-yield`, because a silent zero dividend misprices a call. `--div-yield` replaces any schedule; `--no-div` forces none. |
| **Rate** | Treasury.gov daily par curve interpolated to the expiry, continuous compounding, `from: "treasury-gov"`. Schwab's chain `interestRate` (about 4.03, root only, source unknown) sat below every Treasury tenor on 2026-10-23 (4.07 at 1 month in continuous terms), so it is a flagged fallback and a `crossCheck` field. It is also not the rate behind Schwab's default `theoreticalOptionValue`: on SPX, SPXW and XSP that value implies a flat 0.04% at every expiry, while `strategy=ANALYTICAL` honours the rate it is given ([schwab-implied-rate.md](../../../docs/research/schwab-implied-rate.md)). |
| **Engine** | Python package ([16](16-pricing-engine-package.md) core, [17](17-engine-rate-and-dividend-inputs.md) rate and dividends, [18](18-engine-worker.md) worker, [ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md)); the CLI imports it and calls `price()` in-process. It does not spawn the worker, which is the server's. Exact minutes to the **Settlement instant** come from the engine, not from CLI code. See "How the CLI uses the engine". |
| **Cross-check** | `crossCheck`: IV gap in vol points (ours minus Schwab IV), our value at Schwab IV (`ourValueAtSchwabIv`, the engine priced at Schwab's `volatility` ÷ 100), and the differences `vsMark` (our value minus the **Mark**) and `vsSchwabAnalytical` (`ourValueAtSchwabIv` minus Schwab's `ANALYTICAL` value, since both sit on Schwab's IV and our rate). Tolerance, not equality. The `ANALYTICAL` value comes from one extra `/chains` call (`strategy=ANALYTICAL`, one expiry, `fromDate` and `toDate` set to it) passing our inputs: `interestRate` (percent) from our rate quote, `underlyingPrice` as our spot, `volatility` as Schwab's contract IV, and `daysToExpiration`. That puts Schwab's formula on the same rate and IV as ours, so the difference is the model, the time convention and the dividend treatment. Schwab's default `theoreticalOptionValue` is shown beside it as `schwabDefaultTheoretical` and is **never** the tolerance reference: it uses about 0.04% on index options, so a 249-day SPX option differs from a 4% price by about $100. The `ANALYTICAL` call's `daysToExpiration` is always the **real** remaining life (calendar days from now to the expiry), never `--dte`. A `--dte` stress changes our price but not the cross-check, which compares at today's inputs. |
| **`--spot`** | **`theoretical`** only. **`sell`** uses **`--expected-spot`** at exit instant. |
| **Past valuation or exit** | A live **`theoretical`** or **`sell`** whose valuation or exit instant is before now (a past **`--as-of`**, or **`--dte`** larger than the real remaining life) is an **error** that points to **`--offline`**. One rule for both modes. A `--dte` stress beyond the real remaining life is deferred (2026-10-26). |
| **Scenario path** | Live **`sell`** and **`theoretical --dte`** call the worker's `batch.price_contract` in-process with one Shock, so the CLI and the app share the Shock semantics: IV solved once at today's inputs, spot and forward scaled, the residual carried, `expired` and `dividend_not_in_life` flagged. The CLI passes the single-price numerics (100 by 200), not the grid's 50 by 100. |
| **Greeks** | **`theoretical`** at now only: ours (engine, bump-and-reprice) beside Schwab's. None under `sell` or `--dte` in v1; [20](20-engine-greeks-at-a-scenario-point.md) adds them. Greeks are an output and never an input to the model. |
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
  "schwab": { "mark": 0.42, "bid": 0.38, "ask": 0.46, "volatility": 103.12, "quoteTime": "2026-10-26T15:12:03Z", "greeks": { "delta": 0.31, "gamma": 0.02, "theta": -0.05, "vega": 0.07, "rho": 0.03 } },
  "timeToExpiry": { "years": 0.54, "minutes": 283680, "settlementInstant": "2027-01-15T21:00:00Z" },
  "inputs": {
    "spot": { "value": 25.37, "from": "schwab-quote" },
    "vol": { "value": 102.76, "from": "mark-implied IV from schwab-mark" },
    "rate": { "value": 4.22, "from": "treasury-gov", "curveDate": "2026-10-23" },
    "dividends": { "treatment": "none", "rule": "none" }
  },
  "results": {
    "theoretical": {
      "ours": { "model": "american_closed_form", "value": 0.42, "greeks": { "delta": 0.31, "gamma": 0.02, "theta": -0.05, "vega": 0.07, "rho": 0.03 }, "leisenReimerCheck": null },
      "crossCheck": { "ivGapVolPts": -0.36, "ourValueAtSchwabIv": 0.43, "vsMark": 0.01, "vsSchwabAnalytical": 0.0, "schwabDefaultTheoretical": 0.42 }
    }
  },
  "flags": [],
  "warnings": []
}
```

`ours.model` is the engine's name (`black_scholes_merton`, `american_closed_form`, `american_fd_cash_drop`; `intrinsic` only past expiry). `leisenReimerCheck` is the engine's tree price and its difference from ours, and is set only on American contracts. Greeks are per share: vega per vol point, theta per calendar day, rho per percentage point of rate. Check Schwab's own units against [observations.md](../../../docs/schwab/observations.md) before showing them side by side. When the Mark has no IV, `ours.value` is `null` and `ours.iv` carries `reason` and `residual`. `rate.value` is the continuous rate, in percent.

**`both`:** shared **`contract`**, **`schwab`**, **`inputs`**; **`results.theoretical`** (with **`crossCheck`**) and **`results.expiry`** (intrinsic, **`netPnL`**, **`breakevenSpot`**, **`entry`** provenance).

Every run carries provenance on fields (`from`: `schwab-*` vs `cli`).

## Models and tests

Pricing, IV solving and greeks live in the [engine package](16-pricing-engine-package.md); the Treasury rate and the dividend projection are in [17](17-engine-rate-and-dividend-inputs.md). This issue owns orchestration, the Schwab fetch, the payload mapping and the JSON shape, and adds no model code.

- **American** equity/ETF: the engine's finite-difference cash drop with discrete dividends, or its closed form for a call on a non-dividend payer ([ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md)). **European** index (XSP, SPXW): Black-Scholes-Merton on the parity forward ([ADR 0001](../../../docs/adr/0001-own-pricing-model.md)). The CLI does not choose between them; it passes `exerciseType`.
- **Do not mock the engine.** QuantLib is a normal dependency and the engine needs no network, so CLI tests run the real `price()`. Fake the two seams instead: `schwab_get` (a fixed quote, chain and fundamentals fixture) and `TreasuryCurves(fetch=…)` (the engine's saved 2026-10 XML). The engine's oracles (Haug, closed-form fractional T, CRR) stay in 16; the CLI's tests assert orchestration:
  - `theoretical` at now reproduces the Mark, so the Mark-implied IV is the one the CLI passed;
  - the JSON shape and the `from` provenance on every input, including `curveDate`;
  - the percent boundary, with `--vol 100` and `--vol 1 --vol-unit decimal` equal, and output in percent;
  - the instant arithmetic: `--dte` against `--as-of`, `--dte` winning when both are set, a date meaning 4:00 pm ET, and the 2026-11-01 daylight saving fall-back;
  - **the scenario glue**, since `price_contract` does the pricing: `sell` with exit now and `--expected-spot` equal to the spot reproduces `theoretical` at now; `days_forward` and `spot_move` are computed right across a daylight saving change; a European index option's forward scales with spot; a Mark below intrinsic returns the residual-carried price with `no_iv`; and a `--dte` larger than the real remaining life errors;
  - the dividend rules, each mapped as the decisions table says, and the unsupported ones erroring;
  - `expiry` and `breakevenSpot` closed form, with no engine call.
- Schwab cross-check: cents tolerance against the `ANALYTICAL` value (see the decisions table); document near ex-div and long-dated gaps. The engine's own comparison found Schwab's IV 0.7 to 0.8 vol point above ours on long-dated IREN calls, cause unknown, and noisier short-dated, low-priced options; dividend-paying American options are untested ([16](16-pricing-engine-package.md), the engine's `AGENTS.md` "Against Schwab's values"). Not yet verified: that `ANALYTICAL` on an equity or ETF behaves like Black-Scholes in the passed rate (only SPX was checked, by put-call parity), and the 1 to 1.3 day shortfall in Schwab's life found on IREN calls ([pricing-engine-vs-schwab-iren.md](../../../docs/research/pricing-engine-vs-schwab-iren.md)). Expect a time-convention gap on short-dated options until that is explained. The live rerun ([15](15-rerun-analytical-probe-in-market-hours.md), 2026-10-26) confirmed that `ANALYTICAL` honours a passed `interestRate`, so it is the right reference, and that Schwab's IV sits 1.5 to 2 vol points below the IV of its own Mark on SPY, SPX and XSP, with jumps between adjacent strikes. Expect `ivGapVolPts` of that size, and keep `vsSchwabAnalytical` informational, not a pass-or-fail assertion; its tolerance can be set once real runs show the spread.
- First real use of the engine on **European index options on a parity forward**, which [ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md) lists as untested. The live run on SPX or XSP in phase 3 records the derived forward against the index and the Mark reproduced, in the Answer.

## Implementation phases

1. Dependency wiring, OCC parse, and the valuation-instant arithmetic from `--as-of` and `--dte`, checked against the engine's `settlement_instant` (tests, no network). The engine does the virtual clock; the CLI computes only the instant.
2. **`--offline`** `theoretical`, **`expiry`** and **`sell`**, with **`--entry`** and **`breakevenSpot`** on **`expiry`** only. Offline has no Mark, so it is one `price(volatility=--vol)` at the exit valuation and spot; the live scenario path through `price_contract` arrives with phase 3. These need no Schwab call and no Treasury fetch.
3. Live orchestration: option quote, Underlying quote with fundamentals, one chain call for the expiry (root `interestRate`, and the opposite right's Mark for the parity forward), `TreasuryCurves` with a disk cache, dividend mapping, JSON shape with provenance, greeks and the Schwab block. Then `crossCheck` with the `ANALYTICAL` call last, since it needs our rate and Schwab's IV. Run it live on an equity, an ETF with dividends and an index.
4. Path B (compose flags → OCC), README.

## Open decisions

- Path B OCC resolution: chain-first vs local formatter (implementer choice, phase 4).

Settled 2026-10-26, see the last comment: a date `--as-of` is 4:00 pm ET; "now" is the wall clock with a stale-quote warning past 30 minutes; spot is the option quote's `underlyingPrice`; no `--borrow-rate` in v1 (the engine takes a `borrow_rate` and a `hard_to_borrow` flag, defaulting to none, so add the flag when a held name needs it); an offline European option prices on `--spot` and `--div-yield` with a warning, and a `--forward` flag waits until an offline index run is wanted.

## How this is built and verified

- **Branch.** `feat/schwab-option-price-cli`, in the worktree `../investor-basecamp-worktrees/feat-schwab-option-price-cli`, off master. It includes the engine's three-name `__init__.py` export. Nothing merges into master until the user says so explicitly.
- **No review stop between phases.** Phases 1 to 3 run through, including the live checks below, and the Answer reports the whole branch at once.
- **Live checks** (read-only GETs, a few dozen calls, nothing near the order endpoints, [ADR 0004](../../../docs/adr/0004-no-order-placing-code.md)). The contracts are picked from the live chain and named in the Answer: an equity call (IREN), an American option on a dividend-paying ETF (SPY), and a European index option (XSP or SPXW). Each passes when:
  - `theoretical` at now reproduces the Mark (by construction, so it checks the wiring);
  - `sell` with exit now and `--expected-spot` equal to the spot equals `theoretical`;
  - for the index, the parity forward is within a few cents of the index level, and the dividend rule is named;
  - `crossCheck` runs against the `ANALYTICAL` call and the gaps are recorded, not asserted (see the cross-check notes above).
- **Fixtures.** Trimmed live responses (option quote, Underlying quote with fundamentals, chain slice, `ANALYTICAL` slice), run through the existing redaction, committed under `tools/schwab/tests/fixtures/`. The Schwab-side tests replay them offline.
- **If live disagrees with the plan.** A CLI cause (mapping, units, instants) is fixed on the branch. An engine or model cause (a price, the forward, the IV) is not changed here: stop and report with the numbers.

## Prototype pointer

Schwab `/chains` ANALYTICAL probe and verdict: branch `prototype/schwab-analytical-chain` (commit 7e4964f), `tools/schwab/prototype/ANALYTICAL_CHAIN_VERDICT.md`. Relevant here: overrides work for one expiry per call only, vol is flat, and Schwab's IV, theoretical value and mark did not reproduce each other in a Saturday SPY snapshot. The market-hours rerun ([15](15-rerun-analytical-probe-in-market-hours.md), resolved 2026-10-26) kept every finding: the gaps persist on live quotes, the default theoretical still implies about 0.04% on SPX and XSP, and `ANALYTICAL` honours a passed rate.

QuantLib engine spike and verdict: branch `prototype/quantlib-engine` (commit eaefea7), `tools/schwab/prototype/quantlib-engine/VERDICT.md`. Go; the engine is a Python package the CLI imports and the server runs as a worker ([ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md), built in [16](16-pricing-engine-package.md)). Exact minutes to the settlement instant passed on the virtual clock.

## Comments

**Revised 2026-10-26, after the engine landed ([16](16-pricing-engine-package.md) to [19](19-engine-worker-review-fixes.md)).** The ticket was written before the engine existed. What changed:

- **Unblocked.** 16 and 17 are resolved, and 18 and 19 too.
- **In-process, not the worker.** The CLI imports `price()`; the worker is the server's. New section "How the CLI uses the engine" holds the Schwab-to-engine mapping, the call plan per mode and the percent boundary.
- **Stale statements fixed.** "BS / LR" as the model (Leisen–Reimer is only the engine's cross-check tree, and the model name is `american_closed_form`, `american_fd_cash_drop` or `black_scholes_merton`); "remaining-life math through the engine's virtual clock" (the CLI computes only the valuation instant); `ours.model: "leisen-reimer"` in the sketch.
- **Gaps closed.** European index options need the opposite right's Mark for the parity forward, so the chain call is required, not optional. `--model auto` reads `exerciseType`, so `--offline` must pass `--model`. Offline has no fundamentals, so dividends default to none with a warning. The two dividend rules the ticket never named (`unsupported-frequency`, `missing-ex-date`) are errors. The Mark-implied IV is solved at today's inputs and never re-solved for a scenario. A Mark with no IV is reported as `null` plus the residual, and carried in scenarios as the worker does. A date `--as-of` has a time of day. `vsSchwabAnalytical` compares at Schwab's IV, matching what the `ANALYTICAL` call was given.
- **Not changed.** Flags, modes, `--entry` semantics and Path A scope are as agreed in the grill.

**Decided 2026-10-26, after discussing the revision:**

- **A `--dte` larger than the real remaining life is deferred.** It was in the original grill as a theoretical stress, but a longer-dated contract answers "what if there were more time" better. Live runs now have one rule for both modes: no valuation or exit instant before now.
- **Scenarios reuse the worker's `price_contract`** with one Shock, so the CLI and the app agree by construction and the CLI repeats no shock logic. This replaces the earlier plan of a CLI-side two-call path with a parity test, which was only needed for the past-life stress.
- **No Greeks at the exit instant in v1.** The batch returns prices only. Greeks stay on `theoretical` at now, with Schwab's beside them. [20](20-engine-greeks-at-a-scenario-point.md) adds Greeks at a scenario point to the engine.
- **Ticket 15 is resolved**, so its findings are folded into the cross-check notes above.

**Decided 2026-10-26, grilling before implementation:**

- **A date `--as-of` means 4:00 pm ET.**
- **Valuation clock.** Now is the wall clock. The JSON echoes `quoteTime`, and a stale-quote warning appears when the quote is more than 30 minutes old (always true when the market is closed).
- **Spot source.** The option quote's `underlyingPrice`, `from: schwab-option-quote`. The Underlying's own price is shown in the `schwab` block.
- **Left out of v1.** `--borrow-rate`, and a `--forward` flag for offline European options.
- **Build and verification.** See "How this is built and verified": a branch and worktree, no review stop between phases, live checks run by the implementer, real trimmed fixtures, and engine behaviour left unchanged.

## Answer: phases 1 to 3

Built on branch `feat/schwab-option-price-cli` (worktree `../investor-basecamp-worktrees/feat-schwab-option-price-cli`), not merged. Phase 4 (Path B, flags to OCC) is still open; the README section is done.

**What was built.** `tools/schwab/src/schwab_cli/`: `occ.py` (parser), `instants.py` (valuation and exit instant), `schwab_inputs.py` (the read-only GETs and the Schwab-to-engine mapping), `option_price.py` (modes, the engine call plan, JSON), and the `option price` subcommand in `cli.py`, which imports the engine only inside its handler (a test proves `login` and `get` never load QuantLib). The engine's `__init__.py` now exports `price_contract`, `BatchContract` and `Shock`; the schema did not move. 100 tests in `tools/schwab/tests/` run the real engine with `schwab_get` and `TreasuryCurves(fetch=…)` faked from live fixtures under `tests/fixtures/option_price/`.

**Live verification, 2026-10-26 about 10:45 to 11:00 ET, all GETs.** Contracts: `IREN  270115C00025000` (American equity call, no dividends), `SPY   270115C00765000` (American, one quarterly dividend), `XSP   261218C00768000` and `SPXW  261218C07700000` (European index calls).

| Check | IREN | SPY | XSP |
| --- | --- | --- | --- |
| `theoretical` reproduces the Mark | 4.9000000000 vs 4.9 | 25.3000000000 vs 25.3 | 19.4999999999 vs 19.5 |
| Model chosen | `american_closed_form` | `american_fd_cash_drop`, rule `quarterly-from-next-ex-date`, 1 dividend | `black_76`, rule `none`, `in-parity-forward` |
| `sell`, exit now, `--expected-spot` at the spot | proceeds minus Mark −0.027232 vs delta × spot move −0.027221 | −0.008429 vs −0.008428 | −0.011037 vs −0.011039 |
| Mark-implied IV vs Schwab IV (vol points) | 102.5 vs 100.3 (+2.1) | 15.2 vs 12.9 (+2.3) | 14.7 vs 12.8 (+1.9) |
| `vsSchwabAnalytical` (ours at Schwab's IV minus Schwab's value) | +0.0015 on 4.80 | −0.073 on 22.0 | −0.55 on 17.9 |

`sell` could not be checked for exact equality live, because the spot ticks between two runs. The check above uses the run's own Mark and spot, and agrees to about 1e-5. Exact equality is a fixture test.

**Findings to read.**
- **The ticket's index forward check was mis-stated.** It said the parity forward would be "within a few cents of the index level". A forward is above the index by the carry. XSP: forward 772.50 against index 768.94, implied dividend yield about 0.88% at the Treasury rate. SPXW: 7724.95 against 7688.88. Both are plausible, and the index and its Mark are reproduced; what the plan should have said is "forward near spot × e^((r − q)T) with q near the index yield".
- **`ANALYTICAL` on an index disagrees with us by more than on equities** (XSP −0.55, SPXW −5.3 on about 160). The chain reports `dividendYield: 0.0`, and Schwab's formula has no parity forward, so it probably prices a European index option on spot alone; this was not isolated. On the American equity (IREN) the two agree to a quarter of a cent. SPY is 7 cents low, and whether that is the discrete dividend, the time convention or the model was not isolated either (ticket 15 and `docs/research/pricing-engine-vs-schwab-iren.md` are the open threads). The CLI only reports the gap.
- **The `strike` filter is ignored with `strategy=ANALYTICAL`:** the call returns every strike of the expiry, so the CLI picks its row by symbol.
- **The forward uses the chain's call and put Marks from one response,** not the option quote's Mark and the chain's opposite Mark, which are two snapshots.
- `vsMark` is `ourValueAtSchwabIv − Mark` (the sketch's numbers imply it; our own value is the Mark by construction).

**Error paths run live:** NDX fails before any network call; a symbol with no quote says to check the OCC symbol; `--dte 400` and a past `--as-of` point at `--offline`; a live `--as-of` on `theoretical` points at `--dte`, `sell` and `--offline`.

**Left alone.** No engine price changed. One bug was found and fixed in my own code by a test: `settlement − timedelta(days=n)` on a New York datetime is wall-clock arithmetic and is an hour off across the 2026-11-01 fall-back, so the settlement is converted to UTC first.
