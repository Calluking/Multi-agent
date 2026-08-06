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
| Deterministic artifact observer | DONE | File, command-result, failed/timeout child lifecycle, artifact version, and stale-verification observations are typed and tested |
| Dependency state reconciler | PARTIAL | Evidence-driven blocked/produced/verified/stale transitions and project/run isolation work; ready/completion reconciliation remains |
| Verification ledger | PARTIAL | Exact commands, exit codes, bounded output/error, artifact hashes, attempts, failures, and reruns persist; diagnosis and repair ownership remain |
| Readiness gate | PARTIAL | Downstream spawn is project/run-scoped and blocked on unresolved prerequisites while producers remain allowed; completion gate remains |
| Recovery scheduler | PARTIAL | Failed/timeout outcomes create an owned recovery obligation and gate reason; automatic bounded retry admission remains |
| Same-command re-verification | TODO | A repair resolves a blocker only after the required command passes |
| Contract negotiation lifecycle | DONE | Typed proposal, challenge, revision, acceptance, verification, canonical evolution, and stale-version rejection are tested |
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

Project/run isolation is now implemented. The next step is the universal assignment adapter: normalize arbitrary assignment IDs, owned working directories, artifact paths, producer/consumer participation, and verification commands before enabling completion enforcement.

Current observer evidence:

- missing required files become `blocked`;
- existing files become `produced`, never implicitly `verified`;
- observations retain size, modification time, SHA-256, timestamp, and source;
- paths outside the workspace are rejected;
- unchanged verified artifacts retain verification;
- content changes move verified artifacts back to `produced` with status `stale`;
- `npm test` includes the artifact-observer regression suite.

Verification-ledger evidence:

- native `after_tool_call` observes commands, exit codes, bounded results, errors, and workspace identity;
- only the exact configured verification command can affect its dependency record;
- unrelated successful commands cannot verify artifacts;
- failed matching commands create blocking attempts;
- successful matching commands bind evidence to current SHA-256 artifact versions;
- repeated attempts are retained as a bounded ledger;
- post-verification edits invalidate the successful evidence;
- `npm test` includes the verification-ledger regression suite.

Readiness and recovery evidence:

- consumer assignments are gated by their explicit `consumerIds` dependencies;
- producers are never blocked by the artifact they are responsible for producing;
- produced non-command prerequisites can be consumed;
- artifacts with a verification command require matching verified evidence;
- failed and timed-out child outcomes create bounded lifecycle evidence and a recovery owner;
- child sessions inherit their workspace mapping for command observation.

Contract lifecycle evidence:

- proposal initializes version 1;
- challenge retains the current version;
- revision increments the version;
- acceptance and verification require the exact current base version;
- stale actions are rejected;
- lifecycle changes preserve one canonical contract record.

Project/run isolation evidence:

- task-local records carry explicit `projectId` and `runId`;
- canonical keys include both identities;
- generated IDs include a stable hashed run suffix;
- repeated runs of one project do not overwrite each other;
- retrieval, workspace observation, verification, and readiness gates filter by active project/run;
- other-project and other-run blockers cannot affect the active task;
- unscoped reusable practices remain retrievable;
- partial legacy updates remain safe when their ID is unambiguous.
