# What should the Scenario and Compare views look like?

Type: prototype
Status: open
Blocked by: 07, 13

## Question

Build rough UI variations, with fixture data, of:

- the Scenario builder (SPY moves, IV shifts, days forward, per-Underlying overrides)
- the P/L grid with breaching Shocks highlighted, the worst Shock, and contributions by Underlying and Position
- risk curves of P/L against SPY move at several IV shifts
- the Compare view: one Scenario on two Portfolios, both grids, and the difference

React to which variation makes risk easiest to see and act on.

## Comments

**2026-10-19:** v1 of the risk-reduction pass lands here: a Simulated Portfolio beside the Account, same Scenario, both grids and the difference. The percent-of-account Loss Threshold is the line a Shock is judged against. Design the controls and values as one function each. The button and a WebMCP tool (`document.modelContext`) call it, and a headless agent reaches the same function through one MCP endpoint (`tools/list`, `tools/call`) at the Tailscale address. Return the Shock list and let the agent judge it. Tool names are not chosen yet. See `docs/adr/0005-scenario-controls-are-webmcp-tools.md`. The agent loop that drives those tools is v2.
