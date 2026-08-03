# Inject-only Testing Practice Memory — 20-Task Results

## Configuration

- Model: `deepseek/deepseek-v4-flash`
- Workflow: OpenClaw Planner -> Implementer -> Reviewer -> Judge
- Testing Practice Memory: enabled
- Dependency Memory: disabled
- Co-domain Memory: disabled
- Runtime retries/rerouting: disabled
- Repetitions: one
- Targeted five-task root: `experiments/testing_memory_5tasks_20260803`
- Remaining fifteen-task root: `experiments/testing_memory_remaining15_20260803`

Every Agent received a role-filtered semantic-practice packet at its existing
start point. No extra Agent call, completion gate, rerouting, or automatic retry
was added.

## Aggregate comparison

| Metric | Original mini-baseline | Testing Memory | Change |
|---|---:|---:|---:|
| Mean Task Score | 3.600 / 5 | 3.638 / 5 | +0.038 |
| Mean score percentage | 72.0% | 72.75% | +0.75 pp |
| Workflow complete | 14/20 (70%) | 13/20 (65%) | -5 pp |
| Runnable | 14/20 (70%) | 14/20 (70%) | 0 pp |
| Mean injected text | 0 | 3,715 characters/task | +3,715 |
| Total stage-token accounting | not recomputed here | 2,478,620 | descriptive |
| Sum of task wall time | not recomputed here | 4,864.3 sec | descriptive |

These are independent single runs, not paired deterministic measurements. Large
per-task changes include stochastic incomplete turns and one infrastructure error.

## Per-task comparison

| Task | Baseline score | Testing score | Delta | Testing workflow | Testing runnable |
|---:|---:|---:|---:|:---:|:---:|
| 1 | 4.25 | 1.00 | -3.25 | no | no |
| 2 | 1.00 | 5.00 | +4.00 | yes | yes |
| 3 | 4.00 | 4.25 | +0.25 | yes | yes |
| 4 | 4.00 | 1.00 | -3.00 | no | no |
| 5 | 3.75 | 5.00 | +1.25 | yes | yes |
| 6 | 4.25 | 4.75 | +0.50 | yes | yes |
| 7 | 4.25 | 5.00 | +0.75 | no | yes |
| 8 | 4.50 | 5.00 | +0.50 | yes | yes |
| 9 | 3.00 | 1.00 | -2.00 | no | no |
| 10 | 4.25 | 1.00 | -3.25 | no | no |
| 11 | 4.25 | 1.00 | -3.25 | no | no |
| 12 | 1.00 | 4.50 | +3.50 | yes | yes |
| 13 | 4.00 | 4.75 | +0.75 | yes | yes |
| 14 | 3.75 | 5.00 | +1.25 | yes | yes |
| 15 | 4.25 | 4.75 | +0.50 | yes | yes |
| 16 | 4.25 | 5.00 | +0.75 | yes | yes |
| 17 | 1.00 | 4.00 | +3.00 | yes | yes |
| 18 | 4.00 | 4.75 | +0.75 | yes | yes |
| 19 | 4.00 | 1.00 | -3.00 | no | no |
| 20 | 4.25 | 5.00 | +0.75 | yes | yes |

## Incomplete and non-runnable outcomes

| Task | Outcome | Primary observed cause |
|---:|---|---|
| 1 | no artifacts | `unknown agent id` gateway/infrastructure error across stages |
| 4 | plan + review only | Implementer `abandoned / incomplete_turn`; no solution |
| 7 | runnable, workflow incomplete | Implementer abandoned; Reviewer produced solution/review but no `implementation.md` |
| 9 | plan + review only | Implementer `abandoned / incomplete_turn`; no solution |
| 10 | plan + review only | Implementer `abandoned / incomplete_turn`; no solution |
| 11 | plan + review only | Implementer `abandoned / incomplete_turn`; no solution |
| 19 | plan + review only | Implementer `abandoned / incomplete_turn`; no solution |

Tasks 2 and 8 also had abandoned Implementer turns, but the already-scheduled
Reviewer produced complete runnable artifacts. No recovery turn was added.

## Original five Testing/TDD-fault tasks

| Task | Baseline fault | Testing Memory | Interpretation |
|---:|:---:|:---:|---|
| 5 | fault | no fault observed | Public authorization/report behavior and oracle integrity independently tested. |
| 9 | fault | NE | No implementation; Reviewer refused false approval. |
| 11 | fault | NE | No implementation in this batch; Reviewer marked ML unsupported. |
| 14 | fault | no fault observed | Central visualization/collaboration properties exercised; concrete defect repaired and regression-tested. |
| 20 | fault | no fault observed | Independent collaboration counterexample and explicit capability limitation replaced false assurance. |

Confirmed in the targeted panel: three faults removed, zero confirmed remaining,
two not evaluable. `fault -> NE` is not counted as repair.

## What the other memories are needed for

The full run makes the mechanism boundary visible:

- **Testing Practice Memory** changes acceptance targets, evidence quality, and
  Reviewer approval behavior. It does not create missing code.
- **Private Dependency Memory** is the appropriate mechanism for abandoned
  Implementer turns, missing `solution.py`/`implementation.md`, and incomplete
  handoffs.
- **Co-domain Memory** is needed when complete artifacts exist but subsystem
  interfaces or semantic boundaries remain incompatible.
- **Adaptive Memory** would address whether an Agent changes behavior after
  runtime feedback; it is distinct from test-oracle quality.

## Interpretation

The score average is essentially flat (+0.038/5), runnable rate is unchanged,
and workflow completion is five percentage points lower. Testing Memory therefore
should not be presented as a general performance improvement from this run.

Its supported claim is narrower: on completed target tasks, retrieved practices
changed tests from proxy validation toward requirement-grounded evidence and made
Reviewers disclose unsupported capabilities. Overall reliability remains limited
by artifact/dependency failures, which this inject-only mechanism deliberately
does not recover.

