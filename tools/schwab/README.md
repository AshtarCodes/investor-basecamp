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
```

Captures are written under `.local/schwab/captures/` (gitignored). Schwab OAuth tokens live in Keychain (`investor-basecamp` / `schwab`).

**Macro:** `macro dxy` computes ICE USDX from six Schwab **`BASE/QUOTE`** FX quotes (`method: ice-formula`, `source: schwab-fx`). Schwab does not serve **`$DXY`** or FX **price history** for backfill — see [docs/schwab/external-market-data.md](../../docs/schwab/external-market-data.md) and [observations.md](../../docs/schwab/observations.md).
