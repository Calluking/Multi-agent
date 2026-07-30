# Task 2 Case Study — FoodChain

## Task and audit scope

Task 2 asked for `FoodChain`, a single-file Python application integrating customer ordering, restaurant order management, delivery operations, adaptive routing and prioritization, customer feedback, notifications, and security. The official specification is preserved at:

- `/home/luzh/mab_openclaw_clean_20260727/batch_01_10/task_02/TASK.md`

This case study evaluates the execution trace under four fixed classifications. It uses the raw stage JSONL transcripts, generated artifacts, and recovered final result. The classifications are not inferred from the final score alone; each is tied to whether the relevant capability was required, exercised, and successfully completed.

## Verdict summary

| Category | Verdict | Short basis |
|---|---|---|
| Adaptive execution | **FAULT** | The implementer received a recoverable tool-size error and stated the correct recovery strategy, but did not execute it; the reviewer then recognized the missing deliverable and also failed to complete the recovery. |
| Cross-domain collaboration | **FAULT** | The product required integration across commerce, restaurant operations, logistics, adaptive optimization, feedback/notifications, and security, but no implementation artifact was produced. |
| Dependency management | **FAULT** | The planner handoff existed, but the implementer failed to produce the artifacts required by the reviewer; the downstream stage began with missing prerequisites and the workflow remained incomplete. |
| Test-driven development | **NE** | No executable implementation or test suite was created, so no red/green or test-feedback development loop occurred. |

## Execution timeline

1. **Official task defines a multi-domain delivery platform.** `TASK.md:5-13` requires customer browsing and ordering, restaurant accept/reject/modify operations, delivery tracking, adaptive route/priority/ETA changes, ratings, cross-party notifications, and secure login/encrypted transmission.

2. **Planner produces an integration design.** `plan.md:7-12` separates models, storage, business services, and role-specific interfaces. `plan.md:15-23` maps all seven official requirements. `plan.md:43-83` defines Auth, Restaurant, Order, Delivery, Notification, and Feedback service contracts. `plan.md:99-123` proposes deterministic tests spanning those interfaces.

3. **Implementer reads all required inputs.** In `/home/luzh/.openclaw/agents/mab-clean-batch-t02/sessions/mab-clean-batch-02-1785124283-implementer.jsonl:5-9`, the adapter instructs the implementer to read `TASK.md`, `AGENTS.md`, and `plan.md`; the trace records successful reads.

4. **Implementer attempts one oversized monolithic write.** The raw implementer transcript at `implementer.jsonl:10` shows a `create_code` call containing the intended integrated application. At `implementer.jsonl:11`, the tool rejects it because the code exceeds the 12,000-character maximum.

5. **Implementer identifies but does not perform the recovery.** At `implementer.jsonl:12`, it says, “Too long for create_code. I'll split it up,” but the turn ends with `stopReason:"length"`. No subsequent write occurs, and `implementer.jsonl:13` closes the session. Consequently, neither `solution.py` nor `implementation.md` exists.

6. **Reviewer starts without its required prerequisites.** `/home/luzh/.openclaw/agents/mab-clean-batch-t02/sessions/mab-clean-batch-02-1785124283-reviewer.jsonl:5-11` shows the reviewer trying to read the task, plan, solution, and implementation report. Lines 10-11 return `ENOENT` for `solution.py` and `implementation.md`.

7. **Reviewer diagnoses the broken handoff.** `reviewer.jsonl:12-15` confirms the missing files, lists the workspace, and inspects the implementer output. At `reviewer.jsonl:16`, the reviewer states that it must build the solution itself, but that response also terminates with `stopReason:"length"`; `reviewer.jsonl:17` ends the session without any repair artifact.

8. **Recovered final result confirms total implementation failure.** `/home/luzh/mab_openclaw_clean_20260727/batch_01_10/task_02/result.json:4-8` reports `solution.py missing`; lines 9-15 assign all four objective scores a value of 1; lines 23-27 list `implementation.md`, `solution.py`, and `review.md` as missing; lines 28-29 mark `workflow_complete:false` and `objective_success:false`.

## Adaptive execution — FAULT

The adaptive-execution capability was directly exercised by visible, recoverable feedback.

The implementer’s first construction attempt was rejected for exceeding the tool limit (`implementer.jsonl:10-11`). This was not a hidden evaluator failure or a post-run judgment: the error was returned inside the active implementer turn. The implementer correctly recognized the necessary strategy—split the implementation into smaller writes—at `implementer.jsonl:12`. However, it never issued the promised follow-up write, never produced a partial file, and never ran tests. The opportunity to adapt existed, the appropriate adaptation was identified, and execution still stopped.

The reviewer provided a second recovery opportunity. It observed the missing files directly (`reviewer.jsonl:10-13`), inspected the preserved implementer output (`reviewer.jsonl:14-15`), and explicitly decided to implement the application itself (`reviewer.jsonl:16`). That attempt also ended on output length before any file was created.

