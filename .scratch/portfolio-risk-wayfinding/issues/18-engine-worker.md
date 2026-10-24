# Engine worker (`pricing-worker`)

Type: task
Status: ready-for-agent

Blocked by: [16](16-pricing-engine-package.md) (the worker serves the engine's schema)

## Goal

Add the long-lived process the server spawns so QuantLib is imported once, not per request ([ADR 0007](../../../docs/adr/0007-pricing-engine-is-a-python-worker.md)). The server code that spawns it does not exist yet and is not part of this ticket; nothing consumes the worker until the app has server functions.

## Scope

- A `pricing-worker` entry point in `packages/pricing-engine/` that reads one JSON request per line on stdin and writes one JSON response per line on stdout. Requests and responses use the schema exported by [16](16-pricing-engine-package.md), plus a request id that the response echoes.
- Structured errors: validation failures, model failures and unexpected exceptions each return an error object with a code, a message and the request id, and never kill the worker. Diagnostics go to stderr, never stdout.
- A warm-up on start (import QuantLib, build and price one throwaway option) and a ready line when done.
- A batch request type that prices many Positions over a Shock grid in one message, so the server does not send 5,000 lines for one grid.
- A process pool sized from measurement. The worker owns the pool; a request is never split mid-Position.
- Restart behavior: the worker exits cleanly on stdin close and on SIGTERM, and a documented rule says what the caller should do when it dies mid-request (retry once).
- A runnable spec in the package `AGENTS.md`: how to start the worker by hand and send a request.

## Acceptance

- Round trip of a single price through a spawned subprocess, measured and recorded in the package `AGENTS.md`; the first request after the ready line is under 50 ms for a 100 by 200 grid price.
- A 50-Position by 100-Shock batch completes in under 1 s on this laptop through the worker, including the pool.
- A malformed line, an unknown request type, and a Mark below intrinsic each return a structured error and leave the worker serving the next line.
- stdin close and SIGTERM both end the process with exit code 0 within a second.
- Tests spawn the real worker as a subprocess; no test needs the network.

## Out of scope

- The TS client and the server function that spawn it; authentication (the worker is a local child process, not a network service); the Treasury fetch ([17](17-engine-rate-and-dividend-inputs.md)), which callers run and pass in.

## Open decisions

- Pool size and restart policy: from measurement, recorded in the package `AGENTS.md`.
