# Engine: Greeks at a scenario point

Type: task
Status: needs-triage

Blocked by: none. Wanted by [14](14-schwab-option-price-cli.md), which ships `sell` without Greeks at the exit instant until this lands.

## Goal

Let the engine return the Greeks of a contract at a scenario point: a shocked spot, a moved valuation, and the contract's own Mark-implied IV. Today a single `price()` returns Greeks only at the point it prices, and the worker's `batch` returns prices only (`greeks` and `cross_check` are refused on a batch contract, [16](16-pricing-engine-package.md) and [18](18-engine-worker.md)).

The first consumer is the `sell` mode of the CLI in [14](14-schwab-option-price-cli.md): "if the stock is $40 on 2026-06-30, what are delta, vega and theta then?" These are the Greeks of the option in the scenario you typed in, not a forecast. They are an output of the engine; Schwab's Greeks never go in.

## Why not just call `price()` twice in the CLI

The scenario's IV comes from the Mark at today's inputs, and the scenario then needs the worker's Shock semantics (spot and forward scaling, residual carry, `expired`, `dividend_not_in_life`). Greeks on top of that must be bumped around the shocked point, using the same code path. Doing that in the CLI would repeat `batch.shocked` there, which is what [14](14-schwab-option-price-cli.md) avoids by calling `price_contract`. The engine should own it.

## Scope to settle

- **Shape.** Two candidates:
  - **(a)** Allow `greeks: true` on a batch contract, per Shock or only for chosen Shocks. Cost matters: Greeks are five more prices or more per Shock by bump-and-reprice, so they cannot be on for a 50 by 100 grid. Opt-in per contract with a list of Shock indices.
  - **(b)** A separate worker request type and a public function for one contract and one Shock with Greeks, no grid. Smaller, and all the CLI needs.
- **No IV.** When the Mark has no IV the scenario price is the model value at the 1 vol point floor plus the residual, and Greeks at that floor mean nothing. Return no Greeks and keep the `no_iv` flag.
- **Expired Shock.** A Shock at or past the Settlement instant is plain intrinsic. Return no Greeks, flagged `expired`.
- **Units** stay as in [16](16-pricing-engine-package.md): vega per vol point, theta per calendar day, rho per percentage point of rate, all per share.
- **IV Shift.** A scenario's Greeks are at its shifted IV. Say so in the result.

## Acceptance

- Greeks at a scenario point equal `price()`'s Greeks at the same shocked inputs (the engine as its own twin), for an American put with dividends and a European index option on a forward.
- A European call's delta, gamma, vega and theta at a scenario point match the closed-form values in `tests/support.py`.
- A zero Shock returns the same Greeks as a base `price()` with Greeks.
- With Greeks off, the 50-Position by 100-Shock batch still completes in under 1 s through the worker (`bench/worker.py`), and the first 100 by 200 price stays under 50 ms.
- The committed JSON Schema is regenerated and its staleness test passes.
- No test needs the network.

## Out of scope

- Greeks across a whole Shock grid in the app. The Inspector's Greeks come from the base point; whether the app wants them per Shock is for the server ticket to say.
- Changing any price.
