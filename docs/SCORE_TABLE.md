# C0 versus M3 score table

`C0` is the matched generic-recovery control. `M3` is checkpoint-then-complete
dependency memory. The development and holdout splits must be interpreted
separately because M3 was designed using the five development tasks.

## Five-task development screen

| Task | C0 score | M3 score | Delta | C0 workflow | M3 workflow | C0 run | M3 run |
|---:|---:|---:|---:|:---:|:---:|:---:|:---:|
| 1 | 20 | 100 | +80 | ✗ | ✓ | ✗ | ✓ |
| 2 | 85 | 85 | 0 | ✗ | ✓ | ✓ | ✓ |
| 5 | 95 | 100 | +5 | ✓ | ✓ | ✓ | ✓ |
| 15 | 95 | 90 | -5 | ✓ | ✓ | ✓ | ✓ |
| 17 | 85 | 70 | -15 | ✓ | ✓ | ✗ | ✗ |
| **Mean/rate** | **76.00** | **89.00** | **+13.00** | **60%** | **100%** | **60%** | **80%** |

## Fifteen-task held-out evaluation

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
| **Mean/rate** | **85.00** | **84.33** | **-0.67** | **73.3%** | **86.7%** | **86.7%** | **93.3%** |

Held-out Task Score outcomes: 4 M3 wins, 4 ties, and 7 losses.

## Combined descriptive table

The combined number is descriptive only; it is not a generalization estimate
because five tasks were used to develop M3.

| Metric | C0 | M3 | Change |
|---|---:|---:|---:|
| Mean Task Score, all 20 | 82.75 | 85.50 | +2.75 |
| Workflow completion, all 20 | 70% | 90% | +20 pp |
| Runnable, all 20 | 80% | 90% | +10 pp |

## Held-out fault subsets

| Original fault subset | Tasks | Mean score delta | Workflow delta | Run delta |
|---|---|---:|---:|---:|
| Adaptive execution | 9, 12 | -15.00 | -50.0 pp | 0 pp |
| Dependency management | 3, 4, 7, 9, 12, 19 | -4.17 | -16.7 pp | 0 pp |
| TDD/testing | 9, 11, 14, 20 | -1.25 | +50.0 pp | +25.0 pp |
| Cross-domain integration | 3, 4, 6, 9, 11, 13, 14, 16, 18, 19, 20 | +1.82 | +27.3 pp | +9.1 pp |

