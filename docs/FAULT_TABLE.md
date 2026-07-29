# Four-fault comparison: baseline versus M3

Each cell is `baseline/M3`. The left mark is the original 20-task trace audit;
the right mark is the matched M3 run. M3 marks use its runtime result, reviewer
trace, final artifact, and strict judge findings—not Task Score alone.

- `✓`: capability was exercised and a material fault was confirmed.
- `--`: capability was exercised without an observed material fault.
- `NE`: capability was not exercised; this is neither success nor failure.

| Task | Adaptive execution | Cross-domain integration | Dependency management | TDD/testing collaboration |
|---:|:---:|:---:|:---:|:---:|
| 1 | NE/-- | ✓/-- | --/-- | --/-- |
| 2 | ✓/-- | ✓/✓ | ✓/-- | NE/-- |
| 3 | --/-- | ✓/✓ | ✓/-- | --/✓ |
| 4 | --/-- | ✓/✓ | ✓/-- | NE/-- |
| 5 | --/-- | ✓/-- | --/-- | ✓/-- |
| 6 | --/-- | ✓/✓ | --/-- | --/-- |
| 7 | --/-- | --/-- | ✓/-- | NE/-- |
| 8 | NE/-- | --/-- | --/-- | --/-- |
| 9 | ✓/✓ | ✓/✓ | ✓/✓ | ✓/NE |
| 10 | --/-- | --/-- | --/-- | --/-- |
| 11 | --/-- | ✓/✓ | --/-- | ✓/-- |
| 12 | ✓/✓ | ✓/✓ | ✓/✓ | NE/✓ |
| 13 | --/-- | ✓/-- | --/-- | --/-- |
| 14 | --/-- | ✓/-- | --/-- | ✓/✓ |
| 15 | --/-- | --/-- | --/-- | --/-- |
| 16 | --/-- | ✓/-- | --/-- | --/-- |
| 17 | ✓/✓ | ✓/✓ | ✓/-- | NE/✓ |
| 18 | --/-- | ✓/✓ | --/-- | --/-- |
| 19 | --/-- | ✓/✓ | ✓/-- | --/-- |
| 20 | --/-- | ✓/✓ | --/-- | ✓/✓ |

Example: `✓/--` means the baseline had a confirmed fault and the M3 run did
not show that fault. `--/✓` means a material fault was newly observed in M3.

## Original baseline counts

| Fault | Confirmed tasks | Count |
|---|---|---:|
| Adaptive execution | 2, 9, 12, 17 | 4 |
| Cross-domain integration | 1, 2, 3, 4, 5, 6, 9, 11, 12, 13, 14, 16, 17, 18, 19, 20 | 16 |
| Dependency management | 2, 3, 4, 7, 9, 12, 17, 19 | 8 |
| TDD/testing collaboration | 5, 9, 11, 14, 20 | 5 |

## M3 comparison counts

| Fault | Confirmed M3 tasks | Count | Change from baseline |
|---|---|---:|---:|
| Adaptive execution | 9, 12, 17 | 3 | -1 |
| Cross-domain integration | 2, 3, 4, 6, 9, 11, 12, 17, 18, 19, 20 | 11 | -5 |
| Dependency management | 9, 12 | 2 | -6 |
| TDD/testing collaboration | 3, 12, 14, 17, 20 | 5 | 0 |

These are single-run descriptive counts. They do not establish statistical
improvement, and M3 was tuned on Tasks 1, 2, 5, 15, and 17.

## Classification criteria

### Adaptive execution

`✓` requires visible runtime/user feedback, a later opportunity to respond, and
an absent or ineffective adaptation. `NE` applies when no relevant feedback
reached an agent before its final opportunity.

### Cross-domain integration

`✓` requires a meaningful technical boundary—such as frontend/backend,
UI/functionality, ML/application, NLP/application, data/analytics, networking/state,
or visualization/engine—and a materially missing, incompatible, simulated, or
nonfunctional integration.

### Dependency management

`✓` requires a broken ordering, artifact handoff, readiness, or interface
dependency. A generic command mismatch alone is not automatically a dependency fault.

### TDD/testing collaboration

`✓` requires a materially failed implementation-test-feedback loop: unresolved
observed failures, tests validating an incorrect substitute, missing coverage of
a central requirement followed by false approval, or missed concrete defects.
Literal test-first ordering is not required.
