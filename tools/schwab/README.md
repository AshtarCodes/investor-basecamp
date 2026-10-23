# Schwab dev CLI

Python CLI for Schwab Trader API exploration. Invoked from the repo root as `pnpm schwab`.

## Prerequisites

- macOS (Keychain)
- [uv](https://docs.astral.sh/uv/)
- [mkcert](https://github.com/FiloSottile/mkcert) for the OAuth callback listener

## One-time setup

1. Store Bitwarden machine-account credentials in Keychain (items `bws-access-token` and `bws-org-id`).
2. Mint a loopback TLS certificate (keep mkcert’s root CA in mkcert’s CAROOT only — never commit or sync it):

```bash
mkdir -p .local/schwab/tls
mkcert -key-file .local/schwab/tls/key.pem -cert-file .local/schwab/tls/cert.pem 127.0.0.1
```

## Commands

```bash
pnpm schwab login
pnpm schwab get /trader/v1/accounts/accountNumbers
pnpm schwab capture --option '<OCC>' --equity AAPL
```

Captures are written under `.local/schwab/captures/` (gitignored). Schwab OAuth tokens live in Keychain (`investor-basecamp` / `schwab`).
