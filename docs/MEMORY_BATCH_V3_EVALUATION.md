# Memory-Enabled 20-Task Regression Evaluation (v3)

## Verdict

The first generalized dependency-memory system **does not improve the benchmark overall**. It produces several strong recoveries, but its extraction failures, oversized/noisy checkpoints, and incomplete state reconciliation cause more regressions than improvements.

This run must not be reported as a successful 20-task result:

- 14/20 tasks reached scoring;
- 5/20 stopped during contract extraction or contract transfer;
- Task 20 was interrupted before starting;
- only 6/14 scored tasks produced a runnable solution;
- every scored task retained at least one unresolved memory record, including successful tasks.

## Score comparison

| Task | Baseline score | Memory v3 | Delta | Baseline workflow | Memory workflow | Memory run | Status |
|---:|---:|---:|---:|:---:|:---:|:---:|---|
| 1 | 85 | 20 | -65 | ✓ | ✗ | missing | Severe regression |
| 2 | 20 | 20 | 0 | ✗ | ✗ | missing | No improvement |
| 3 | 80 | 20 | -60 | ✓ | ✗ | missing | Severe regression |
| 4 | 80 | — | — | ✓ | — | — | Contract extraction failed |
| 5 | 75 | 90 | +15 | ✓ | ✓ | pass | Improvement |
| 6 | 85 | 30 | -55 | ✓ | ✗ | missing | Severe regression |
| 7 | 85 | 90 | +5 | ✗ | ✓ | pass | Dependency/workflow recovery |
| 8 | 90 | 95 | +5 | ✓ | ✓ | pass | Improvement |
| 9 | 60 | — | — | ✗ | — | — | Contract extraction failed |
| 10 | 85 | — | — | ✓ | — | — | Generated contract remained invalid |
| 11 | 85 | 20 | -65 | ✓ | ✗ | missing | Severe regression |
| 12 | 20 | 20 | 0 | ✗ | ✗ | missing | No improvement |
| 13 | 80 | 20 | -60 | ✓ | ✗ | missing | Severe regression |
| 14 | 75 | 90 | +15 | ✓ | ✓ | pass | Improvement |
| 15 | 85 | 85 | 0 | ✓ | ✓ | pass | Preserved baseline |
| 16 | 85 | — | — | ✓ | — | — | Contract-transfer FileNotFoundError |
| 17 | 20 | 75 | +55 | ✗ | ✓ | pass | Major dependency recovery |
| 18 | 80 | 20 | -60 | ✓ | ✗ | missing | Severe regression |
| 19 | 80 | — | — | ✗ | — | — | Generated file contracts lacked locations |
| 20 | 85 | — | — | ✓ | — | — | Batch interrupted before task start |

## Aggregate comparison

### Direct paired comparison (14 scored tasks)

| Metric | Baseline on same 14 | Memory v3 | Change |
|---|---:|---:|---:|
| Mean Task Score | 68.93% | 49.64% | **-19.29 points** |
| Workflow complete | 10/14 | 6/14 | **-4 tasks** |
| Runnable solution | 10/14 | 6/14 | **-4 tasks** |

Among the 14 paired tasks:

- 5 improved: Tasks 5, 7, 8, 14, and 17;
- 3 tied: Tasks 2, 12, and 15;
- 6 regressed: Tasks 1, 3, 6, 11, 13, and 18.

The original complete baseline mean was 72%. A direct 20-task memory mean is unavailable because six intended tasks were not scored. If missing runs are assigned zero solely as a coverage-adjusted diagnostic, the result is 34.75%; this is not a valid Task Score, but it illustrates system-level unreliability.

## Positive result: dependency-fault recovery

The strongest evidence of benefit is Task 17:

- baseline: 20%, no solution, incomplete workflow;
- memory v3: 75%, runnable solution, complete workflow;
- improvement: +55 points.

Task 7 also changed from incomplete to complete workflow while improving 85% to 90%.

These cases support the narrow hypothesis that an explicit unresolved-artifact checkpoint plus a second bounded recovery opportunity can repair some missing-handoff failures.

Tasks 2 and 12 show that the same mechanism is not sufficient: both remained at 20% with no implementation.

## Regression mechanism

The failed scored tasks generally contain only `plan.md`; the implementer and reviewer never materialized the required implementation artifacts. The automatically generated graphs were too detailed and the runner injected up to eight records per checkpoint.

Checkpoint overhead correlated negatively with execution:

| Outcome | Tasks | Mean total checkpoint bytes | Mean dependency records |
|---|---:|---:|---:|
| Runnable | 6 | 16,917 | 10.17 |
| Not runnable | 8 | 20,278 | 12.00 |

This is not proof of causation, but the traces show the familiar failure pattern: agents spend their first pass reading and reasoning over a large contract set, then reach an output limit or incomplete turn before the first persistent implementation write. The memory system therefore amplified the exact failure it was intended to solve.

## Contract-extraction reliability

Five tasks failed before task execution:

- Tasks 4 and 9: no parseable dependency YAML after three attempts;
- Task 10: an extracted dependency had no applicable stage;
- Task 16: contract-transfer `FileNotFoundError`;
- Task 19: generated file dependencies omitted required locations.

Task 20 did not start because the long-running batch was interrupted when the previous assistant turn ended.

Contract extraction is therefore only 15/20 on attempted tasks in this run, below the reliability required for a mandatory memory layer.

## State-model failure

All 14 scored tasks ended with unresolved memory records, including the six fully successful workflows. Causes include:

- semantic product requirements lacking an evaluator;
- abstract execution and handoff nodes not always mapped to runtime evidence;
- readiness vocabulary mismatches (`available`, `produced`, `verified`);
- duplicated views of the same artifact or stage transition;
- completion decisions evaluated before all updated states were reconciled.

Consequently, unresolved-memory count cannot yet be used as a completion metric.

## Design changes required before v4

1. **Fail open on extraction failure.** Invalid optional memory must not prevent the underlying task from running.
2. **Limit proactive injection to one current blocker.** Do not inject a whole task DAG.
3. **Separate obligations from product requirements.** Product coverage belongs in verification/domain memory unless it creates a real cross-agent dependency.
4. **Prefer deterministic workflow contracts.** Extract only task-specific interfaces semantically; derive ordinary stage artifacts directly from the workflow adapter.
5. **Require an atomic-write instruction only after a relevant failure.** Do not burden initially healthy tasks with recovery memory.
6. **Add a memory-off fallback.** If extraction, validation, or retrieval fails, execute the baseline workflow unchanged.
7. **Evaluate semantic nodes or exclude them from hard completion.** Unknown semantic state must not remain a permanent blocker.
8. **Run matched controls with identical extra turns.** The present run confounds memory with additional implementer/reviewer calls.

## Research conclusion

The experiment demonstrates that dependency memory can be beneficial for selected missing-handoff failures, but a mandatory automatically generated memory graph is harmful. The next system should be a sparse, event-triggered recovery layer—not a comprehensive dependency checklist injected into every agent stage.

