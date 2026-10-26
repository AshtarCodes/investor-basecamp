# Schwab dev CLI

Python CLI for Schwab Trader API exploration. Invoked from the repo root as `pnpm schwab`.

## Prerequisites

- macOS (Keychain)
- [uv](https://docs.astral.sh/uv/)
- [mkcert](https://github.com/FiloSottile/mkcert) for the OAuth callback listener

## One-time setup

1. Store Bitwarden machine-account credentials in Keychain (items `bws-access-token` and `bws-org-id`).
2. Mint a loopback TLS certificate for the OAuth listener. **mkcert’s root CA** lives only in mkcert’s CAROOT (`mkcert -CAROOT`); never copy that into the repo or a synced folder. The **leaf** cert and key for `127.0.0.1` go under `.local/schwab/certificates/` (gitignored with the rest of `.local/`):

```bash
mkdir -p .local/schwab/certificates
mkcert -key-file .local/schwab/certificates/key.pem \
  -cert-file .local/schwab/certificates/cert.pem 127.0.0.1
```

## Commands

```bash
pnpm schwab login
pnpm schwab get /trader/v1/accounts/accountNumbers
pnpm schwab capture --option '<OCC>' --equity AAPL
pnpm schwab macro dxy
pnpm schwab option price --symbol 'IREN  270115C00055000'
```

Captures are written under `.local/schwab/captures/` (gitignored). Schwab OAuth tokens live in Keychain (`investor-basecamp` / `schwab`).

**Macro:** `macro dxy` computes ICE USDX from six Schwab **`BASE/QUOTE`** FX quotes (`method: ice-formula`, `source: schwab-fx`). Schwab does not serve **`$DXY`** or FX **price history** for backfill — see [docs/schwab/external-market-data.md](../../docs/schwab/external-market-data.md) and [observations.md](../../docs/schwab/observations.md).

## Option pricing

`pnpm schwab option price --symbol '<OCC>'` reprices one option with our own model (the [pricing engine](../../packages/pricing-engine/AGENTS.md), imported in-process) from live Schwab quotes. The OCC symbol is the 21-character form Schwab prints, root padded to six (`XSP   261218C00768000`). Live runs always call Schwab, with read-only GETs; `--offline` uses only the flags. Details and decisions: [ticket 14](../../.scratch/portfolio-risk-wayfinding/issues/14-schwab-option-price-cli.md).

```bash
# Fair value now: Mark-implied IV, Treasury rate, Greeks, and a cross-check against Schwab's ANALYTICAL value
pnpm schwab option price --symbol 'IREN  270115C00025000'
# Hold to expiry: intrinsic, net P&L against the mark, breakeven (no model)
pnpm schwab option price --symbol 'IREN  270115C00025000' --mode expiry --expected-spot 40
# Sell early: our value at the exit date (4 pm ET) if the stock is 40 then
pnpm schwab option price --symbol 'IREN  270115C00025000' --mode sell --as-of 2026-12-15 --expected-spot 40
# Time stress: today's spot and IV, only 30 days left (at most the real remaining life)
pnpm schwab option price --symbol 'IREN  270115C00025000' --dte 30
# No Schwab, no Treasury: every input by flag (--model is required, percent flags are percent)
pnpm schwab option price --symbol 'XSP   261218C00768000' --offline --model european --spot 768 --vol 15 --rate 4
```

- Flags and output are percent (`--vol`, `--rate`, `--div-yield`, and every percent in the JSON); `--vol-unit decimal` changes how `--vol` is read. The engine's decimals never reach the output.
- `--dte` wins over `--as-of`. A date means 4 pm New York. A live run takes no instant before now; use `--offline` for the past.
- The Treasury curve is cached for a day under `.local/schwab/`. A European option (an index such as XSP or SPXW) is priced on a put-call parity forward built from the chain's call and put Marks.
- `crossCheck` is informational: Schwab's IV sits about 2 vol points off the IV of its own Mark, and its `ANALYTICAL` value ignores the parity forward on indexes.
