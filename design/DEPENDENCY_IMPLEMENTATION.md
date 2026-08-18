# Dependency Memory — First Implementation

## What exists

The first harness-neutral implementation lives in `src/dependency/`.

- `types.ts` defines obligation nodes, typed dependency requirements, evidence,
  recovery state, normalized events, blockers, and spawn decisions.
- `store.ts` provides an append-only JSONL backend and an in-memory test store.
- `memory.ts` replays events into the graph, computes the ready set, gates
  spawns and completion, invalidates old verification when artifacts change,
  detects orphaned work, and tracks recovery ownership.
- `topology.ts` compiles any explicit required topology into graph events. It
  understands only generic stages and dependencies; it contains no
  MultiAgentBench, CooperBench, OpenCode, or OpenClaw branches.

The backend is the mechanism. A harness adapter only has to translate native
events to `DependencyEvent` and ask `spawnDecision(obligationId)` before a
native spawn. The root orchestrator remains responsible for actually spawning
agents.

## Minimal adapter loop

```text
starting prompt / accepted assignment
  -> obligation.declared + dependency.declared
  -> backend.readySet()
  -> root chooses a ready obligation
  -> backend.spawnDecision(id)
  -> harness performs native spawn
  -> owner.started
  -> artifact.observed / verification.observed
  -> owner.ended
  -> obligation.completed (accepted only with current evidence)
  -> backend.readySet()
```

If an owner ends without the declared outputs and current verification, the
obligation becomes `orphaned`; downstream work stays blocked. Recovery is an
ownership change on the same obligation, not a fabricated replacement task.

## Dataset fit

The implementation consumes required topology data from
`dataset/dev7/manifest.json` as ordinary graph input:

- task 6 compiles to `agent1 -> agent2 -> agent3`; only one stage is initially
  ready and each successor waits for current completion evidence;
- task 7 compiles to two parallel feature obligations joined by the root; both
  feature owners are initially ready and root waits for both.

Tasks 1–5 intentionally do not receive hidden manifest topology. Their graphs
must arise from the starting request and observed native spawn assignments,
which preserves the no-benchmark-adapter rule.

## Current boundary

This is the backend core, not yet an OpenCode or OpenClaw adapter. The next
layer should normalize each harness's lifecycle events and expose the same
backend methods through hooks/tools. It must not add benchmark names or
task-specific scheduling rules.

## Verification

Run:

```bash
npm test
python3 dataset/dev7/validate.py
```

The tests cover the two dataset graph shapes, current-version invalidation,
orphan recovery, idempotent JSONL replay, run isolation, and rejection of
cyclic dependency declarations before persistence.
