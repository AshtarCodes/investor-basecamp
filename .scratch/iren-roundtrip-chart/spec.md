# IREN builds chart prototype (`/prototype/roundtrip`)

Status: built as a prototype, uncommitted on branch `prototype/roundtrip-chart` (worktree `.claude/worktrees/roundtrip-chart`). 2026-10-26.

## Goal

A throwaway route, `/prototype/roundtrip`, to *see* the builds from [`scenarios/iren/roundtrip-results.md`](../../scenarios/iren/roundtrip-results.md) instead of reading tables: step through the top contenders, pick a price path and policy, and show or hide each leg (shares, each call or spread, puts, banked proceeds) on a line chart. It refines the existing Scenario/Compare prototype (`/prototype/scenario`) and uses the real numbers from the CLI runs, not the toy Black-Scholes fixture.

## What already exists and gets reused

- Route pattern and files: `src/routes/prototype/scenario.tsx` (thin route, `validateSearch`, yellow prototype strip), `src/components/prototype/scenario/` (model + variants), `PrototypeSwitcher` (bottom bar, `←`/`→`, `?variant=`), `pnpm prototype:scenario` script.
- The ideas from variant B (risk curves) worth keeping: one line per item, a colour swatch plus an eye button per line to hide it, click a point to read it in a side panel, Compare as solid-versus-dashed overlay plus a delta column, a dashed threshold line. Its chart is hand-drawn SVG; the new one uses TanStack's library.
- UI parts: `button`, `badge`, `card`, `table`, `collapsible`, `separator` from `src/components/ui/`, and `Eye`/`EyeOff` from `lucide-react`.

## The chart library

`@tanstack/charts` 1.1.0 (npm; React peer `^18 || ^19`, so React 19 is fine). Install: `pnpm add @tanstack/charts`. From its docs:

- `defineChart({ marks, scales, tooltip, focus, ... })` builds a framework-independent definition. `<Chart definition height ariaLabel onSelect onFocusChange />` from `@tanstack/charts/react` renders it. The definition's identity is the update boundary, so memoise it on the state that changes.
- Marks used: `lineY` (long-format rows, `z` splits series, `strokeDasharray` is a static string per mark), `areaY` and `differenceY` (the gap between two paths), `ruleY` (baselines, thresholds), `dot` and `text` (event markers and labels), `barY` and `rect` (outcome view). Marks paint in array order.
- Hover: `focus: 'group-x'`, a crosshair, and a tooltip. Click: `keyedSelection` with a stable datum key, or the `onSelect` callback.
- Hiding a series needs no library feature: filter the rows passed to the mark. A fixed colour per leg keeps colours stable when others are hidden.
- Not yet verified (see the spike): a time scale, a per-series `stroke`/`strokeDasharray` accessor, a symlog scale, SSR with TanStack Start and Vite 8. The docs call parts of the API alpha; the Alpha Stability page 404s, so treat the API as moving.

## The data (the part that needs care)

The numbers come from Python (`scenarios/iren/analysis/roundtrip_report.py`), which already simulates every build, policy and path from cached live CLI prices. The app should not re-implement that engine.

**Plan: export a static JSON.** A new `scenarios/iren/analysis/export_chart_data.py` runs the existing engine and writes `scenarios/iren/data/chart-data-2026-10-26.json`; the prototype imports it. No CLI calls and no server.

- The engine needs a small change first: `simulate()` returns only totals. Add an optional trace that records, at each event date, the value of every component (shares, each call or spread sleeve, each put, banked cash, cumulative debt paid) plus the events (trigger fired, half-sale proceeds, puts bought, debt paid).
- Shape: `meta` (spot $25.70, capital, source files, dates), `paths[pathId]` (label, kind straight or round-trip, weight, spot at each date), `builds[]` (id, programme, style, contracts, shares, 200-point status, metrics), `runs["buildId|policyId|debt"][pathId]` (legs with points, events, totals).
- Size: about 12 contenders per programme, 6 policies, 4 debt shares (0%, 10%, 25%, 50%), 7 paths, about 8 legs, 4 to 6 dates: roughly 1 MB. Fine to import; trim policies if not.
- Correctness gate in the exporter: for every run, the sum of legs plus banked cash plus debt paid must equal the engine's total to the dollar, or the export fails.
- `tsconfig` has no `resolveJsonModule` and includes only `*.ts(x)`: enable it, or have the exporter also emit a typed `.ts` file.

