# Roundtrip chart v2: both expiries on one chart, and builds of your own

Status: built 2026-10-27 (see "v2 built" in `spec.md`), settled by grilling the same day. Builds on `spec.md` (v1, built in this worktree). Still a throwaway research prototype for IREN: it answers "which build should I put on", lives in this worktree, and is never merged as a feature.

Terms (all in `GLOSSARY.md`): **Build**, **Sleeve**, **Leg**, **Price Path**, **Action**, **Quote Set**.

## Why v1 cannot do it

v1 is organised around a **programme**. `27` (Jan 2028 options) and `28` (Jan 2029 options) are separate worlds, each with its own JSON file, build list (legs are roles like `atm` resolved through `ROLE[prog]` and `EXPCODE[prog]` in `roundtrip_report.py`), timeline, exits and path weights. The yellow-strip toggle swaps the whole page, so a Jan 2028 build and a Jan 2029 build cannot share a chart, and a mixed build cannot exist. Builds are fixed, and prices are frozen at 2026-10-26.

## The redesign in one line

**Put the expiry on each Leg instead of on the page, and price everything live.** A Build is Sleeves (any expiry, any strike) plus shares. A Price Path is a standalone preset of dated prices, each with an Action. Any Build runs on any Price Path, priced from a Quote Set taken today.

## Decisions

### Builds

- A **Build** is a name, an optional description, a **budget** (whole dollars, at least $1,000, default $10,000) and Sleeves. Shares take whatever the Sleeves don't use. Returns are on the Build's own budget.
- A **Sleeve** is a number of identical contracts bought together: one call, or one spread (two Legs). You size it in contracts; the page shows its $ cost and share of budget.
- Any expiry from Jun 2027 onward, any listed strike. One Build may mix Jan 2028 and Jan 2029 Legs.
- Every Build can be edited and deleted, including the seeded v1 ones. No restore feature.
- No `style` column. The list is one list sorted by Expected; seeded builds carry their v1 style in the description (for example "Return-heavy. v1 stored build.").
- Each card shows an expiry badge (Jan 2028, Jan 2029, Mixed), **Expected** and **On loaded path**. The fixed Bear / Base / Bull columns go, since those paths can be renamed or deleted.
- A Build that can't be priced today (a Leg expired or no longer listed, or cost above its budget) stays in the list, greyed, with the reason ("Jun 2027 $40 call expired", "over budget by $1,240"), and is not run.

### Price Paths and Actions

- A **Price Path** is a name, an optional description, a **weight**, and dated points. Each point has a price and an **Action**: Hold, Sell X% → cash, or Sell X% → shares (X chosen from a second select).
- Price Paths are independent. They change only when you edit one on purpose.
- A path starts at today's IREN price; its targets stay fixed dollar levels. Points dated before today are kept but skipped.
- **Expected** is the weighted average of a Build's result over every path with weight above 0, the weights scaled to 100%. New paths start at weight 0.
- **Seeded paths (11):** the seven thesis paths with v1's headline rules as Actions (Hold until 2028, then Sell 50% → cash on 2028-06-30 and Sell 100% → cash on 2028-11-30), plus a "sell half" copy of each of the four round-trip paths that adds Sell 50% → cash on the date the path reaches $85. Thesis weights: Base 45, Bull 20, and 7 for each of the five bear-type paths. All can be edited or deleted.

### How Actions and expiries move money

- **Sell X%** sells X% of what is left in each option Sleeve, rounded half up to whole contracts (50% of 1 sells 1, 50% of 3 sells 2, 25% of 1 sells 0). Shares are never sold by an Action. The event marker shows how many contracts sold.
- **→ cash:** the money sits at 0% to the end and counts in the final total. **→ shares:** it buys shares at that point's price; the unsold options stay.
- **Expiry:** a Leg still held is sold on the last trading day before its expiry (2028-01-20 for Jan 2028) at model value, and the money buys shares that day.
- **Debt payment:** unchanged from v1. The 0 / 10 / 25 / 50% toggle takes that share of the gain over the Build's budget on 2027-11-30, from cash first, then calls (highest leverage first), then shares.
- **Puts:** gone. v1's sale rules and 2028 exits are replaced by Actions.

### Builds and paths together

- A Build can be linked to Price Paths through a join table. For now the app allows one link per Build: the path loaded by default when you select that Build. Any path can still be loaded onto any Build by hand.
- Selecting a Build loads its default path; with no default, the current path stays loaded.
- Views A (legs over time) and B (outcome by path) show one Build. Compare shows the focused Build against one other, both on the loaded path. That is how a Jan 2028 Build and a Jan 2029 Build share a chart.
- If the two Builds in Compare have different budgets, Compare switches to %; $ stays available with a "budgets differ" note. The all-shares line uses the focused Build's budget.

### Pricing

