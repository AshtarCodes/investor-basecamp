# Register the Schwab developer app

Type: task
Status: resolved
Blocked by: 03

## Question

Get a Schwab app to "Ready For Use", so the real payload shapes can be inspected. This is a HITL task: only you can sign up with your brokerage identity.

Checklist. Steps 1 to 3 fix the app's address, which goes into the callback, so do them before registering. Decisions are in "Where does the app run, and how do you reach it?". How the laptop actually serves the address is a separate decision, "How does the laptop serve the basecamp address?", and isn't needed here.

1. Create a Tailscale account if you don't have one, and install Tailscale on the laptop (the standalone download from tailscale.com) and on your phone.
2. In the Tailscale admin console DNS page: switch the tailnet DNS name to the randomized two-word name, enable MagicDNS, and enable HTTPS certificates. Note the tailnet name. Don't name any machine `basecamp`.
3. In Bitwarden, enable Secrets Manager (free plan) and create the project "investor-basecamp" to receive the Schwab app key and secret.
4. At developer.schwab.com, sign up with the same email as your brokerage login.
5. Request the "Trader API – Individual" product and wait for that approval.
6. Create one app with both "Accounts and Trading Production" and "Market Data Production", and with these two callbacks, comma-separated, matching exactly with no trailing slash:
   - `https://basecamp.<tailnet>.ts.net/api/schwab/callback`
   - `https://127.0.0.1:8182/api/schwab/callback`
7. Log into thinkorswim once, if you haven't since the TD Ameritrade migration.
8. Wait for the app to move from "Approved – Pending" to "Ready For Use" (usually 1 to 3 days), then store the app key and secret in the Bitwarden project.

Record in the answer: the tailnet name, the exact callbacks registered, the Bitwarden secret names for the app key and secret (never the values), and the date the app became ready.

## Comments

**2026-10-18:** steps 1 to 3 are done. The tailnet is `ojos-alhena.ts.net`, with MagicDNS and HTTPS certificates enabled. The laptop (`ashtars-macbook-pro`) and phone (`iphone-13`) are connected, and nothing is named `basecamp`. The app callback for step 6 is `https://basecamp.ojos-alhena.ts.net/api/schwab/callback`. No Tailscale Service was created: that waits on "How does the laptop serve the basecamp address?".

**2026-10-22:** the developer app is available. Callbacks and Bitwarden secret names are in the answer. Values were not recorded.

## Answer

Ready for use on 2026-10-22. The tailnet is `ojos-alhena.ts.net`.

Callbacks registered, with no trailing slash:

- `https://basecamp.ojos-alhena.ts.net/api/schwab/callback`
- `https://127.0.0.1:8182/api/schwab/callback`

Bitwarden secret names in the "investor-basecamp" project (values stay there):

- `SCHWAB_CLIENT_ID` for the app key
- `SCHWAB_CLIENT_SECRET` for the app secret

This unblocks [Pull real Schwab payloads for your accounts](05-pull-real-schwab-payloads.md). The laptop still does not serve `basecamp.ojos-alhena.ts.net`; that remains [How does the laptop serve the basecamp address?](11-how-the-laptop-serves-the-basecamp-address.md). The loopback callback is enough for the throwaway payload script.