**What the dates allow.** Existing valuations exist only on the event dates, so each line has few points:

| Programme | Dates with values for every leg |
| --- | --- |
| 28 (Jan 2029 options) | 2026-10-26 (entry), 2027-06-30, 2027-11-30, 2028-06-30, 2028-11-30 (held spreads also at expiry) |
| 27 (Jan 2028 options) | 2026-10-26, 2027-06-30, 2027-11-30, 2027-12-31 |

Jan 2029 calls were not valued on 2027-12-31. The chart shows markers at the valuation dates and says so ("straight segments are not prices in between"). **Phase 2 (optional):** add monthly dates for a real-looking line, about 1,000 more live CLI valuations (18 contracts x 7 paths x about 8 dates), roughly 13 minutes throttled. Recommend doing this after the UI shape is settled, not before.

## Views (the existing variant switcher: `←`/`→`, `?variant=`)

**A. Path lines (the main chart).** x is date, y is the account or a leg. One line per leg, a bold total line (wealth plus debt paid), a dashed "all shares" baseline, a break-even rule at $10,000 (or 0%). Event dots with labels: trigger fired, half-sale, puts bought, debt paid. Controls: path (7 pills; "all paths" draws only the total as ghost lines), policy, debt share (10, 25, 50%), y mode ($ value, $ P/L, return %). Legend rows with a swatch, an eye (show or hide), and a solo button; "show all", "hide all". Click a date to see each leg's value in the side panel.

**B. Outcome by path.** x is the seven paths, y is total return incl. debt. Grouped bars: the build against all shares. A second panel stacks the build's legs for the selected path (what each call contributed to the end), using the same hide toggles. This is where "is it worth the headache over shares" shows up as a gap.

**C. Compare two builds.** Refines the existing Compare mode: pick build X and Y (default Y = all shares). Overlay X solid and Y dashed with `differenceY` shading the gap, a delta column per leg, and the two builds' bear, base, bull and debt-paid side by side.

## Top contenders (the left rail)

- Source: the 181 constructions per programme in the engine. A contender is a build on the Pareto frontier of expected return against bear-path return for at least one policy; cap at about 12 per programme, always including all shares.
- Group by style (return-heavy, balanced, barbell-heavy, stock-heavy, baseline). Each card shows contracts and shares, expected return, bear, base, bull, expected debt, and badges: "passes 200 pts" and contract count.
- Sort toggle: expected return, bear, base-case gain over shares, expected debt. `↑`/`↓` steps through the rail.
- A programme toggle (28 first, 27 behind it). Policy picker lists hold, sell half at $85 or $103, sell half plus puts, puts only.

## State

URL search params through `validateSearch` so a view is shareable: `variant`, `programme`, `build`, `policy`, `path`, `debt`, `y`, `hidden` (comma list of leg ids). The strip at the top shows the data caveat in the same yellow band as the other prototype.

## Files

- `src/routes/prototype/roundtrip.tsx` (thin), `package.json` script `prototype:roundtrip`.
- `src/components/prototype/roundtrip/`: `model.ts` (types, formatters, colour per leg), `data.ts` (typed import of the JSON), `contenders-rail.tsx`, `leg-legend.tsx`, `variant-a-path.tsx`, `variant-b-outcome.tsx`, `variant-c-compare.tsx`.
- `scenarios/iren/analysis/export_chart_data.py` and an engine trace change.
- Prototype header comments say "PROTOTYPE (throwaway)", as in the scenario prototype.

