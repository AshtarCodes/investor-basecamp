# Can the Schwab Trader API supply our positions and market data?

Type: research
Status: resolved

## Question

Is the Schwab Trader API free and practical for one retail account holder to read their own positions, balances, quotes, option chains, and price history from a self-hosted app? What does access and auth cost in ongoing effort?

## Answer

Yes. Researched 2026-10-17. developer.schwab.com blocks automated fetches, so official wording came from a verbatim mirror of the portal docs ([accounts-and-trading-production.txt](https://repo.hex.pm/preview/dp_exchange_schwab/0.1.2/docs/reference/schwab/documentation/accounts-and-trading-production.txt), [spec notes](https://repo.hex.pm/preview/dp_exchange_schwab/0.1.2/docs/reference/schwab/spec-facts.md)) plus community sources ([schwab-py](https://schwab-py.readthedocs.io/en/latest/getting-started.html), [Schwabdev setup guide](https://raw.githubusercontent.com/tylerebowers/Schwabdev/refs/heads/main/docs/pages/setupguide.html)).

- **Cost:** free for individual account holders. Real-time data falls under your normal nonprofessional subscriber terms.
- **Access:** request "Trader API – Individual", then create one app with "Accounts and Trading Production" and "Market Data Production". Approval is manual, usually 1 to 3 days. Changing the callback URL later sends the app back for re-approval. Log into thinkorswim once (community advice). No sandbox exists.
- **Auth:** three-legged OAuth. The callback must be HTTPS and match exactly; `https://127.0.0.1:<port>` is accepted, `localhost` is not. Access token lasts 30 minutes. Refresh token lasts a hard 7 days, and renewing it requires an interactive browser login. Nothing extends it.
- **Positions:** `GET /trader/v1/accounts/accountNumbers` maps account numbers to hashes; every account path takes the hash. `GET /trader/v1/accounts?fields=positions` returns long and short quantity, `averagePrice`, `marketValue`, open and day P/L, and the instrument (OCC-style option symbols padded to 21 characters). There is no Total Cost field: compute it from average price, quantity, and multiplier. Balances include `liquidationValue` and `cashBalance`, with a different shape for cash and margin accounts.
- **Not returned:** futures, futures options, forex, and mutual funds.
- **Market data:** quotes and option chains return IV (`volatility`, as a percent), delta, gamma, theta, vega, rho, and theoretical value per contract. `GET /marketdata/v1/pricehistory` gives daily candles up to 20 years back, for stocks and ETFs only.
- **Rate limit:** about 120 non-order requests per minute per app (medium confidence).
- **Main ongoing burden:** the weekly re-login. The app needs a clear Reconnect flow instead of failing silently.
