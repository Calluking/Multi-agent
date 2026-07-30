# Memory-Management System for Multi-Agent Coding

## Goal

Design a memory-mediated orchestration system that improves performance on the four fault classes studied in the 20-task MultiAgentBench coding baseline:

1. Adaptive-execution faults
2. Cross-domain integration faults
3. Dependency-management faults
4. Test-driven development and verification faults

Memory answers **what the team knows**. Orchestration determines **when an agent must retrieve that knowledge, act on it, and demonstrate that the problem is resolved**. Both are required: merely storing an error does not ensure that an agent responds to it.

## Proposed memory types

| Memory type | Visibility | Principal fault addressed | Main contents |
|---|---|---|---|
| Instruction and procedural knowledge | Public, mostly read-only | Adaptive execution | Task constraints, reusable procedures, recovery strategies, benchmark rules |
| Dependency and interface memory | Private drafts; public contracts | Dependency management | Prerequisites, ownership, artifact state, interface definitions, handoffs |
| Domain and integration knowledge | Public | Cross-domain collaboration | Schemas, APIs, terminology, assumptions, compatibility decisions |
| Verification memory | Public policy and evidence; private diagnostic scratchpad | TDD and adaptive execution | Acceptance criteria, commands, results, failures, diagnoses, repair history |

## 1. Instruction and procedural knowledge

This memory includes the original instructions and reusable knowledge about how agents should operate and recover from observed failures.

Example:

```yaml
procedure: recover_from_oversized_generation
trigger:
  - output_limit_reached
  - proposed_full_rewrite
action:
  - preserve_existing_artifact
  - divide_change_into_small_patches
  - patch_one_component
  - compile_and_run
  - persist_progress_before_continuing
avoid:
  - regenerating_the_entire_program
```

This could help with Tasks 2, 9, 12, and 17, where an agent encountered a failure but repeated essentially the same unsuccessful strategy.

Instruction memory alone does not produce adaptive execution. The system must enforce a live feedback loop:

```text
observe result -> record diagnosis -> select a changed strategy -> act -> verify
```

The orchestrator must deliver runtime output to an agent and schedule an opportunity to repair the failure.

## 2. Dependency and interface memory

Not all dependency memory should be private.

- **Private working memory:** tentative plans, local reasoning, and incomplete assumptions.
- **Public contract memory:** information on which another agent's work depends.

Example shared contract:

```yaml
artifact: REST_API
owner: backend_agent
status: ready
depends_on:
  - data_model:v2
provides:
  endpoints:
    - method: POST
      path: /sessions
      request_schema: CreateSession
      response_schema: Session
consumers:
  - frontend_agent
verification:
  command: pytest tests/test_sessions.py
  result: passed
```

Artifact states should be explicit:

```text
planned -> in_progress -> produced -> verified -> ready_for_consumers
```

An artifact must not become available merely because its owner says that work was performed. A consumer may use it only after the relevant contract is verified. This would reveal Task 9's invalid imports before downstream work relied on them.

**Principle:** private reasoning is acceptable; cross-agent dependencies must be public.

## 3. Domain and integration knowledge

This public memory should emphasize boundary contracts instead of collecting large amounts of generic domain information.

Example frontend/backend integration entry:

```yaml
decision: session_transport
domains:
  - frontend
  - backend
chosen_contract:
  protocol: websocket
  url: /ws/sessions/{session_id}
  messages:
    client_to_server:
      - join
      - update_track
    server_to_client:
      - state_snapshot
      - participant_joined
      - track_updated
frontend_assumption:
  authentication: bearer_token
backend_assumption:
  authentication: bearer_token
compatibility_status: verified
```

The shared entry acts as a boundary object that different agents can retrieve and update. It targets failures such as:

- a backend being implemented while the frontend is omitted;
- machine learning being replaced by fixed heuristics;
- real-time communication being represented only by local callbacks or strings;
- independently generated components exposing incompatible interfaces.

## 4. Verification memory

Verification should not be purely private. It has three layers.

### 4.1 Public verification policy

Known before implementation begins:

```yaml
acceptance_criterion: program_starts
command: python3 solution.py
timeout_seconds: 120
expected:
  exit_code: 0
  interactive_blocking: false
```

### 4.2 Public verification ledger

Updated after every meaningful execution:

```yaml
attempt: 3
agent: implementation_agent
command: python3 solution.py
result: failed
error_type: ModuleNotFoundError
error: No module named "main"
affected_requirement: application_startup
diagnosis: pseudo-files were concatenated into one physical file
next_owner: implementation_agent
next_action: replace cross-file imports incrementally
resolved: false
```

### 4.3 Private diagnostic scratchpad

An agent may privately retain temporary hypotheses, exploratory commands, and noisy diagnostic details. Once a result affects another agent or the completion decision, the agent must promote it to the shared verification ledger.

Therefore, verification memory is:

```text
public policy + public evidence + private diagnostic workspace
```

This would prevent the Task 9 situation in which the reviewer had to rediscover the startup error instead of receiving a structured failure-and-repair handoff.

## Fault-to-mechanism mapping

| Fault class | Primary memory | Additional control mechanism |
|---|---|---|
| Adaptive execution | Procedural memory and verification history | Runtime-feedback delivery and retry scheduling |
| Cross-domain collaboration | Domain and integration memory | Explicit shared interface contracts |
| Dependency management | Dependency and interface memory | Readiness gates and ownership |
| TDD and testing collaboration | Verification memory | Repeated test-diagnose-repair-retest loop |

## Orchestrator rules

The first design should enforce at least these rules:

1. Before acting, an agent retrieves relevant instructions, dependency contracts, domain contracts, and unresolved verification history.
2. An agent cannot consume an artifact until its dependency state is `verified` or `ready_for_consumers`.
3. Every meaningful execution result is written to the verification ledger.
4. A failed attempt must produce a diagnosis and a materially changed next action.
5. Every unresolved failure must be assigned to a named owner.
6. Completion is prohibited while required verification entries remain unresolved.
7. Every memory entry records provenance: its author, supporting observation, timestamp or sequence number, and verification status.
8. When an agent approaches its output or time limit, it persists its artifacts, current state, unresolved errors, and next action before transferring ownership.

## Initial architectural model

```text
Task and user requirements
          |
          v
Instruction/procedural memory ---> Orchestrator
                                      |
                     +----------------+----------------+
                     v                                 v
             Agent private memory             Agent private memory
                     |                                 |
                     +------ shared dependency -------+
                     +------ shared domain contracts -+
                     |                                 |
                     +-------- execution environment -+
                                      |
                                      v
                         Shared verification ledger
                                      |
                                      v
                Orchestrator schedules repair or releases dependency
```

## Central design claim

The proposed system is not simply a vector database attached to multiple agents. It is a **memory-mediated orchestration system**: shared, structured memories preserve the team's operational state, while enforced retrieval, readiness gates, ownership, and feedback loops make agents use that state.

Without the control layer, the system could preserve Task 9's error perfectly while subsequent agents still ignore it or repeat the same failed response.

## Automatic dependency-contract generation prototype

The first dependency-memory implementation now includes an automatic semantic contract extractor. It consumes task text plus an external workflow description, validates the generated dependency DAG, folds non-independent product features into artifact acceptance criteria, and compiles complete YAML memory records. Runtime truth remains based on deterministic events and typed observations rather than model claims.

Implementation and findings are under:

```text
design/dependency_memory_experiment/
```