## Steps

1. **Spike (short).** One page with three `lineY` series, a `ruleY`, dots and a hide toggle in this repo, to confirm the unverified API items above and that SSR hydrates. Decide the fallback (client-only render) here.
2. **Exporter.** Engine trace, `export_chart_data.py`, the to-the-dollar check, the JSON.
3. **Shell.** Route, search params, contender rail, selectors, strip.
4. **Variant A.** Then B, then C.
5. **Check against the report.** The page must reproduce known figures: for the return-heavy build (2 x Jan 2029 $40, 6 x $90, 1 x 25/75 spread, 134 shares) under hold, expected +674%, bear +36%, base +624%, bull +1,904%; base-path final wealth $63,393 plus $9,012 debt paid at 25%; under sell half at $85 expected +570% and bear +119%. Screenshot each variant, as for the scenario prototype.
6. **Typecheck and lint** the new files (`tsc`, Oxlint); the prototype stays uncommitted on the working tree until a variant wins.
7. **Phase 2 (optional).** Dense monthly dates; a payoff-by-spot view (P/L against stock price on a chosen date), which needs a spot ladder of about 600 new valuations.

## Decisions for the owner

1. **Programme first:** Jan 2029 only (28), with 27 behind a toggle? Recommended.
2. **Default y:** return % on $10,000, or dollars? Recommended: dollars for the total, return % for individual legs. Bull-path legs reach tens of thousands of dollars, so a single linear axis flattens the others; one path at a time keeps it readable.
3. **Dense dates now or later:** recommended later.
4. **Do you want puts drawn as legs** (their own line from purchase to the end), or only as an event dot and a cost? Recommended: legs, since you asked to see each position.

## Risks

- The library is new to this repo; the spike limits the cost of surprises.
- Sparse dates make lines look coarse; the markers and caption say what they are.
- The round-trip paths are stylised and harsher than history; the path pills label the November-peak ones as stress paths.
- Exported numbers are a snapshot at spot $25.70 on 2026-10-26; the page shows that date and does not update.

## Built (2026-10-26)

- Route `/prototype/roundtrip` (`pnpm prototype:roundtrip`), three variants on the bottom bar (`←`/`→`, `?variant=A|B|C`): **A** legs over time, **B** outcome by path, **C** compare two builds. Screenshots: `a-legs-over-time.png`, `b-outcome-by-path.png`, `c-compare-builds.png`.
- Both axis units, toggled in the yellow strip: dollars and return %. In dollars each line is the leg's holdings, banked proceeds and cumulative debt are their own lines, and the total includes debt paid. In return % each line is the return on one share or contract against its entry cost, as if held.
- Data: `scenarios/iren/analysis/export_chart_data.py` writes `scenarios/iren/data/chart-data-{27,28}-2026-10-26.json` (13 builds, 6 policies, debt 0/10/25/50%, 7 paths per programme). Every run is checked against the engine's `simulate()`: legs plus banked cash plus debt paid equal its total, and the per-leg contributions equal total minus $10,000 (all 624 runs pass).
- Library notes from the spike: `@tanstack/charts` 1.1.0; `scaleUtc` needs `d3-scale` (added); a dynamic mark list needs a loose type (`ChartMark<any, any, any>[]`) because the library infers types from literal tuples; event dots and labels use `decorative()` so they do not become hover points; one `lineY` per leg with a constant `stroke` keeps colours stable when legs are hidden.
- `tsconfig` gained `resolveJsonModule`. Typecheck is clean and Oxlint has no errors (style warnings about type assertions remain, acceptable for a throwaway).
- Running it in the worktree needs the env the main checkout keeps in `.env.local` (not copied). Placeholders are enough for the prototype: `DATABASE_URL=/tmp/roundtrip-prototype.db BETTER_AUTH_SECRET=placeholder-0123456789-0123456789 BETTER_AUTH_URL=http://localhost:3000 pnpm prototype:roundtrip`.
- Not done: dense monthly dates, the payoff-by-spot view (phase 2), a committed branch.

