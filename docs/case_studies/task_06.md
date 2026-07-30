# Task 06 Case Study — ProjectOrganizer

## Task and scope

Task 06 requests a project-management application whose modules have an explicit dependency chain: task CRUD must precede scheduling; scheduling must precede resource allocation; resource allocation must precede notifications; and the UI may be developed concurrently but must be integrated last (`TASK.md:5-11`). The task also requests the create, revise, and optimize development phases (`TASK.md:17-20`).

The audit reads the planner, implementer, and reviewer JSONL sessions line by line and distinguishes faults visible during agent execution from failures produced afterward by the adapter/verifier.

| Category | Required verdict |
|---|---|
| Adaptive execution | **NO FAULT** |
| Cross-domain collaboration | **FAULT** |
| Dependency management | **NO FAULT** |
| TDD/testing-feedback collaboration | **NO FAULT** |

## Evidence sources

Workspace: `/home/luzh/mab_openclaw_clean_20260727/batch_01_10/task_06`

Raw traces:

- `/home/luzh/.openclaw/agents/mab-clean-batch-t06/sessions/mab-clean-batch-06-1785125285-planner.jsonl`
- `/home/luzh/.openclaw/agents/mab-clean-batch-t06/sessions/mab-clean-batch-06-1785125285-implementer.jsonl`
- `/home/luzh/.openclaw/agents/mab-clean-batch-t06/sessions/mab-clean-batch-06-1785125285-reviewer.jsonl`

Artifacts: `TASK.md`, `official_task.json`, `AGENTS.md`, `plan.md`, `solution.py`, `test_solution.py`, `implementation.md`, `review.md`, `failure.json`, and `result.json`.

Adapter: `/home/luzh/mab_openclaw_clean_20260727/batch_01_10/run_batch.py`.

## Timeline

1. **Planning.** The planner defines the intended product chain as `TaskManager -> TaskScheduler -> ResourceAllocator -> NotificationEngine`, with `ProjectOrganizerUI` integrated last (`plan.md:3-15,27-33`). It maps a deterministic test to each module and boundary (`plan.md:17-25`) and specifies standard-library unit tests (`plan.md:43-53`).

2. **Implementation begins from a clean workspace.** Implementer raw line 5 receives the build/test instruction. Lines 6-9 read `TASK.md`, `AGENTS.md`, and `plan.md`; lines 10-11 confirm that `solution.py` does not yet exist.

3. **Implementation and tests complete successfully.** At raw line 12 the implementer writes the full five-module `solution.py`. Later it creates the test suite and runs it; the recorded output at implementer line 49 reports all 54 tests passing. Lines 50-51 run `python3 solution.py demo` successfully and show the project-plan, resource-allocation, and notification views. Lines 52-53 write `implementation.md`, and line 54 summarizes the completed artifacts.

4. **Independent review exercises the system and repairs defects.** The reviewer reads all upstream artifacts, inspects requirements, and adds/rewrites the comprehensive test file. Reviewer lines 67-69 run 54 tests and the demo successfully. The final `review.md:22-30` records two findings: duplicate resource alerts were fixed by clearing alerts after polling, and misleading schedule-change reporting was simplified while preserving internal rescheduling behavior. The final review reports PASS with minor repairs (`review.md:1-4`).

5. **A post-agent verification command times out.** Only after planner, implementer, and reviewer have finished does the outer verifier execute bare `python3 solution.py`. Because the program enters its interactive CLI and waits at the prompt, `result.json:4-8` records compile exit 0, run exit 124, and the prompt text. `result.json:24-26` still shows no missing artifacts and workflow complete, but objective success false.

6. **A separate post-agent serialization error is recorded.** `failure.json:1-4` contains `TypeError('Object of type bytes is not JSON serializable')`. This is an adapter/evaluation artifact created after the work products and review exist; it is not feedback delivered to a working agent.

## Category evidence

