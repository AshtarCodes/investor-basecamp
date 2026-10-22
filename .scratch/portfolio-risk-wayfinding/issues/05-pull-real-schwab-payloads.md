# Pull real Schwab payloads for your accounts

Type: task
Status: open
Blocked by: 04

## Question

Run a throwaway script that completes the OAuth flow and saves the raw responses from `/trader/v1/accounts/accountNumbers`, `/trader/v1/accounts?fields=positions`, one `/marketdata/v1/quotes` call for an option you hold, and one `/marketdata/v1/pricehistory` call. Redact account numbers and keep the dumps out of git.

The facts the answer must record, because the sync mapping waits on them:

- How a short option Position reports `averagePrice` and quantity (sign, per share or per contract), so Total Cost comes out signed correctly.
- The balance fields actually present for each of your account types (cash, margin, IRA), and which one is Net Liquidation Value.
- The exact option symbol format, and whether index options (SPX, XSP) come back with a different root or settlement flag.
- Any asset types in your accounts that v1 can't price.
- How Schwab's IV and greeks on the quote compare with what thinkorswim shows for the same contract.
- The units of the quote's dividend fields (`divAmount`, `divPayAmount`, `divYield`, `nextDivExDate`) and of the option chain's `volatility` and `interestRate`, for a dividend-paying stock you hold. "Which pricing models and inputs should the engine use?" couldn't confirm them.
- Any hint of Schwab's rate source and day count. For example: does the chain's `interestRate` vary by expiry, and do days-to-expiry values include the time of day?

The script is throwaway: keep it on a branch, not on master, and link it from the answer.
