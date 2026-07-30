# MultiAgentBench coding tasks 1-20: four-problem audit

## Scope

This audit covers the 20 coding tasks in the adapted OpenClaw mini-baseline. It is not leaderboard-comparable to the official MARBLE execution. Each task has a detailed trace-based case study in `case_study/task_NN.md`.

## Classification criteria

| Mark | Meaning | Evidentiary rule |
|:---:|---|---|
| ✓ | Confirmed fault | The capability was meaningfully exercised and the trace contains concrete evidence of a material failure. |
| -- | No observed fault | The capability was meaningfully exercised and completed without a material failure, including cases where agents successfully reacted to intermediate failures. |
| NE | Not exercised | The run never created the conditions needed to evaluate the capability; this is neither a pass nor a failure. |

### Adaptive task execution

- **✓** only when feedback or a failure was visible to a working agent, the agent had a later opportunity to respond, and its response was absent or ineffective.
- **--** when visible feedback was diagnosed and handled effectively, followed by appropriate verification.
- **NE** when no relevant failure or corrective feedback reached an agent before its final opportunity. A post-agent evaluator failure alone does not count.

### Cross-domain collaboration/integration

For this table, the broadened product-integration definition requested by the user is used. Frontend/backend, UI/functionality, ML/application, NLP/application, security/workflow, data/analytics, networking/state, visualization/engine, and comparable technical subsystem boundaries count even when generic agents implement them.

- **✓** when a meaningful multi-domain boundary is required and a required integration is materially missing, incompatible, simulated without the required behavior, or nonfunctional.
- **--** when the required domain boundaries are implemented and meaningfully exercised without a material defect.
- **NE** when the task contains no meaningful multi-domain boundary.

This column measures product integration. It does not prove collaboration between separately assigned domain-specialist agents.

### Dependency management

- **✓** when an explicit ordering, artifact handoff, or interface dependency is broken: downstream work starts without required inputs, required artifacts are absent, or components expose incompatible interfaces.
- **--** when relevant ordering and handoffs complete successfully and interfaces remain compatible.
- **NE** when the task/run contains no meaningful dependency to evaluate.
- A generic execution-command mismatch is not automatically a dependency-management fault.

### Test-driven development/testing collaboration

- **✓** when implementation/testing collaboration is exercised but fails materially: observed failures remain unresolved, tests validate incorrect substitutes, a central requirement lacks coverage and is falsely approved, or reliability verification misses a concrete defect.
- **--** when tests provide useful feedback, failures are diagnosed and repaired, regressions are rerun, and no material testing/review defect is observed.
- **NE** when no code/test artifact or test-feedback loop exists. Missing implementation alone is classified under handoff/dependency, not automatically TDD.
- Literal test-first ordering is not required for `--`; the evaluated construct is the iterative implementation-testing-feedback loop described in the benchmark paper.

## Final table

| Task | Adaptive execution | Cross-domain integration | Dependency management | TDD/testing collaboration |
|---:|:---:|:---:|:---:|:---:|
| 1 | NE | ✓ | -- | -- |
| 2 | ✓ | ✓ | ✓ | NE |
| 3 | -- | ✓ | ✓ | -- |
| 4 | -- | ✓ | ✓ | NE |
| 5 | -- | ✓ | -- | ✓ |
| 6 | -- | ✓ | -- | -- |
| 7 | -- | -- | ✓ | NE |
| 8 | NE | -- | -- | -- |
| 9 | ✓ | ✓ | ✓ | ✓ |
| 10 | -- | -- | -- | -- |
| 11 | -- | ✓ | -- | ✓ |
| 12 | ✓ | ✓ | ✓ | NE |
| 13 | -- | ✓ | -- | -- |
| 14 | -- | ✓ | -- | ✓ |
| 15 | -- | -- | -- | -- |
| 16 | -- | ✓ | -- | -- |
| 17 | ✓ | ✓ | ✓ | NE |
| 18 | -- | ✓ | -- | -- |
| 19 | -- | ✓ | ✓ | -- |
| 20 | -- | ✓ | -- | ✓ |

## Counts

| Category | Faults | No observed fault | Not exercised |
|---|---:|---:|---:|
| Adaptive execution | 4 | 14 | 2 |
| Cross-domain integration | 16 | 4 | 0 |
| Dependency management | 8 | 12 | 0 |
| TDD/testing collaboration | 5 | 10 | 5 |

## Confirmed-fault task IDs

- Adaptive execution: 2, 9, 12, 17
- Cross-domain integration: 1, 2, 3, 4, 5, 6, 9, 11, 12, 13, 14, 16, 17, 18, 19, 20
- Dependency management: 2, 3, 4, 7, 9, 12, 17, 19
- TDD/testing collaboration: 5, 9, 11, 14, 20