### 1. Adaptive execution — NO FAULT

The agents respond effectively to every failure or concern that is actually visible while they still have an opportunity to act.

- The implementer begins with no `solution.py` (implementer lines 10-11), writes the system, runs 54 tests, runs the noninteractive demo, and documents both commands/results (implementer lines 12,49-54).
- The reviewer finds a genuine duplicate-dispatch problem in `NotificationEngine.poll_alerts` and repairs it. `review.md:24-26` states the old alert list was redispatched on every poll and that `clear_alerts()` was added after reading it.
- The reviewer also identifies unreliable change-list semantics in schedule recomputation and resolves the public behavior while verifying readiness and final schedule state (`review.md:28-30`).
- It reruns the complete suite and demo after its work; reviewer lines 68-69 show 54/54 passing and successful rendered output.

#### Why the timeout is not an adaptive fault

An adaptive fault requires feedback to be visible to an agent and a later opportunity for that agent to respond ineffectively. The timeout does not satisfy that temporal rule:

- All three agent stages had already ended when the verifier ran the bare entry point.
- The verifier used `python3 solution.py`, which intentionally enters an interactive CLI. The agents had verified the finite `python3 solution.py demo` path instead (implementer lines 50-51; reviewer lines 68-69).
- `result.json:6-8` shows the program was alive and waiting at `ProjectOrganizer Interactive CLI ... >`; it was not a crash.
- No subsequent agent stage received the exit-124 result. Therefore there was no later opportunity to adapt.

The same reasoning applies to `failure.json:3`: the bytes-serialization error belongs to post-agent packaging, not to an agent feedback loop. Adaptive execution is therefore **NO FAULT**.

### 2. Cross-domain collaboration — FAULT

Under the broadened definition, product-domain integration counts. Task 06 contains meaningful boundaries among task state, dependency scheduling, resource accounting, notification delivery, and UI visualization. Several crossings work, but a central required boundary remains materially incomplete.

#### Working product crossings

- `TaskScheduler` is constructed from `TaskManager`, and completion changes readiness/order; the full-workflow test confirms that completing T1 unblocks T2.
- `ResourceAllocator` validates tasks through the scheduler and prevents allocation beyond capacity; the suite exercises exact-cap, high-utilization, and over-allocation behavior.
- `NotificationEngine` consumes resource alerts and dispatches task/resource events to observers. The reviewer specifically repairs repeated alert delivery (`review.md:24-26`).
- `ProjectOrganizerUI` renders task schedule, resource usage, and notifications together. The implementer demo output at raw line 51 and reviewer rerun at lines 68-69 show all three views populated from shared state.

#### Materially incomplete real-time boundary

The specification requires real-time task/resource updates and notifications when tasks complete, resources are over-allocated, or due dates approach (`TASK.md:10`). The delivered cross-domain behavior is synchronous and manually triggered:

- `NotificationEngine.poll_alerts` is a polling boundary rather than an automatic resource-event subscription (`solution.py:541-599`, especially `poll_alerts` at line 585).
- Due-soon notification is an explicit API call, not a clock-driven connection between task due dates and notifications. The reviewer states this directly at `review.md:50-55`: there is no real-time clock, due-soon notifications must be called explicitly, and no automated approaching-due-date detection exists.
- The task judge likewise calls real-time behavior simulated polling/observer behavior rather than actual asynchronous push (`task_score.stdout.json:548`).
- The bare CLI is single-process and interactive; there is no background event loop or continuous task/resource monitoring that automatically crosses state changes into user-visible alerts.

Thus the modules are structurally wired, but the required task/resource-time -> notification -> user boundary is materially absent. Cross-domain collaboration is **FAULT**.

### 3. Dependency management — NO FAULT

The dependency chain is explicit, honored in the implementation, and successfully handed through the adapted workflow.

#### Product dependency chain

