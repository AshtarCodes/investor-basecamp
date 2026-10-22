# Scenario controls are one function, exposed as WebMCP tools and one MCP endpoint

Crossing the Portfolio Loss Threshold in v1 only opens a Simulated Portfolio and the Compare view. The v2 pass is an agentic loop that adjusts that book until the worst Shock is back under the percent. Each control and value is one server-side function. The page calls it through a TanStack server function, and registers it as a WebMCP tool with `document.modelContext` from the [WebMCP draft](https://webmachinelearning.github.io/webmcp/) (Community Group Report, 3 September 2026). An agent with the page open calls `executeTool`. An agent with no page open POSTs JSON-RPC to one MCP endpoint at `https://basecamp.<tailnet>.ts.net/mcp`, using the [streamable HTTP transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) (protocol version 2026-07-28). `tools/list` returns the catalog. `tools/call` names the tool and passes its arguments. Neither path drives the screen.

Tools return the underlying data and leave the judgment to the agent. A read of a Scenario returns its Shocks, on the order of fewer than ten for a Simulated Portfolio, and the agent decides which is worst. Tool names are not chosen yet. The same function backs the button, the WebMCP tool, and the MCP call.

## Considered Options

- **A route per question.** Each answer would be its own URL, and a digested field such as "worst shock" would hide the Shocks the agent needs.
- **The server function as the headless door.** Start's server functions are the app's own RPC. Their URLs are generated ids, and a request with no `Origin`, `Referer`, or `Sec-Fetch-Site` is rejected.
- **WebMCP only.** An agent looking at the page is covered. A headless client has nothing to call, unless a bridge launches a browser and runs `executeTool` inside it.
- **A second implementation behind MCP.** The page and the endpoint would drift.
- **Driving the DOM.** The agent would be guessing at controls the page already knows how to run.

## Consequences

- The headless caller sends the session cookie. The endpoint checks it the same way a protected server function does.
- Read values use `readOnlyHint`. Edits use `consequentialHint`. No tool calls a Schwab order endpoint; that stays [ADR 0004](0004-no-order-placing-code.md). A tool may edit a Simulated Portfolio, including its Cash, Positions, Hypothetical Trades, Loss Threshold, and Scenarios.
- The Tailscale HTTPS name is a secure context, which WebMCP requires.
- The draft's declarative form binding is still unspecified, so WebMCP tools are registered imperatively with a name, description, and JSON Schema.
