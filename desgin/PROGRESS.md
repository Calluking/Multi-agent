# Universal Plugin Progress

This file is the durable implementation checklist. Update it whenever a milestone changes state or an experiment produces new evidence.

Status values: `DONE`, `PARTIAL`, `TODO`, `BLOCKED`.

## Recovered baseline

| Area | Status | Evidence |
|---|---|---|
| Original MultiAgentBench architecture identified | DONE | `dependency_memory/v4_sparse/` and `all_three` experiments |
| Native OpenClaw plugin registration | DONE | Typed hooks and memory tools validated |
| Native subagent injection | DONE | Task 17 lifecycle probe and task 1 trace audit |
| MultiAgentBench one-task plugin run | DONE | Both conditions scored 100%; plugin activity audited |
| CooperBench one-task generalization | DONE | Arbitrary feature owners composed; official tests 34 passed |
| Twenty-task plugin comparison | DONE | Without plugin 83.0; with plugin 81.75 |

## Plugin implementation roadmap

| Milestone | Status | Acceptance condition |
|---|---|---|
| Structured canonical identity | DONE | Structured keys, legacy fallback, partial-update preservation, generated-record identity, and regression tests pass |
| Assignment and participant registry | PARTIAL | Arbitrary assignment IDs and capabilities are retained throughout a run |
| Sparse assignment-aware retrieval | PARTIAL | Only relevant private records and shared boundary contracts reach each agent |
| Spawn/completion episode correlation | DONE | Injection IDs correlate with real child session keys and outcomes |
| Deterministic artifact observer | PARTIAL | File existence, size, mtime, SHA-256 version, workspace confinement, and stale-verification detection are implemented; tool/command observations remain |
| Dependency state reconciler | PARTIAL | Missing → blocked and existing → produced work; verified/ready require the upcoming verification ledger |
| Verification ledger | TODO | Exact command, artifact version, result, diagnosis, owner, repair, and rerun are persisted |
| Readiness gate | TODO | Consumers cannot use unresolved or stale prerequisites |
| Recovery scheduler | TODO | A blocker creates a bounded repair opportunity for a capable owner using a changed strategy |
| Same-command re-verification | TODO | A repair resolves a blocker only after the required command passes |
| Contract negotiation lifecycle | PARTIAL | Proposal, challenge, atomic revision, acceptance, verification, supersession, and stale-version rejection work universally |
| Completion gate | TODO | Success is prohibited while required artifacts, contracts, or verification entries remain unresolved |
| MultiAgentBench adapter | PARTIAL | Fixed workflow maps cleanly into universal assignments and artifacts |
| CooperBench adapter | PARTIAL | Peer feature ownership and shared artifacts map cleanly without role-name assumptions |
| Benchmark-independent core | TODO | Banks, routing, observation, recovery, and gates contain no benchmark-specific logic |

## Structured canonical identity implementation

Implemented in the plugin:

- `openclaw_plugin/src/memory-engine.ts`
- `openclaw_plugin/test/deduplication.mjs`
- `openclaw_plugin/package.json`
- `openclaw_plugin/src/index.ts`

Evidence:

- explicit `projectId`, `artifactIds`, `interfaceId`, `subject`, `producerIds`, `consumerIds`, and `verificationSubject` fields;
- kind-specific canonical keys with project isolation and private-owner separation;
- differently worded records with the same structured identity collapse to the original canonical ID;
- partial updates retain previously stored identity fields;
- legacy records remain readable and retain normalized-exact fallback behavior;
- plugin-generated MultiAgentBench and cooperative-assignment records now carry structured identity;
- `npm test` passes concurrency, deduplication, targeting, and co-domain filtering tests.

## Development and benchmark order

Complete the plugin before using benchmarks for final validation:

1. Implement and locally test every universal control-plane milestone.
2. Run plugin unit tests and native OpenClaw integration validation.
3. Freeze the plugin implementation for evaluation.
4. Run CooperBench to validate arbitrary peer assignments and shared-artifact composition.
5. Run MultiAgentBench to validate dependency recovery, contract use, testing evidence, and workflow completion.
6. Compare plugin/no-plugin conditions only after the implementation is complete.

Do not use intermediate benchmark runs as substitutes for completing the architecture.

## Next implementation milestone

Complete command/tool observation and the verification ledger. Artifact existence now advances a record only to `produced`; matching successful command evidence must advance the same artifact version to `verified`, and any later content hash change must invalidate that evidence.

Current observer evidence:

- missing required files become `blocked`;
- existing files become `produced`, never implicitly `verified`;
- observations retain size, modification time, SHA-256, timestamp, and source;
- paths outside the workspace are rejected;
- unchanged verified artifacts retain verification;
- content changes move verified artifacts back to `produced` with status `stale`;
- `npm test` includes the artifact-observer regression suite.
