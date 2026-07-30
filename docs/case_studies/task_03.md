# Task 03 Case Study — CollaborativeSchedulePlanner

## Task and audit scope

Task 03 asks for a collaborative team scheduler spanning several product domains: user/task management, task and team-member constraints, shared schedule collaboration and notifications, machine-learned preference adjustment, feedback-driven rescheduling, and schedule reporting/visualization. The primary requirements appear in `TASK.md:5-11`; the required development sequence—create, revise, optimize—appears at `TASK.md:17-20`.

This case study evaluates four fault classes from the raw line-oriented traces and final artifacts:

- adaptive execution;
- cross-domain collaboration, using the broadened definition in which integration between product domains counts even when generic agents perform the work;
- dependency management, with official and adapted workflows distinguished;
- TDD/testing-feedback collaboration.

The fixed classifications are:

| Category | Verdict |
|---|---|
| Adaptive execution | **NO FAULT** |
| Cross-domain collaboration | **FAULT** |
| Dependency management | **FAULT** |
| TDD/testing-feedback collaboration | **NO FAULT** |

## Evidence sources

Workspace: `/home/luzh/mab_openclaw_clean_20260727/batch_01_10/task_03`

Raw traces:

- `/home/luzh/.openclaw/agents/mab-clean-batch-t03/sessions/mab-clean-batch-03-1785124478-planner.jsonl`
- `/home/luzh/.openclaw/agents/mab-clean-batch-t03/sessions/mab-clean-batch-03-1785124478-implementer.jsonl`
- `/home/luzh/.openclaw/agents/mab-clean-batch-t03/sessions/mab-clean-batch-03-1785124478-reviewer.jsonl`

Key artifacts:

- `TASK.md`, `official_task.json`, `AGENTS.md`, `plan.md`;
- `solution.py`, `implementation.md`, `test_solution.py`, `review.md`, `result.json`;
- adapter: `/home/luzh/mab_openclaw_clean_20260727/batch_01_10/run_batch.py`.

## Timeline

1. **Planner establishes both architecture and an official-style handoff.** The planner reads the task in raw trace lines 6-8 and writes `plan.md` in line 11. The plan proposes `Agent1 (create_code) -> Agent2 (add missing features) -> Agent3 (optimize)` (`plan.md:3-9`) and designs the user/task, constraint, ML, feedback, notification, and reporting modules (`plan.md:13-48`).

2. **Implementer consumes the plan but fails before producing artifacts.** The implementer is instructed to create and test the solution at raw line 5, reads `TASK.md`, `AGENTS.md`, and `plan.md` at lines 6-9, then says it will create the solution at line 10. That model turn terminates with `stopReason: "length"`; line 11 closes the session. The stage metadata confirms only three `read` calls and no write or execution (`result.json:42-57`).

3. **Reviewer encounters a broken upstream handoff and recovers.** Reviewer raw line 5 requires reading and reviewing upstream outputs. Line 10 reports `ENOENT` for `solution.py`; line 11 reports `ENOENT` for `implementation.md`. At lines 12-14 the reviewer explicitly recognizes that the implementer produced no artifacts and decides to build the solution itself.

4. **Reviewer builds, tests, and audits the replacement.** The reviewer later runs the built-in suite, observes 16 passing checks, inspects a suspected team-member overlap, reasons through the concrete schedule, and determines that example is valid (reviewer line 24). It writes `implementation.md` at lines 24-25, creates an additional edge-case suite at lines 26-27, runs it at lines 28-29, and receives `22 passed, 0 failed`. It then writes the final review at lines 30-31 and reports both suites green at line 32.

5. **Final adapted verification succeeds.** `result.json:4-8` records compile and run exit 0. Lines 135-138 mark the run as adapted, with no missing artifacts, workflow complete, and objective success. The task judge nevertheless scores instruction following 3/5 because important product requirements remain partial (`task_score.stdout.json:548`).

## Category findings

### 1. Adaptive execution — NO FAULT

The relevant feedback loop is positively exercised at the reviewer stage.

- The reviewer receives explicit, actionable evidence that both required upstream artifacts are absent: `solution.py` and `implementation.md` return `ENOENT` in reviewer trace lines 10-11.
- It has a later opportunity to act and does so: lines 12-14 identify the failed implementer handoff and switch to building the solution.
- It then validates the replacement instead of merely claiming recovery. Reviewer line 24 records 16 passing built-in checks and a manual investigation of a suspected overlap. Lines 28-29 run the additional suite and report 22/22 passing.
- Final verification independently reports compile and run success (`result.json:4-8`) and no missing artifacts (`result.json:135-138`).

The response to visible failure was effective. The fact that the reviewer had to absorb implementation work is a dependency-management fault, but it is not an adaptive-execution fault: once the failure became visible, the agent changed course and completed a verified recovery.

### 2. Cross-domain collaboration — FAULT

Under the broadened definition, this task clearly exercises meaningful product-domain boundaries. The issue is not absence of specialist agents; it is defective or missing integration between required scheduling domains.

#### Availability does not reach the scheduler

The task requires users to share availability and the system to optimize from those constraints (`TASK.md:5,7`). `User.available_slots` is declared in `solution.py:22-25`, but there is no public method that records availability and `_assign_task` never reads it (`solution.py:464-514`). The identity/profile domain therefore fails to supply a required constraint to the scheduling domain.

