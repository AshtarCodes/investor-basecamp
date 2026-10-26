Live Schwab responses captured 2026-10-26 during market hours, one coherent snapshot per contract:
`<name>_option_quote.json`, `_underlying_quote.json` (with fundamentals), `_chain.json` (one strike,
both rights) and `_analytical.json` (the `strategy=ANALYTICAL` chain trimmed to the contract's own
row). They were fetched with the CLI's own path builders in `schwab_inputs.py`, parsed, sorted and
passed through `redact_account_numbers`. Refresh them the same way; the tests derive `now` from each
quote's `quoteTime`, so a refreshed snapshot needs no test edits.
