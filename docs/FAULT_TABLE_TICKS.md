# Four-fault occurrence table

This table describes faults observed in the original 20-task mini-baseline logs.
It does not mark whether the later M3 memory mechanism fixes the fault.

- `✓`: confirmed fault.
- `--`: capability exercised, but no material fault observed.
- `NE`: capability was not exercised, so the run is not evidence of success or failure.

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

| Fault | Confirmed tasks | Count |
|---|---|---:|
| Adaptive execution | 2, 9, 12, 17 | 4 |
| Cross-domain integration | 1, 2, 3, 4, 5, 6, 9, 11, 12, 13, 14, 16, 17, 18, 19, 20 | 16 |
| Dependency management | 2, 3, 4, 7, 9, 12, 17, 19 | 8 |
| TDD/testing collaboration | 5, 9, 11, 14, 20 | 5 |
