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
| Structured canonical identity | PARTIAL | Implementation and tests pass; CooperBench rerun must confirm the observed duplicate is eliminated |
| Assignment and participant registry | PARTIAL | Arbitrary assignment IDs and capabilities are retained throughout a run |
| Sparse assignment-aware retrieval | PARTIAL | Only relevant private records and shared boundary contracts reach each agent |
| Spawn/completion episode correlation | DONE | Injection IDs correlate with real child session keys and outcomes |
| Deterministic artifact observer | TODO | File state, version, tool result, exit code, incomplete turn, and stale verification become typed observations |
| Dependency state reconciler | TODO | Planned → in progress → produced → verified → ready transitions are evidence-driven |
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

## Next implementation milestone

Finish validation of structured canonical identity before moving to the deterministic observer:

1. Rebuild/reload the plugin in OpenClaw.
2. Rerun the CooperBench one-task probe in a fresh bank.
3. Confirm exactly one canonical shared `Encoding.encode` contract remains.
4. Mark this milestone `DONE` only after that runtime evidence.
5. Begin the deterministic artifact observer milestone.
