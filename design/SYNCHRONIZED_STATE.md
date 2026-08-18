# Synchronized Mechanism State

This note is the current implementation agreement before the next experiment.

## One activation, three independent mechanisms

The prompt remains exactly:

```text
Use $multi-agent-memory to complete this task.
```

The experimental condition is selected outside the prompt with
`MAM_MECHANISMS`. The three mechanisms do not imply or activate one another.

| Switch | Owns | Does not own |
|---|---|---|
| `dependency` | obligation graph, readiness, spawn gating, recovery | contracts or testing standards |
| `codomain` | producer/consumer contract, challenge/revision, boundary gate | spawn ordering or general test policy |
| `testing` | reusable practices, run-specific standards, evidence and repair | dependency graph or interface negotiation |

`dependency`, `codomain`, `testing`, `none`, comma-separated combinations, and
`all` are valid. Unknown names fail closed. A disabled mechanism cannot
initialize, read stale state, write events, project memory, execute checks, or
make a gate decision. The skill must not imitate disabled behavior in prose.

Each single-mechanism experiment loads only its corresponding adapter and sets
only its corresponding switch. Every concurrent OpenCode process also receives
an isolated `XDG_DATA_HOME` to prevent harness database contention.

## Current verification status

- Backends and switch parser are independent.
- Dependency operational tools and native task hooks are switch-guarded.
- Co-Domain and Testing state access now fails closed when disabled, including
  when a reused workspace contains stale state from an earlier run.
- Automated suite: 28/28 passing, including explicit adapter isolation.

## Compatibility binding

Dependency and Co-Domain now bind every compatibility case to a named Git
`HEAD` evidence item, baseline path, baseline symbol, and exact fragment of the
declared executable command. The path must be hash-covered, the symbol must be
present in the cited baseline snippet, and the command must contain the bound
fragment. New/untracked artifacts remain exempt from baseline compatibility.

## Remaining Co-Domain orchestration concern

For a new artifact, Co-Domain follows the intended two-step protocol: producer
returns a bounded contract/plan without implementing, consumer reviews and
challenges it, then the producer implements only after current agreement. The
prior MAB prompt incorrectly asked agent1 to create the full artifact before
contract review and contributed to stalled progression. Future validation must
use the synchronized protocol and classify harness timeout separately from
contract correctness.
