# M3 dependency-memory development results

## Status

M3 is the current development candidate. It passed the two-task mechanism pilot
and improved the aggregate result in a one-repetition, five-task screen. It has
not yet been validated with repeated five-task trials or on the 15-task holdout.

## Design evolution

- **M1:** sparse event-triggered blocker memory. It avoided startup DAG injection,
  but recovery could still end without a persisted artifact.
- **M2:** atomic first-write recovery. It reliably created runnable files, but its
  instruction to stop after a small scaffold caused Task 17 scores of 35 and 45.
- **M3:** checkpoint-then-complete. The first recovery action persists a runnable
  checkpoint, then bounded edits must cover top-level requirements. A recovered
  checkpoint retains `scaffold_handoff_incomplete` debt until `implementation.md`
  exists, so exit code 0 alone cannot establish completion.

## M3 mechanism pilot: Tasks 1 and 17, three repetitions

| Task | M3 scores | Workflow | Runnable | Interpretation |
|---|---:|---:|---:|---|
| 1 | 100, 100, 100 | 3/3 | 2/3 | Healthy quality preserved; one default-command timeout remains |
| 17 | 80, 70, 85 | 3/3 | 3/3 | Median 80, fixing M2's scaffold-finalization failure |

Against the existing matched C0 pilot across all six runs, M3 changed:

- mean Task Score: 85.83 → 89.17 (+3.33);
- workflow completion: 66.7% → 100%;
- runnable rate: 50% → 83.3%;
- mean paired wall-time ratio: 1.244×;
- mean paired token ratio: 0.932×.

The generic evaluator still reports `INCOMPLETE`: its failed-task score gate is
not met because C0's Task 17 judge scores were high despite execution/handoff
failures, and two stochastic pairs meet its severe-regression definition. This
must not be hidden; workflow, execution, and judge score measure different things.

## Five-task development screen: one repetition

| Task | C0 score | M3 score | Δ | C0 workflow | M3 workflow | C0 run | M3 run |
|---:|---:|---:|---:|:---:|:---:|:---:|:---:|
| 1 | 20 | 100 | +80 | No | Yes | No artifact | Pass |
| 2 | 85 | 85 | 0 | No | Yes | Pass | Pass |
| 5 | 95 | 100 | +5 | Yes | Yes | Pass | Pass |
| 15 | 95 | 90 | -5 | Yes | Yes | Pass | Pass |
| 17 | 85 | 70 | -15 | Yes | Yes | Exit 1 | Timeout |
| **Mean/rate** | **76** | **89** | **+13** | **60%** | **100%** | **60%** | **80%** |

Average wall time decreased from 374.9s (C0) to 278.7s (M3). The screen supports
advancing M3, but Task 17's noninteractive entrypoint remains an unresolved
runtime dependency. A narrow runtime-memory rule should trigger only after exact
timeout/EOF evidence; it must not alter healthy runs.

## Experimental boundaries

- Tasks 1, 2, 5, 15, and 17 are the development panel.
- The other 15 coding tasks remain held out.
- The five-task table is a screen with one repetition, not a stable estimate.
- Failed background launches caused by a missing non-login `PATH` are harness
  failures and are excluded; they contain no agent calls or scores.
- The interrupted sequential screen preserved only its completed Task 1 pair.
  Tasks 2, 5 and Tasks 15, 17 were then run in two matched shards.

## Next decision

Before holdout evaluation, add only the evidence-triggered noninteractive
entrypoint repair (timeout, EOF-on-input, or persistent-server evidence), rerun
Task 17 with Task 1 as the safety control, then repeat the five-task panel if the
runtime repair succeeds without reducing Task Score.