## Changes (2026-10-27)

- **Jan 2029 30/75, 35/75, 40/75 call spreads** added as barbell options B4-B6 (`roundtrip_report.py`), with live quotes for the new $30 and $35 strikes (`roundtrip_grid.py snapshot` now only quotes what is missing). Six of them are always exported, beside the 25/75 builds they replace, plus one return-heavy build.
- **Hold means hold.** New "In 2028" control for the Jan 2029 programme: hold to the Jan 2029 expiry (the default), or sell half in Jun 2028 and half in Nov 2028 (what "Hold" did before). It combines with any sale rule, so "sell half at $85, then scale out in 2028" is one click. Run keys and metrics are now `<build>|<rule>~<exit>|<debt>`; `?exit=hold|scale`.
- **Variant B keeps one scale** across every sale rule, 2028 exit and debt share for the build, on both charts, so changing the rule moves the bars and not the axis.
- **Your price points** (under the chart in variant A; `?custom=2027-03:90,2027-09:60`): pick a month and a price, press "Price this path (live CLI)". The dev server runs `custom_path.py`, which prices every leg with live CLI calls (about a minute for a new path; cached in `data/roundtrip-exit-values-custom-2026-10-26.json`) and traces every build, rule, exit and debt share along it with the same engine. The result appears as a "Your points" path in all three variants. Dev server only; needs Schwab sign-in.
- **Fix: the page reloaded while pricing.** `custom_path.py` appends to the CLI response log and the valuation caches under `scenarios/iren/data/`; Vite's watcher saw each write and sent a full reload (the chart "flashing", pricing state lost). `vite.config.ts` now ignores those files in `server.watch`; restart the dev server to pick it up.
- **Variant A keeps one scale** across paths, sale rules, 2028 exits and debt shares ("Same scale on every path" toggle, on by default). The axis ignores the straight-to-bull path and your own points (bull peaks near $220k and made the base and bear lines flat), so it runs $0 to $100k; a path above it stops at the top of the axis, with a note, and the tooltip still shows the real values.
- **Price points follow the path.** The panel lists the selected path's own points (`knots` in the chart data, from `export_chart_data.py`) as a month select and a price box each, and the chart rings them (grey on stored paths, purple on yours). Changing one makes them your points; yours stay when you change path ("Start again from <path>" and "Clear my points" return to a stored path's). Pricing runs on your own points only.
- **Your points are priced by the batch engine, not the CLI.** `custom_path.py` now sends the pricing worker (`packages/pricing-engine`, `uv run pricing-worker`) one `batch` request per contract: the stored 2026-10-26 Mark, spot and rate, and a Shock per date, spot and IV rule, with the Mark-implied IV solved by the engine. A path takes about 2 seconds (it took 40-50 s with one CLI call per valuation) and nothing is cached. The CLI and the stored paths are unchanged. Checked by pricing the Base points and comparing with the stored Base path: where the trigger dates agree (hold, sell half at $85, the put rules) the totals differ by $0 to $21 on $10k of capital (0.04%); the $103 rule differs because a custom path also tests the trigger on your own dates (Dec 2027 touches $103). Against the CLI's 756 stored valuations the batch is within $0.08 a share (median 0.03%).

## v2 built (2026-10-27): one timeline, Builds and Price Paths of your own

Plan: `plan-v2-one-timeline-and-my-builds.md`. Screenshots: `v2-a-legs-over-time.png`, `v2-a-unsaved-copy.png`, `v2-b-outcome-by-path.png`, `v2-c-compare.png`, `v2-builder.png`.