#### Team-member occupancy is not propagated correctly

The scheduler checks all involved users when testing a candidate slot (`solution.py:489-503`), but after assignment it marks occupancy only for `task.owner_id` (`solution.py:509-513`). A task that includes Bob as a required team member does not reserve Bob's time for later tasks owned by Bob. This is a concrete broken crossing between team composition and resource scheduling.

The built-in “team-member constraint” check does not expose that defect: it merely verifies that a team task received some day (`solution.py:634-642`). Reviewer trace line 24 examines only the demo's particular non-conflicting arrangement and concludes it is fine; it does not test the missing occupancy propagation.

#### Feedback learning does not meaningfully select time slots

Feedback updates one hourly weight (`solution.py:161-168`, `209-228`), but task ordering uses the average of all 24 weights (`solution.py:453-458`). That average is constant across a user's tasks, and `_assign_task` never calls `score_hour`. Thus the feedback/ML domain is connected syntactically to re-optimization but does not drive the time-slot choice required by `TASK.md:9-10`.

#### Real-time collaboration is only an event log

`Notifier.broadcast` appends timestamped dictionaries to an in-process list (`solution.py:180-196`). There is no edit-session protocol, subscriber delivery, concurrency control, or real-time interface. The plan itself calls this a notification “simulation” (`plan.md:28-29`). The task judge reaches the same conclusion: the CLI and log are not a real-time collaborative interface, and the ML analysis is minimal (`task_score.stdout.json:548`).

These are material product-boundary failures, so cross-domain collaboration is **FAULT**, even though several simpler crossings—feedback triggering optimization and scheduled data feeding reports—do operate.

### 3. Dependency management — FAULT

There are two distinct workflow views.

#### Official workflow

The official task defines three developer phases: create, revise, optimize (`TASK.md:17-20`). `official_task.json:48-63` assigns corresponding constraints to three agents: agent1 must create; agent2 must revise/add missing functionality; agent3 must revise/optimize. The planner mirrors that dependency chain in `plan.md:3-9`.

That chain was not executed. The nominal implementer produced no `solution.py` or `implementation.md` (reviewer trace lines 10-14). No distinct create artifact was handed to a revision agent and then to an optimization agent. Instead, one downstream reviewer created the implementation and reviewed it in the same stage. The required temporal dependency and separation of responsibilities collapsed.

#### Adapted workflow

The adapter replaces the official roles/actions with planner, implementer, and independent reviewer prompts (`run_batch.py:194-211`) and labels the result “adapted; not leaderboard-comparable” (`run_batch.py:249`, `result.json:135`). Even within that adapted chain, the implementer-to-reviewer dependency failed: stage metadata shows the implementer made only read calls (`result.json:42-57`), while the reviewer discovered absent inputs and had to reconstruct the entire missing stage.

The eventual artifact completeness does not erase the failed handoff. Dependency management concerns whether prerequisite work was produced and consumed in the intended order; here it was not. Verdict: **FAULT**.

### 4. TDD/testing-feedback collaboration — NO FAULT

The testing-feedback workflow itself is exercised and closes successfully.

- The replacement implementation contains an executable deterministic suite. Reviewer trace line 24 records 16 passing built-in checks.
- The reviewer does not stop at the original checks. It creates `test_solution.py` in lines 26-27, covering invalid users/tasks, bad dependencies, empty schedules, repeat optimization, repeated feedback, reporting, and cycle detection.
- It runs that suite in lines 28-29 and obtains 22 passed, 0 failed.
- `review.md:19-68` documents both test groups and their exact commands/results; `result.json:4-8` independently verifies executable success.

No failing test feedback was ignored, miscommunicated, or left unresolved. The cross-domain defects above reflect requirement/modeling gaps in what was tested, but under this audit's category boundaries they do not establish a failure of the actual TDD/testing-feedback collaboration that occurred. The observed test cycle—construct, run, inspect, add coverage, rerun, document—completed successfully. Verdict: **NO FAULT**.

## Official versus adapted interpretation

| Question | Official task | Adapted run |
|---|---|---|
| Required roles | Creator → reviser → optimizer (`official_task.json:48-63`) | Planner → implementer → reviewer (`run_batch.py:194-211`) |
| Did the prerequisite handoff succeed? | No; the prescribed three-stage code evolution did not occur | No; implementer outputs were absent at reviewer start (reviewer lines 10-14) |
| Was recovery effective? | Official sequence still not restored | Yes; reviewer built and verified final artifacts |
| Comparability | Official MultiAgentBench workflow | Explicitly adapted/not leaderboard-comparable (`result.json:135`) |

This distinction explains why adaptive execution can be **NO FAULT** while dependency management is **FAULT**: recovery was effective, but the prerequisite chain itself failed.

## Conclusion

Task 03 is a useful mixed case. The reviewer reacted well to an upstream failure, created a runnable replacement, expanded the tests, and closed the testing loop; therefore adaptive execution and TDD/testing-feedback collaboration are **NO FAULT**. At the same time, the implementer-to-reviewer prerequisite collapsed, and the official create→revise→optimize chain was not honored; dependency management is **FAULT**. Finally, under the broadened product-integration definition, essential boundaries among availability, team-member occupancy, ML preference learning, scheduling, and real-time collaboration are missing or defective; cross-domain collaboration is **FAULT**.
