# MultiAgentBench Coding Mini-Baseline (Tasks 1-20)

- Model: `deepseek/deepseek-v4-flash`
- Workflow: OpenClaw planner -> implementer -> reviewer
- Attempts: one clean attempt per task; no selective retries
- Scoring: MultiAgentBench task rubric plus adapted communication/planning judges
- Comparability: adapted experiment; not leaderboard-comparable

## Aggregate

- Workflow complete: 14/20
- Solutions produced: 17/20
- Compile pass: 17/20
- Run pass: 14/20
- Run timeout: 2/20
- Mean Task Score: 72.0%
- Mean adapted coordination: 84.0%

## Per-task results

| Task | Workflow | Solution | Compile | Run | Task Score | Adapted coordination | Missing handoff |
|---:|---|---|---|---|---:|---:|---|
| 1 | complete | yes | pass | pass | 85% | 100% | - |
| 2 | incomplete | no | fail | fail | 20% | 60% | implementation.md, solution.py, review.md |
| 3 | complete | yes | pass | pass | 80% | 100% | - |
| 4 | complete | yes | pass | pass | 80% | 100% | - |
| 5 | complete | yes | pass | pass | 75% | 100% | - |
| 6 | complete | yes | pass | timeout | 85% | 100% | - |
| 7 | incomplete | yes | pass | pass | 85% | 50% | implementation.md |
| 8 | complete | yes | pass | pass | 90% | 100% | - |
| 9 | incomplete | yes | pass | fail | 60% | 50% | implementation.md, review.md |
| 10 | complete | yes | pass | timeout | 85% | 100% | - |
| 11 | complete | yes | pass | pass | 85% | 100% | - |
| 12 | incomplete | no | fail | fail | 20% | 40% | implementation.md, solution.py, review.md |
| 13 | complete | yes | pass | pass | 80% | 100% | - |
| 14 | complete | yes | pass | pass | 75% | 100% | - |
| 15 | complete | yes | pass | pass | 85% | 100% | - |
| 16 | complete | yes | pass | pass | 85% | 100% | - |
| 17 | incomplete | no | fail | fail | 20% | 30% | implementation.md, solution.py, review.md |
| 18 | complete | yes | pass | pass | 80% | 100% | - |
| 19 | incomplete | yes | pass | pass | 80% | 50% | implementation.md |
| 20 | complete | yes | pass | pass | 85% | 100% | - |

## Interpretation

`Workflow incomplete` means an agent failed to produce a required artifact or handoff. It does not mean the harness crashed. A solution can therefore compile and run while the workflow is still incomplete. `Run timeout` means the submitted program did not terminate within the independent execution limit.
