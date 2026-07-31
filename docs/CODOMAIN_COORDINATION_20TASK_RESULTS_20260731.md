# Co-Domain Coordination Memory — 20-Task Run (2026-07-31)

## Configuration

- Tasks: MultiAgentBench coding Tasks 1–20
- Repetitions: one
- Condition: co-domain coordination memory only
- Dependency memory: disabled
- Main result root: `experiments/codomain_coordination_20tasks_20260731`
- Late-hook validation root: `experiments/codomain_coordination_latehook_fix_20260731`

Twenty deterministic mechanism tests passed before the batch.

## Main batch results

| Task | Mean score (/5) | Workflow complete | Runnable | Coordination records | Verified |
|---:|---:|:---:|:---:|---:|---:|
| 1 | 5.00 | yes | yes | 1 | 1 |
| 2 | 4.25 | yes | no | 0 | 0 |
| 3 | 4.25 | no | yes | 0 | 0 |
| 4 | 5.00 | yes | yes | 1 | 1 |
| 5 | 5.00 | yes | yes | 1 | 1 |
| 6 | 5.00 | yes | yes | 1 | 1 |
| 7 | 4.75 | yes | yes | 1 | 1 |
| 8 | 5.00 | yes | yes | 1 | 1 |
| 9 | 1.00 | no | no | 0 | 0 |
| 10 | 5.00 | yes | yes | 1 | 1 |
| 11 | 5.00 | yes | yes | 1 | 1 |
| 12 | 4.25 | yes | yes | 1 | 1 |
| 13 | 4.50 | yes | yes | 1 | 1 |
| 14 | 4.50 | yes | yes | 1 | 1 |
| 15 | 4.75 | yes | yes | 1 | 1 |
| 16 | 4.75 | yes | yes | 1 | 1 |
| 17 | 3.75 | yes | yes | 0 | 0 |
| 18 | 4.75 | yes | yes | 1 | 1 |
| 19 | 4.25 | yes | yes | 1 | 1 |
| 20 | 4.75 | yes | yes | 1 | 1 |

## Aggregate

| Metric | Result |
|---|---:|
| Mean task score | 4.475 / 5 |
| Score percentage | 89.5% |
| Workflow complete | 18 / 20 (90%) |
| Runnable artifact | 18 / 20 (90%) |
| Coordination records | 16 |
| Verified records | 16 |
| Failed records | 0 |
| Agent accept events | 10 |
| Audit verification events | 16 |
| Runtime open challenges | 0 |
| Stage errors | 0 |
| Total stage tokens | 3,240,601 |
| Sum of per-task wall time | 5,015.4 seconds |

The wall-time sum is about 83.6 minutes. The batch was executed serially, with a
detached continuation after the first foreground process was cleaned up.

## Why four tasks initially had no coordination record

The co-domain integration hook originally ran after the Implementer and before the
Reviewer. Tasks 2, 3, 9 and 17 had no `solution.py` at that hook because the
Implementer turn ended incomplete. Therefore no real artifact existed from which
to extract and repair a producer-to-consumer boundary.

- Task 3: Reviewer later produced a runnable artifact, but `implementation.md` was
  absent.
- Task 17: Reviewer later produced a complete runnable workflow.
- Task 2: Reviewer produced the required files, but `solution.py` still exited 1.
- Task 9: no `solution.py`, `implementation.md`, or `review.md` was produced.

This exposed a scheduling gap rather than an interface-schema error.

## Late-hook fix and validation

The runner now detects this sequence:

```text
no artifact after Implementer
    -> Reviewer creates or repairs artifact
    -> late co-domain integration
    -> initialize coordination pool
    -> boundary-aware late Reviewer
    -> audit verification event
```

Tasks 2, 3 and 17 were rerun to validate the change.

| Task | Score | Workflow | Runnable | Records | Verified | Late hook used |
|---:|---:|:---:|:---:|---:|---:|:---:|
| 2 | 1.00 | no | no | 0 | 0 | no artifact available |
| 3 | 4.50 | yes | yes | 1 | 1 | not needed in this rerun |
| 17 | 3.75 | yes | yes | 1 | 1 | yes |

Task 17 confirms that the late hook works. Task 3 confirms normal early extraction
when an artifact exists in that repetition. Task 2 confirms the intended mechanism
boundary: co-domain memory cannot negotiate an interface when no usable artifact
survives. Artifact recovery belongs to Dependency Memory.

Task 9 was not rerun because its original run never produced `solution.py`; the
late hook would correctly remain inactive without Dependency Memory.

Across the main batch and targeted validation, the co-domain mechanism successfully
created and verified records for 18 distinct tasks. Tasks 2 and 9 require recovery
before co-domain coordination can begin.

## Runtime negotiation behavior

The main batch persisted:

- 16 proposal records;
- 10 explicit Reviewer accept events;
- 16 audit verification events;
- no runtime challenge or revision event.

The absence of challenge/revision means that Reviewers accepted or directly
verified the proposed contracts in these single runs. It does not exercise every
state transition. Deterministic tests cover proposal, challenge, versioned revision,
stale-revision rejection, accept and verification.

## Interpretation

The 20-task run validates that the coordination pool works across varied coding
tasks without producing a failed interface record. It also reveals two limits:

1. Co-domain memory is downstream of artifact availability and cannot replace
   Dependency Memory.
2. The current Agent workflow tends to accept or verify contracts rather than use
   explicit challenge/revision events, so more adversarial producer/consumer role
   separation is needed to evaluate negotiation quality.