This is therefore **FAULT**, not “not exercised”: two agents received actionable failure state while they still had authority to continue, but neither converted its diagnosis into a successful recovery.

## Cross-domain collaboration — FAULT

Under the broadened definition, product-level integration counts even though the execution agents had generic planner/implementer/reviewer roles.

The official product has several meaningful boundaries:

- Customer discovery and ordering (`TASK.md:7`)
- Restaurant inventory/order decisions (`TASK.md:8`)
- Delivery assignment and live status (`TASK.md:9`)
- Logistics adaptation using route, priority, ETA, real-time data, and feedback (`TASK.md:10`)
- Restaurant and delivery quality feedback (`TASK.md:11`)
- Notifications spanning all parties (`TASK.md:12`)
- Authentication and protected data transmission (`TASK.md:13`)

The plan makes those integrations concrete. It defines shared data models and repositories (`plan.md:7-12`, `plan.md:25-41`), then specifies Auth, Restaurant, Order, Delivery, Notification, and Feedback service boundaries (`plan.md:43-83`). Its proposed tests include order state transitions, delivery lifecycle, adaptive priority, ETA recalculation, feedback aggregation, and all-party notification fan-out (`plan.md:99-123`). Thus the cross-domain boundary was meaningful and explicitly placed in scope.

It failed materially because no `solution.py` was ever written. There is no implemented interface between customer orders and restaurant decisions, no transition into delivery tasks, no feedback-driven routing, no notification fan-out, and no security boundary. The recovered result’s missing-solution finding (`result.json:4-8`) and missing artifact list (`result.json:23-27`) establish that this was not merely incomplete test coverage. The entire integrated product was absent.

## Dependency management — FAULT

The adapter established a sequential artifact dependency:

`planner → plan.md → implementer → solution.py + implementation.md → reviewer → review.md`

The planner satisfied its immediate handoff by writing `plan.md`. The implementer successfully consumed it (`implementer.jsonl:6-9`) but failed to produce either downstream prerequisite. The reviewer nevertheless launched and immediately encountered `ENOENT` for both files (`reviewer.jsonl:10-11`). Although the reviewer recognized the dependency failure, it did not restore the missing artifacts before its own session ended (`reviewer.jsonl:16-17`).

The final artifact state is exact evidence of the broken chain: `result.json:23-27` lists all three implementation/review deliverables as missing, and `result.json:28-29` marks the workflow and objective unsuccessful. This is a dependency-management fault because a required upstream deliverable was not completed before the dependent review stage, and the fallback repair path also failed.

## Test-driven development — NE

TDD is **not exercised** in this trace.

The plan contains a detailed proposed test matrix (`plan.md:99-123`), but planning tests is not a TDD feedback loop. The implementer never created `solution.py`, never created a test file, and never invoked an execution tool after the rejected oversized write (`implementer.jsonl:10-13`). The reviewer likewise never reached code or test creation (`reviewer.jsonl:10-17`). Final verification could not compile or run anything because the solution was absent (`result.json:4-8`).

There is therefore no observable test-first cycle, failing test, production-code correction, regression run, or cross-stage test feedback. The correct classification is **NE**, rather than FAULT: the workflow failed before test-driven development could begin.

## Official task versus adapter behavior

The official task specifies the product and a generic three-step developer process—create, revise, optimize (`TASK.md:19-22`). It does not define planner, implementer, reviewer, artifact handoffs, tool-size limits, or recovery behavior.

Those execution mechanics came from the adapted harness. The implementer prompt in `implementer.jsonl:5` required reading the plan, creating `solution.py` with deterministic executable tests, running it, fixing failures, and writing `implementation.md`. The reviewer prompt in `reviewer.jsonl:5` required reading those outputs, repairing the solution, adding tests, rerunning, and writing `review.md`.

Accordingly:

- The **cross-domain fault** is judged against the official product requirements: none of the required integrations was implemented.
- The **adaptive and dependency faults** arise from adapter-stage behavior: recoverable feedback and explicit artifact handoffs were mishandled.
- The **TDD NE** classification reflects the adapter’s requested testing workflow never reaching an executable test cycle.
- The run is explicitly marked `adapted; not leaderboard-comparable` in `result.json:17-18`; this does not change the factual trace classifications.

## Conclusion

Task 2 failed before implementation could stabilize. The planner produced a credible multi-domain design, but the implementer used an oversized single write, did not execute its own proposed split-write recovery, and left the reviewer without the artifacts it depended on. The reviewer diagnosed the broken handoff but also exhausted its turn before creating files. As a result, the product’s customer, restaurant, delivery, optimization, feedback, notification, and security domains were never integrated, while no executable test loop ever began.

Final classifications: **Adaptive = FAULT; Cross-domain = FAULT; Dependency = FAULT; TDD = NE.**
