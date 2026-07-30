# M3 held-out evaluation

## Protocol

- Held-out tasks: 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 18, 19, 20.
- Conditions: matched generic recovery control (`C0`) versus dependency-memory candidate (`M3`).
- One repetition per task and condition: 30 scored runs.
- Tasks 1, 2, 5, 15, and 17 are excluded because they were used for development.

## Per-task results

| Task | C0 score | M3 score | Delta | C0 workflow | M3 workflow | C0 run | M3 run |
|---:|---:|---:|---:|:---:|:---:|:---:|:---:|
| 3 | 75 | 70 | -5 | ✓ | ✓ | ✓ | ✓ |
| 4 | 95 | 90 | -5 | ✓ | ✓ | ✓ | ✓ |
| 6 | 100 | 95 | -5 | ✓ | ✓ | ✓ | ✓ |
| 7 | 100 | 100 | 0 | ✓ | ✓ | ✓ | ✓ |
| 8 | 90 | 90 | 0 | ✓ | ✓ | ✓ | ✓ |
| 9 | 20 | 20 | 0 | ✗ | ✗ | ✗ | ✗ |
| 10 | 100 | 100 | 0 | ✓ | ✓ | ✓ | ✓ |
| 11 | 100 | 90 | -10 | ✗ | ✓ | ✗ | ✓ |
| 12 | 100 | 70 | -30 | ✓ | ✗ | ✓ | ✓ |
| 13 | 80 | 95 | +15 | ✓ | ✓ | ✓ | ✓ |
| 14 | 80 | 95 | +15 | ✓ | ✓ | ✓ | ✓ |
| 16 | 95 | 90 | -5 | ✓ | ✓ | ✓ | ✓ |
| 18 | 70 | 85 | +15 | ✗ | ✓ | ✓ | ✓ |
| 19 | 75 | 90 | +15 | ✓ | ✓ | ✓ | ✓ |
| 20 | 95 | 85 | -10 | ✗ | ✓ | ✓ | ✓ |

## Aggregate

| Metric | C0 | M3 | Change |
|---|---:|---:|---:|
| Mean Task Score | 85.00 | 84.33 | -0.67 |
| Workflow completion | 73.3% | 86.7% | +13.3 pp |
| Runnable | 86.7% | 93.3% | +6.7 pp |
| Mean wall time | 288.0s | 305.5s | +6.1% |
| Mean stage tokens | 168,196 | 177,164 | +5.3% |

Task-score outcomes: 4 wins, 4 ties, and 7 losses for M3.

## Fault-subset result

The subsets below use the original trace-audit labels; they are descriptive,
not independent samples.

| Original fault subset | Held-out tasks | Mean score delta | Workflow delta | Run delta |
|---|---|---:|---:|---:|
| Adaptive execution | 9, 12 | -15.00 | -50.0 pp | 0 pp |
| Dependency management | 3, 4, 7, 9, 12, 19 | -4.17 | -16.7 pp | 0 pp |
| TDD/testing | 9, 11, 14, 20 | -1.25 | +50.0 pp | +25.0 pp |
| Cross-domain integration | 3, 4, 6, 9, 11, 13, 14, 16, 18, 19, 20 | +1.82 | +27.3 pp | +9.1 pp |

## Verdict

M3 improves artifact/workflow completion and runnable rate, but it does not
improve held-out Task Score and it regresses the two held-out tasks previously
classified with adaptive-execution faults. It therefore does **not** validate
the proposed dependency memory as a general solution to dependency management
or adaptive task execution.

The development-panel gain did not generalize. M3 should remain an ablation or
diagnostic prototype, not the final method. The next design must explain Task 12's
large regression and Task 9's unchanged failure before any additional benchmark
claim is made.
