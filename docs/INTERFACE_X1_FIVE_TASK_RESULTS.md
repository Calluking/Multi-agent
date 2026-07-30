# X1 shared-interface memory: five-task development result

## Method

X1 adds shared interface memory on top of the M3 sparse dependency-recovery runner.
The planner writes at most three producer/consumer contracts, the runner validates
and bounds them, the implementer receives the obligations and invariants, and the
reviewer receives the same records plus boundary-test and audit instructions.

Development tasks: 1–5. All five had a confirmed baseline cross-domain fault.

## Outcomes

| Task | Baseline score | X1 score | Baseline workflow | X1 workflow | Cross-domain fault baseline/X1 | Finding |
|---:|---:|---:|:---:|:---:|:---:|---|
| 1 | 85 | 80 | ✓ | ✓ | ✓/✓ | Memory selected internal registration/database/CLI boundaries and missed the required web, 3D/audio, translation, and live-session crossings. |
| 2 | 20 | 100 | ✗ | ✓ | ✓/-- | Produced a runnable system and exercised order-state and delivery-routing crossings. |
| 3 | 80 | 20 | ✓ | ✗ | ✓/✓ | No solution artifact; three interface records remained failed. An earlier independent smoke run scored 85, showing high run-to-run instability. |
| 4 | 80 | 85 | ✓ | ✓ | ✓/✓ | Verified HTTP and SQLite boundaries but omitted the harder frontend, retailer ingestion, email, and genuine real-time boundaries. |
| 5 | 75 | 100 | ✓ | ✓ | ✓/-- | Added and tested the previously missing identity/authorization-to-task boundary. |

Aggregate score changed from 68.0 to 77.0. Workflow completion and runnable
artifacts remained 4/5. Confirmed cross-domain faults changed from 5/5 to 3/5.
These are single-run development observations, not a held-out effectiveness claim.

## Diagnosis

1. **Boundary discovery optimizes for easy interfaces.** Planner-generated records
   often describe internal calls already likely to work instead of the difficult
   boundary implied by the task.
2. **Agent-authored audits are too permissive.** A contract can be marked verified
   even while an important unselected product boundary remains absent.
3. **Three full records can still overload implementation.** Task 3 reproduced the
   incomplete-turn behavior that motivated sparse dependency memory.
4. **The mechanism can repair precise omissions.** Task 5 is the strongest example:
   the shared contract made authorization semantics and negative testing explicit.

## Required X2 changes

- Discover boundaries from official task requirements before planning, then bind
  them to planned components; do not let the planner choose only easy boundaries.
- Rank boundaries by externality and risk: required technology crossings,
  cross-user security, real-time/event behavior, and multi-party state invariants.
- Inject one current interface at a time rather than all records.
- Judge coverage against task-derived boundary candidates; an audit of selected
  records alone cannot establish cross-domain success.
- Use a matched control and repeated runs after X2 stabilizes.
