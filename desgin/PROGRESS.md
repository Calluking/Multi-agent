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
| Dependency state reconciler | DONE | Evidence-driven blocked/produced/verified/stale transitions, project/run isolation, and completion reconciliation are implemented |
| Verification ledger | DONE | Exact commands, exit codes, bounded output/error, artifact hashes, attempts, failures, reruns, and repair ownership persist |
| Readiness gate | DONE | Downstream spawn is project/run-scoped and blocked on unresolved prerequisites while producers remain allowed |
| Recovery scheduler | DONE | Failures create owned obligations, changed-strategy packets, bounded admission, and explicit exhaustion escalation |
| Same-command re-verification | TODO | A repair resolves a blocker only after the required command passes |
| Contract negotiation lifecycle | DONE | Typed proposal, challenge, revision, acceptance, verification, canonical evolution, and stale-version rejection are tested |
| Completion gate | DONE | Terminal completion is revised while project-scoped artifacts or contracts remain unresolved |
| MultiAgentBench adapter | DONE | Fixed workflow maps through generic producer/consumer artifact dependencies |
| CooperBench adapter | DONE | Arbitrary peer IDs, work directories, owned artifacts, and shared contracts map without role-name assumptions |
| Benchmark-independent core | DONE | Banks, routing, observation, recovery, and gates contain no benchmark-specific control logic |

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

The universal plugin implementation is complete for evaluation. Freeze behavior after native integration validation, then run CooperBench and MultiAgentBench as the final verification phase.

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

Universal control-plane completion evidence:

- arbitrary assignment IDs register without planner/implementer/reviewer inference;
- assignment work directories are normalized and confined;
- owned artifact paths and handoff artifacts are assignment-scoped;
- peer paths cannot leak into another owner's dependency record;
- downstream spawns are blocked until prerequisites are produced or verified;
- producer finalization is revised before a child exits while its owned artifacts or exact-command verification remain unresolved;
- the revision re-enters the same child once with a concrete, idempotent completion instruction, matching the ideal implementation-finalization checkpoint;
- failed owners receive an evidence-bearing changed-strategy recovery packet;
- retry admission is bounded and exhaustion requires escalation;
- terminal completion is revised while completion artifacts or shared contracts remain unresolved;
- completion releases only after artifact and contract obligations are satisfied;
- native OpenClaw runtime loads all six hooks and both tools with zero plugin diagnostics;
- conversation access is explicitly enabled for the completion-finalization hook;
- the complete local suite contains eleven passing behavioral test scripts.

## Final validation (2026-08-06)

The plugin implementation and the requested one-task validations are complete.

- MultiAgentBench task 1 completed the planner → implementer → reviewer workflow. The final workspace contains `plan.md`, `solution.py`, `implementation.md`, and `review.md`; an independent `python3 solution.py` run exits 0 and prints `ALL TESTS PASSED`.
- CooperBench task 0 produced both independent `tiktoken/core.py` feature changes. The combined integration tree passes the repository suite plus both feature suites: **34 passed**.
- Live validation exposed and fixed stable root/run identity, workspace discovery across native prompt forms, downstream-role preservation, observer-owned workflow readiness, command-wrapper normalization, and exclusion of unscoped legacy dependencies from run-local gates.
- Post-validation analysis exposed one architectural omission: the plugin had consumer and root gates but not the ideal producer pre-finalization checkpoint. `before_agent_finalize` now observes the child workspace and revises an early producer completion before `subagent_ended`.
- The final plugin unit suite passes all eleven behavioral scripts.

The final evidence and caveats are recorded in `desgin/FINAL_VALIDATION.md`.

## Concurrent-run repair (2026-08-07)

The fresh five-task comparison exposed two live control-plane gaps that unit-only validation had missed:

- workspace phrases such as `workspace root (/path/plan.md)` were interpreted as a directory, so the observer checked `/path/plan.md/plan.md` and permanently blocked the consumer;
- OpenClaw intentionally ignores `before_agent_finalize` revision requests after a deterministic side effect such as `sessions_spawn`, allowing coordinators to end after “I will wait” even with unresolved obligations.

The plugin now remembers the authoritative root workspace, normalizes artifact-shaped workspace hints to their parent directory, correlates concurrent child spawns by label instead of FIFO order, and injects a mandatory continuation action directly into persisted spawn results. Producer tool results likewise carry a post-write completion/verification obligation because a finalization-only gate cannot reliably revise turns containing writes or commands.

Focused live validation produced all four ordered artifacts and independently executed `python3 solution.py` with exit 0 and exact stdout `memory-gate-ok`. The complete local suite now contains twelve passing behavioral scripts, including the workspace-path and continuation regressions.

Full repaired-plugin evaluation completed on five MultiAgentBench tasks and five CooperBench pairs. MultiAgentBench reached 5/5 complete workflows and 87/100 versus the unchanged 46/100 control. CooperBench reached 5/5 dual handoffs and 5/5 integrations, but only 3/10 official feature suites and 1/5 paired tasks passed, yielding 20/100 versus the 0/100 control. The remaining milestone is co-domain composition quality, not dependency handoff completion.

## Dynamic co-domain repair (2026-08-07)

The missing co-domain path is now implemented and covered by the plugin suite:

- peer `PATCH_READY.md` handoffs are treated as producer boundary evidence rather than private completion prose;
- when two or more handoffs exist, the plugin creates one versioned integration contract even if assignments declare different artifacts;
- the contract preserves each handoff's public signatures, defaults, validation, error behavior, changed paths, and test evidence as simultaneous integration acceptance criteria;
- it is injected into resumed coordinator turns and blocks root completion until the coordinator records real shared-boundary verification;
- universal assignment parsing now recognizes OpenClaw's absolute `working ONLY in the workspace directory: …` wording, and `Artifact:` declarations are retained as handoff ownership;
- `npm test` passes all thirteen behavioral scripts, including dynamic handoff discovery, coordinator injection, completion gating, and the OpenClaw workspace-phrase regression.

The first fresh live Cooper retry did not reach plugin execution because the configured benchmark provider timed out during the root's first LLM request. Earlier attempted retries that show empty handoffs are invalid: their gateway was restarted after the root yielded, interrupting live child sessions. Those runs must not be used as score evidence. A clean end-to-end Cooper score remains pending a successful provider run with the gateway held stable through child completion and integration.

Focused runtime tracing subsequently found one native-hook adapter detail: some OpenClaw spawn events omit `taskName` and `label` even though the child objective begins `You are <assignment>`. The plugin now derives the assignment from that objective as a fallback, so peer workspace registration and dynamic handoff discovery are preserved on that hook variant. The adapter regression is covered by the assignment test; the suite remains fully passing.