- Nothing about prices is stored. When the page first loads, the server takes one **Quote Set**: a live quote for every contract any Build uses, throttled, never `--offline`. It holds the Quote Set and the engine results in memory. "Re-quote now" takes a new one; a server restart does too. The yellow strip shows "Priced 2026-10-27 14:05 · IREN $27.37".
- Entry: ask for long Legs, bid for short Legs. (A mid toggle may come later.)
- Path weights are 35/45/20 for every Build, judged to Jan 2029.

## Page layout

- **Yellow strip:** the programme toggle goes. It shows the Quote Set time and spot, "Re-quote now", the debt toggle and $/%.
- **Left column:** every Build, sorted by Expected, with "+ New build"; each card has edit and delete.
- **Selection area** (right column, under the legend, where v1 has empty space): the list of Price Paths. Each row has the name, a pencil and a trash can; "+ New path" sits below. The unsaved copy, if any, sits at the top with Save and Discard. Deleting confirms in the page (no `confirm()`).
- **Edit area** (under the chart, replacing v1's "Price points" panel): one row per point with date, price, Action and %, for the loaded path. Changing a point makes an unsaved copy ("Unsaved · from Base") and leaves the preset alone; Save names it and adds it to the list. The pencil on a preset edits that preset in place, and Save overwrites it. Only one unsaved copy exists at a time, and switching Builds keeps it.
- **Builder panel** (from "+ New build" or edit): name, description, budget, default path, and Sleeve rows. Each row has a type (call or call spread), an expiry and strike(s) from the live chain, and contracts. Each row shows cost per contract, total, and share of budget with the bid/ask spread (warning above 10%). Shares fill the rest live, and Save is blocked above budget.

## Data: SQLite (Drizzle)

In `src/db/schema/roundtrip.ts`, exported from the barrel. Throwing the prototype away means dropping the `rt_` tables.

| Table | Columns |
| --- | --- |
| `rt_build` | id, name, description (null), budget (int, default 10000), created_at, updated_at |
| `rt_sleeve` | id, build_id → `rt_build` (cascade), position, contracts |
| `rt_leg` | sleeve_id → `rt_sleeve` (cascade), expiry, strike, kind C/P, side +1/−1; PK (sleeve_id, expiry, strike, kind) |
| `rt_path` | id, name, description (null), weight, created_at, updated_at |
| `rt_path_point` | path_id → `rt_path` (cascade), date, price, action `hold`/`sell_cash`/`sell_shares`, sell_pct (null for hold); PK (path_id, date) |
| `rt_build_path` | build_id → `rt_build` (cascade), path_id → `rt_path` (cascade); PK (build_id, path_id). The app keeps one row per build for now. |

Legs are keyed by expiry, strike and kind rather than an OCC symbol, so a Build carries over to any day's Quote Set. A seed runs on first use: v1's featured and frontier builds from both programmes, and the 11 paths.

The Python engine never touches the database. A server function reads the rows, passes the Build, the path and the Quote Set to the engine as JSON, and keeps the result in memory.

## Steps

1. **Engine rework** (`roundtrip_report.py` and the trace in `export_chart_data.py`): Legs carry their contract, per-Leg expiry with the day-before sale into shares, Actions on path points, per-Build budget, debt rule as v1, no puts, all prices through the batch pricing worker. Input and output are JSON on stdin and stdout.
2. **Regression check** (a pytest test). It reads the 2026-10-26 quote JSON files in `scenarios/iren/data`. Each v1 policy without puts is expressed as Actions on each v1 path, and the test reproduces every matching v1 run within $25 on $10k, plus the `spec.md` figures (+674% expected, +36% bear, and the rest). The to-the-dollar leg-sum check stays. **Nothing else starts until this passes.**
3. **`pnpm schwab option chain --symbol IREN`** (read-only, live only, with tests per that tool's AGENTS.md). It feeds the builder's expiry and strike selects and the Quote Set.
4. **Schema, migration and seed**, plus the server functions: Quote Set in memory, "Re-quote now", run engine, and CRUD for Builds and paths.
5. **Page:** remove the programme toggle; build list with Expected and On loaded path; selection area and edit area with Actions; Compare on the loaded path with the budget rule.
6. **Builder panel.**
7. **Checks:** `tsc`, Oxlint, Knip, Ruff, ty, pytest. Price one hand-made Build through the page and from the command line, expecting the same numbers. Take screenshots and update `spec.md`.

## Risks

- The engine rework touches every number past results rest on; the regression check is what makes it safe.
- v1's hold exit values Legs at expiry, while v2 sells the day before at model value. The difference is small time value, which the $25 tolerance should absorb; if it doesn't, the test compares at the same date.
- Live pricing on every page load: about 25 contracts throttled is a minute or two, and needs a Schwab sign-in. Without one, nothing prices.
- Wide bid/ask on far strikes and spreads makes ask/bid entry look worse than a mid fill (about 7–10% of cost on the 25/75).
- Expected now depends on weights you can edit, so two sessions' Expected figures are only comparable with the same weights.
