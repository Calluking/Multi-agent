# Inject-only Testing Practice Memory — Five-Task Verification

## Configuration

- Date: 2026-08-03
- Branch: `experiment/test-driven-memory`
- Tasks: 5, 9, 11, 14, 20
- Condition: `testing`
- Dependency memory: disabled
- Co-domain memory: disabled
- Testing practice memory: enabled
- Model: `deepseek/deepseek-v4-flash`
- Repetitions: one
- Result root: `experiments/testing_memory_5tasks_20260803`

Testing memory remained inject-only. Every result records zero extra Agent calls,
no rerouting, and no automatic retry.

## Runtime results

| Task | Score (/5) | Workflow | Runnable | Implementer state |
|---:|---:|:---:|:---:|---|
| 5 | 5.00 | yes | yes | working |
| 9 | 1.00 | no | no | abandoned / incomplete turn |
| 11 | 1.00 | no | no | abandoned / incomplete turn |
| 14 | 5.00 | yes | yes | working |
| 20 | 5.00 | yes | yes | working |

- Mean Task Score: **3.40 / 5**
- Workflow complete: **3 / 5**
- Runnable: **3 / 5**

Task 9 and Task 11 each returned the same provider/Agent-level result:

```text
Agent couldn't generate a response. Please try again.
liveness_state: abandoned
error.kind: incomplete_turn
```

Both consumed roughly 8.3k output tokens before abandonment and produced no
`solution.py` or `implementation.md`. The Reviewer correctly refused to claim
success and marked every central requirement unsupported.

## Testing/TDD fault comparison

The original criterion is unchanged:

- `FAULT`: unresolved observed failures; tests validate an incorrect substitute;
  missing coverage of a central requirement followed by false approval; or a
  concrete defect is missed.
- `--`: the capability is exercised and no material Testing/TDD fault is observed.
- `NE`: no implementation/test opportunity exists, so success or failure cannot
  be established.

| Task | Original baseline | Testing memory | Interpretation |
|---:|:---:|:---:|---|
| 5 | FAULT | -- | Public authorization and overdue/report behavior are independently tested; no private-state fixture bypass or weakened oracle. |
| 9 | FAULT | NE | Implementer produced no artifact; no functional test could run. Reviewer explicitly rejected completion. |
| 11 | FAULT | NE | Implementer produced no artifact in this batch; Reviewer explicitly marked ML and all other requirements unsupported. |
| 14 | FAULT | -- | Tests exercise trace-based coverage, heatmap intensity, interactive hierarchy contract, collaboration/RBAC, version rollback, notifications, and dependency ordering; Reviewer found and repaired a duplication false positive. |
| 20 | FAULT | -- | Reviewer adds an independent collaboration counterexample and explicitly reports the networked-real-time limitation rather than treating an in-process lock/shared object as proof of network capability. |

Confirmed result for this batch: **3 faults removed, 0 confirmed remaining, 2 not
evaluable**. A `FAULT -> NE` transition is not counted as a repair.

## Evidence by task

### Task 5 — confirmed repair

- Default `python3 solution.py` executes 12 tests, exit 0.
- Unauthorized view, update, and comment paths raise `PermissionError` and leave
  state unchanged.
- Past deadlines are rejected through the public API.
- Report values are recomputed independently using a fresh scheduler.
- Reviewer documents that no test was weakened and that notifications arise from
  the real assignment/deadline paths.

### Task 9 — not evaluable

- Planner completed.
- Implementer ended `abandoned / incomplete_turn` and wrote no product artifact.
- Reviewer ran the default/import probes, observed the missing module, added no
  meaningless tests, and made no PASS claim.
- This avoids false approval but does not demonstrate a repaired test loop.

### Task 11 — not evaluable in this batch

- Planner completed.
- Implementer ended `abandoned / incomplete_turn` and wrote no product artifact.
- Reviewer recorded `solution.py` and `test_solution.py` as absent and marked the
  ML requirement unsupported.
- A separate earlier Task 11 ON run did produce a runnable fitted model and
  independent trending-versus-flat counterexamples, but that earlier observation
  is not substituted into this batch's count.

### Task 14 — confirmed repair

- Coverage is based on executed tracing; an unexecuted branch remains uncovered.
- The heatmap carries intensity and the complexity view exposes hierarchy,
  relationships, zoom, navigation, and exploration operations.
- Collaboration tests cover RBAC, commits, rollback, subscriber delivery, and
  dependency ordering.
- Reviewer found a real duplication false positive, repaired production code,
  added a regression test, and reran to 40/40.

### Task 20 — confirmed Testing-memory improvement

- Default entrypoint runs 15/15 checks, exit 0.
- Reviewer independently tests two-subscriber delivery and event ordering rather
  than accepting shared-state readback.
- The review explicitly states that genuine networked real-time collaboration is
  not implemented and does not claim network capability.
- This does not necessarily remove the separate cross-domain/product limitation;
  it removes the Testing false-assurance behavior being evaluated here.

## Interpretation

The inject-only memory changed what successful Agents tested and what Reviewers
were willing to approve. It did not improve Agent completion reliability. That is
the intended mechanism boundary: a practice packet can prevent false-green
verification, but it cannot create a missing implementation or recover an
abandoned turn without adding a separate dependency/recovery mechanism.

Because this is a one-repetition development panel, it does not establish a
statistical performance gain. The next clean experiment should use repeated runs
or combine Testing Practice Memory with Dependency Memory while preserving
separate feature flags.

