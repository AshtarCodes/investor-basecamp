# No code that places orders

Reading positions from Schwab requires the "Accounts and Trading Production" product, so the app's token can also place trades. We deliberately ship no code that calls a Schwab order endpoint: a bug, a compromised dependency, or a misread prompt can't trade your account through this app. Tokens are encrypted at rest, secrets come from Bitwarden Secrets Manager, and disconnecting Schwab is explicit.

## Consequences

Any future trading feature, including one suggested by the v2 position-rules flow, needs a new ADR that supersedes this one. Adding it quietly isn't allowed.
