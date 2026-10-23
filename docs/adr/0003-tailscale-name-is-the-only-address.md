# The app's only address is a Tailscale name

The served app is reached at `https://basecamp.<tailnet>.ts.net`, from the laptop and the phone. It listens on `127.0.0.1` over plain HTTP, and Tailscale handles HTTPS in front of it. Passkeys for that instance, and the app's Schwab callback, are tied to that hostname. `pnpm dev` and `pnpm dev:auth` run at `http://localhost:3000` on loopback. Passkeys on that origin are `pnpm dev:auth` only, with relying party id `localhost`. `pnpm dev` signs in with email and password. See [Three run modes](0006-three-run-modes.md). A Tailscale name can be moved to another machine, either as a Tailscale Service or as a node named `basecamp`. So the planned move from laptop to VPS needs no Schwab re-approval and no passkey re-enrollment, and the app is never publicly exposed.

## Considered Options

- **`127.0.0.1` only:** passkeys can't be tied to an IP address, and the phone can't reach it.
- **The laptop's own Tailscale machine name:** changes when the app moves to a VPS.
- **A public domain:** costs money and needs its own certificate setup. There's no domain today. Switching to one later costs one Schwab re-approval and re-enrolling passkeys.

## Consequences

- The tailnet name is part of the address and appears in public certificate logs. Tailscale only allows switching between its default and randomized names.
- Nothing else in the tailnet may use the name `basecamp`.
- If Tailscale is off, the app is unreachable at its address.
- A Service must be hosted by a tagged device, which the user's laptop isn't.
- `https://127.0.0.1:8182/api/schwab/callback` is registered for the dev CLI. That CLI is the only process that runs the Schwab browser login. The app's callback stays `https://basecamp.<tailnet>.ts.net/api/schwab/callback`.