- **Engine.** `scenarios/iren/analysis/roundtrip_engine.py` runs one Build on one Price Path from a Quote Set with a pricer passed in (no I/O): Actions, the weekday-before-expiry sale into shares, the debt rule, the trace and v1's to-the-dollar leg-sum check. `roundtrip_run.py` is the JSON entry point (stdin, stdout): it prices every value it needs in one `pricing-worker` session (Mark-implied IV, then Rule 2 exit IV) and runs every Build x path x debt share. v1's scripts are unchanged; they are the regression oracle. A run ends at the later of the path's last point and the last expiry sale, and the path is flat after its last point.
- **Regression gate** (`test_roundtrip_regression.py`, all pass, every run within $0 of v1): hold to the Jan 2029 expiry for every exported build, path and debt share (476 runs); sell half at $85 and at $103 on builds without spread sleeves; the Jan 2028 programme as Sell 100% -> cash on 2027-12-31 on builds without spreads; and the return-heavy build's v1 hold-exit figures (E +768.05%, bear +35.32%, base $83,312). Batch pricing against the CLI on that base run: $83,315 against $83,312.
- **Not reproducible by design:** spec.md's +674% is v1's "scale" 2028 exit, which sold half the *shares* in Jun and Nov 2028; Actions never sell shares, so no v2 path reproduces it. Likewise v1's half-sale left spreads alone while v2's Sell X% sells every option Sleeve, and v1's Jan 2028 programme stopped on 2027-12-31.
- **What changes in the ranking:** on one timeline the Jan 2028 builds lead the seeded list (about +850% Expected on the 2026-10-27 Quote Set). Their calls are sold in Jan 2028 into shares, which then ride the 2028 path to $164 on Base; in v1 that programme was measured on 2027-12-31.
- **Chain.** `pnpm schwab option chain --symbol IREN [--from YYYY-MM-DD] [--contract-type CALL|PUT|ALL]`: one read-only GET plus the Treasury rate per expiry (Schwab's chain rate as a flagged fallback); tests on the replayed fixture. A live chain from Jun 2027 is about 200 calls in about a second.
- **Data.** `rt_` tables in `src/db/schema/roundtrip.ts`, migration `drizzle/0001_roundtrip_builds.sql`. `store.ts` reads, saves, deletes and checks them; it seeds 29 builds and 11 paths from `scenarios/iren/data/roundtrip-v2-seed.json` (`export_seed.py`) when there are no Builds and no paths, so deleting everything brings the seed back on the next load. Service tests on an in-memory database.
- **Server.** `server.ts` keeps the Quote Set and every run in memory, keyed by the Build's and the path's content, so a save or an edit runs only what is new; "Re-quote now" drops both. An all-shares baseline ($10,000, scaled to each Build's budget) runs on every path. `api.ts` holds the server functions. The page loads its data after it mounts (a live chain and an engine run take a few seconds), not in a route loader.
- **Page.** Programme toggle gone; the strip shows the Quote Set's time and spot, "Re-quote now", the debt share and $/%. Left: every Build sorted by Expected, with an expiry badge, Expected, On loaded path, edit and delete (in-page confirm); a Build that can't be priced is greyed with the reason. Right column under the legend: the Price Paths with pencil and trash, "+ New path", and the unsaved copy at the top. Under the chart: the loaded path's points with Action and percent. Builder panel from "+ New build" or the pencil.
- **Running it:** `DATABASE_URL=/tmp/roundtrip-prototype-v2.db BETTER_AUTH_SECRET=placeholder-0123456789-0123456789 BETTER_AUTH_URL=http://localhost:3000 pnpm prototype:roundtrip` (it applies the migrations first). Needs a signed-in Schwab CLI.
- **Repo changes outside the prototype:** `tsconfig.json` `lib` is ES2023 (for `toSorted`, which Oxlint asks for); `pnpm prototype:roundtrip` runs `drizzle-kit migrate` first.
- **Not done:** the plan's "same numbers through the page and from the command line" was checked as engine-from-CLI against the CLI cache, not against the page's own in-memory Quote Set (the page calls the same `roundtrip_run.py`). Exchange holidays are not modelled in the day-before-expiry sale. v1's `chart-data-*.json`, `custom_path.py` and `export_chart_data.py` are no longer used by the page.
