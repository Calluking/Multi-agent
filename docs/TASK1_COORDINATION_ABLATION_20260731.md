# Task 1 Coordination-Memory Ablation — 2026-07-31

## Setup

- Task: MultiAgentBench coding Task 1
- Repetitions: 1 per condition
- Conditions: baseline, dependency only, co-domain only, both
- Model and runner: unchanged across the four-condition batch
- Main run root: `experiments/feature_ablation_task1_coordination_20260731`
- Compatibility-fix rerun: `experiments/feature_ablation_task1_coordination_fix_20260731`

## Four-condition batch

| Condition | Mean task score | Workflow complete | Runnable | Wall time | Total stage tokens | Coordination records | Agent events | Audit events |
|---|---:|:---:|:---:|---:|---:|---:|---:|---:|
| Baseline | 5.00/5 | yes | yes | 164.8 s | 122,494 | 0 | 0 | 0 |
| Dependency only | 5.00/5 | yes | yes | 188.2 s | 127,617 | 0 | 0 | 0 |
| Co-domain only | 5.00/5 | yes | yes | 248.7 s | 165,422 | 1 | 0 | 0 accepted |
| Both | 5.00/5 | yes | yes | 196.5 s | 155,131 | 1 | 1 accept | 1 verification |

The first co-domain-only run exposed an ID compatibility defect: the Reviewer
correctly wrote `interface:feedback_consumption`, while the legacy audit path
expected `feedback_consumption`. The end-to-end boundary passed, but the event was
rejected by bookkeeping. This was fixed by accepting both pool `memory_id` and
legacy `interface_id` formats.

## Co-domain compatibility-fix rerun

| Condition | Mean task score | Breakdown | Workflow complete | Runnable | Wall time | Total stage tokens | Records verified |
|---|---:|---|:---:|:---:|---:|---:|---:|
| Co-domain only, fixed | 4.75/5 | 5 / 5 / 5 / 4 | yes | yes | 267.5 s | 177,837 | 1/1 |

The corrected rerun accepted the audit event and persisted a verified coordination
record. The one-point quality deduction is a judge outcome for this single
stochastic run; there was no stage error, workflow failure, runtime failure or
memory rejection.

## Mechanism observations

### Dependency memory

No dependency blocker was observed in any Task 1 condition. Therefore the
dependency recovery mechanism was enabled in the dependency and both conditions,
but correctly did not schedule an unnecessary recovery turn.

### Shared coordination memory

The `both` condition exercised the complete successful lifecycle available in this
run:

```text
integration_agent proposal
    -> reviewer_agent accept
    -> reviewer_agent verification
    -> record status verified
```

The record was `interface:translation_to_exchange_stream`, covering the real
translation producer to shared conversation consumer path. The audit recorded
exact evidence for deterministic translation, ordered raw/translated messages,
two appended entries per send, unknown-word passthrough and the pre-unlock error.

The corrected co-domain-only rerun exercised:

```text
integration_agent proposal
    -> reviewer audit verification
    -> record status verified
```

No challenge/revision was necessary because the Reviewer found the proposed
contract compatible with the repaired implementation. Unit tests separately cover
challenge, versioned revision, stale-revision rejection and acceptance.

## Interpretation

Task 1 is ceiling-saturated in this batch: all four original conditions scored
5.00/5 and completed with runnable artifacts. It therefore verifies that the new
mechanism can run without breaking Task 1, but it does not demonstrate a score
improvement over baseline.

The cost is measurable. Relative to baseline, the `both` condition used about
32,637 additional stage tokens and 31.7 additional seconds. Co-domain-only runs
were more expensive because they add the integration and coordination/audit path.

A stronger effectiveness test should use tasks with observed cross-domain faults,
while retaining Task 1 as a non-regression case.
