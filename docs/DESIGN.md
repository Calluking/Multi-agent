# Design 1: memory-mediated orchestration for multi-agent coding

## Objective

Build a task-general memory system for four observed multi-agent coding faults:

1. adaptive task execution;
2. cross-domain integration;
3. dependency management;
4. test-driven development and verification collaboration.

Memory stores operational knowledge. The orchestrator determines when it is
extracted, who may retrieve it, when another turn is scheduled, and what evidence
is required before a blocker is considered resolved.

## Four memory types

| Memory | Visibility | Main fault | Contents |
|---|---|---|---|
| Instruction/procedural knowledge | Public, mostly read-only | Adaptive execution | Constraints, reusable recovery procedures, changed-strategy rules |
| Dependency/interface memory | Private working state; public contracts | Dependency management | Prerequisites, ownership, artifacts, readiness, interfaces, handoffs |
| Domain/integration knowledge | Public | Cross-domain integration | Schemas, APIs, terminology, compatibility and boundary decisions |
| Verification memory | Public policy/evidence; private diagnostics | TDD and adaptive execution | Commands, results, failures, diagnoses, repairs and retests |

## Common memory record

```yaml
schema_version: "1.0"
memory_id: "dependency:<run>:<role>:<subject>"
memory_type: dependency_state
scope:
  task_id: 17
  run_id: current_run
  recipient_role: implementer
  visibility: private
subject: solution.py
status: missing
expected: solution.py exists and passes python3 solution.py
observed: previous turn ended before a write persisted
evidence:
  source: runner
  stage: implementation
  error_kind: incomplete_turn
  writes_observed: 0
priority: 100
recovery_target: checkpoint_then_complete
resolved: false
```

Every state claim requires provenance. Intent such as “I will implement it” is
not evidence that an artifact exists or is verified.

## Extraction

Use deterministic extraction for observable runtime state:

- file creation, modification, absence, and version;
- compilation result;
- exact command, exit code, timeout, stdout and stderr;
- tool failure and stage termination;
- required report or handoff absence;
- artifact modification after its last verification.

Use semantic extraction only for relationships that events cannot establish,
such as a frontend expecting a backend schema or one module consuming another's
symbol. Semantic records begin as `proposed` or `unverified`; only execution
evidence can make them `verified`.

## Selection

Current-run state is selected before cross-task procedural memory:

```text
exact task/run
→ exact recipient role
→ current stage
→ unresolved/blocking status
→ exact artifact/error/interface
→ semantic + lexical similarity
→ recency and evidence confidence
```

Normally inject only the highest-priority blocker. Large startup memory blocks
were empirically harmful in the earlier comprehensive-DAG experiment.

## Injection points

| Hook | Information delivered |
|---|---|
| Agent activation | Role obligations and verified prerequisites |
| After failed command/tool result | Exact failure evidence and smallest changed action |
| Before dependency consumption | Artifact readiness and interface contract |
| Ownership transfer | Missing inputs, prior failure, recovery owner and next action |
| Before final report | Unresolved required artifacts and verification state |
| After repair | Result of rerunning the same command |

## Required adaptive loop

```text
observe exact result
→ extract unresolved blocker
→ select a materially changed strategy
→ deliver evidence to an agent allowed to edit
→ apply bounded repair
→ rerun the same verification
→ resolve only when evidence changes as expected
```

A failure produced by the last recovery cannot be called adaptive execution if
no subsequent agent receives it. This is an unresolved limitation of M3.

## Implemented prototype: M3

M3 is the tested private dependency-memory ablation.

### Trigger priority

```text
solution missing: 100
compile failure: 90
runtime failure: 80
recovered scaffold handoff incomplete: 70
review report missing: 50
implementation report missing: 40
```

### Checkpoint-then-complete

When `solution.py` is absent after an agent turn:

1. the first substantive recovery action must persist a runnable checkpoint;
2. the agent must continue with bounded edits rather than stop at the scaffold;
3. it implements an end-to-end slice for each top-level requirement;
4. it replaces placeholders and disconnected markers with working behavior;
5. it runs `python3 solution.py`, repairs failures, and writes the handoff report.

The orchestrator retains `scaffold_handoff_incomplete` debt when the checkpoint
runs but `implementation.md` is absent. Exit code 0 alone does not mean that the
task requirements are complete.

### Fail-open behavior

Memory extraction, rendering, or logging errors fall back to the matched generic
continuation prompt. Optional memory failure must not become task failure.

## Experimental result and revised claim

M3 performed well on the five tasks used during development, but the benefit did
not generalize to held-out Task Score:

| Split | C0 score | M3 score | Score delta | Workflow delta | Runnable delta |
|---|---:|---:|---:|---:|---:|
| Development tasks (5) | 76.00 | 89.00 | +13.00 | +40.0 pp | +20.0 pp |
| Held-out tasks (15) | 85.00 | 84.33 | -0.67 | +13.3 pp | +6.7 pp |

Therefore M3 is not the final method. It is evidence that sparse event-triggered
memory can improve artifact and workflow completion. It is not evidence that the
system solves dependency management or adaptive execution generally. In the two
held-out adaptive-fault tasks, Task 9 remained failed and Task 12 regressed.

## Next design requirement

The next version must be derived from the Task 9 and Task 12 failures and tested
without reusing the consumed holdout as a fresh test set. It should add a bounded
closed-loop verification opportunity after the final recovery and distinguish
artifact existence from semantic requirement coverage, while preserving the
sparse, evidence-triggered injection policy.

