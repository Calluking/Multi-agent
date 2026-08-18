# Co-Domain Memory — First Implementation

The harness-neutral backend lives in `src/codomain/` and follows
`CODOMAIN_MEMORY.md`.

It implements:

- append-only JSONL and in-memory event stores;
- structurally identified producer/consumer contracts;
- candidate-to-proposal promotion grounded by evidence;
- precise challenges and participant-authored revisions;
- optimistic version checks that reject stale writes;
- participant-specific acceptance, requiring both sides;
- separate agreement and verification lifecycles;
- current-version artifact evidence from both owners;
- rejection of disconnected boundary tests;
- stale verification after artifact or semantic changes;
- sparse producer and consumer projections;
- high-risk integration gates without spawn control;
- idempotent event replay and run isolation.

The backend does not infer contracts from keywords, insert domain templates,
spawn agents, or expose a benchmark-specific path. The OpenCode bridge at
`adapters/opencode/codomain-memory.mjs` provides explicit initialize, propose,
challenge, revise, accept, inspect, artifact-observation, real-path verification,
and integration-decision tools. It also normalizes WSL's optional `python`
alias to `python3`, rejects runtime/environment installation and system-path
mutation, and bounds verification commands to 120 seconds.

Run `npm test` to execute the Co-Domain and Dependency regression suites.