- The official ordering is stated in `TASK.md:7-11`.
- The plan preserves it exactly (`plan.md:27-33`).
- The implementation is laid out in the same order, and constructor injection enforces the runtime dependencies: scheduler receives task manager; allocator receives scheduler; notification engine receives allocator; UI is assembled over the completed components. The module entry points appear at `solution.py:209` (`complete_task`), `416` (`allocate`), `541` (`NotificationEngine`), and `607` (`ProjectOrganizerUI`).
- Integration tests and the successful demo prove that data flows through the completed chain rather than through isolated substitutes.

#### Workflow dependency chain

The adapted harness invokes planner, then implementer, then reviewer (`run_batch.py:194-211`). Here, unlike Task 03, each prerequisite artifact exists when the next stage uses it: the implementer reads the plan and produces solution/tests/implementation; the reviewer consumes them, repairs defects, reruns tests, and writes `review.md`. `result.json:24-25` confirms no missing required artifacts and workflow completion.

The official `official_task.json` describes creator/reviser/optimizer agent profiles, but `AGENTS.md` explicitly instructs the clean run not to use MARBLE profiles/actions. Therefore the official action-level workflow is not directly exercised; the adapted pipeline is explicitly labeled “adapted; not leaderboard-comparable” (`result.json:18-19`). Within the pipeline actually run, prerequisites and handoffs succeed. Dependency management is **NO FAULT**.

### 4. TDD/testing-feedback collaboration — NO FAULT

Testing is extensive, boundary-aware, and used to drive repair.

- The plan maps deterministic tests to each module and integration boundary (`plan.md:17-25,43-53`).
- The implementer runs 54 unit/integration tests and receives `OK` (raw line 49), then validates the demo separately (lines 50-51).
- Tests cover full workflow, CRUD validation, DAG cycles, dependency readiness, priority ordering, resource caps and utilization alerts, observers, due-soon notifications, UI output, empty-state rendering, and Unicode/edge inputs.
- The reviewer uses test feedback to fix duplicate alert dispatch (`review.md:24-26`) and clarify rescheduling results (`review.md:28-30`), then reruns the entire suite and demo successfully (reviewer lines 68-69).
- `review.md:15-20` records the exact final command and result: 54/54 passed, followed by a successful demo.

No testing feedback was dropped or left unresolved. The later verifier timeout uses an interactive invocation outside the test collaboration and, for the same temporal reason discussed above, does not reverse the TDD verdict. TDD/testing-feedback collaboration is **NO FAULT**.

## Official versus adapter interpretation

| Aspect | Official specification | Adapted run |
|---|---|---|
| Product order | CRUD -> scheduling -> resources -> notifications; UI integrated last (`TASK.md:7-11`) | Same order in plan and implementation |
| Development roles | Create -> revise -> optimize (`TASK.md:17-20`; profiles in `official_task.json`) | Planner -> implementer -> independent reviewer (`run_batch.py:194-211`) |
| Handoff result | Official MARBLE actions not exercised due clean-run instructions | All adapted artifacts handed off successfully |
| Final execution issue | Not part of official agent collaboration | Bare interactive invocation times out after agents finish |
| Comparability | Official benchmark workflow | Adapted/not leaderboard-comparable (`result.json:18-19`) |

## Conclusion

Task 06 shows why event timing matters. During the agent workflow, feedback was handled effectively: the implementation and tests were completed, the reviewer repaired real defects, and 54 tests plus the demo passed. The later timeout occurred only because the outer verifier launched an interactive CLI without input after all agents had finished; it was never visible to an agent with another opportunity to respond. Adaptive execution and TDD/testing-feedback collaboration are therefore **NO FAULT**.

The module and workflow prerequisite chains were preserved, so dependency management is **NO FAULT**. However, the product's promised real-time crossing remains polling/manual rather than automatic: due-date and resource state do not continuously generate user-visible updates. Under the broadened product-integration definition, cross-domain collaboration is **FAULT**.
