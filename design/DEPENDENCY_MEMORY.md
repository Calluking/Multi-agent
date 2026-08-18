# Dependency Memory — Universal Architecture Specification

## 1. Purpose

Dependency Memory preserves and enforces the concrete obligations that connect work in a multi-agent run.

It answers:

> What has been promised, what does it depend on, what evidence shows its current state, who currently owns it, and what may proceed?

Its operational purpose is to maintain a live dependency graph that guides the
root orchestrator's scheduling decisions. The graph computes which assignments
or assignment phases are ready to spawn, which must wait, and which owner must
recover a failed prerequisite. An agent must not be spawned into work whose
required inputs are still unavailable, because it cannot complete that work
correctly and will otherwise waste a turn or produce invalid output.

Dependency Memory is not a workflow template. It must not assume planners, implementers, reviewers, a fixed number of agents, or files such as `plan.md` and `review.md`.

The starting request is the authority. Agent spawning remains the harness and root agent's decision.

## 2. Non-negotiable invariants

1. Initial obligations come only from explicit user/task requirements.
2. The memory system never invents a role, agent, artifact, command, or handoff.
3. Actual spawn assignments may extend the graph dynamically.
4. Statements of intent are not completion evidence.
5. Artifact existence is not verification evidence.
6. Modifying an artifact invalidates verification tied to an older version.
7. A consumer cannot be released while a required prerequisite is unresolved.
8. Root completion is checked even when no subagent was spawned.
9. Model truncation, cancellation, timeout, or tool-call truncation cannot be treated as successful completion.
10. Private reasoning is never promoted into shared memory; only observable commitments and state are shared.
11. The graph, not role names or a fixed workflow, determines the current spawn-ready set.
12. Independent branches remain spawnable in parallel; an unrelated unresolved dependency cannot serialize them.
13. An upstream agent ending is not sufficient to release a consumer; the exact required output state must be satisfied.
14. Readiness may be defined at assignment-phase granularity so useful independent preparation can begin before a later dependency is ready.

## 3. Authority hierarchy

When sources disagree, use this order:

```text
explicit user request
  > benchmark/task contract
  > explicit child assignment accepted by the harness
  > observed artifact and command evidence
  > agent status report
  > inferred semantic relationship
```

An inferred dependency may be proposed, but it cannot silently become required.

## 4. Graph model

The dependency graph contains obligation nodes and typed edges.

### 4.1 Obligation node

```yaml
obligation_id: run-42:root:solution
run_id: run-42
scope: root
source:
  type: starting_request
  evidence_ref: prompt:final-deliverable
owner:
  kind: root_agent
  id: root
required_outputs:
  - artifact: solution.py
acceptance:
  - kind: exists
    artifact: solution.py
state: unresolved
evidence: []
```

### 4.2 Dynamic child obligation

Created only after an actual spawn/delegation event:

```yaml
obligation_id: run-42:child-7:api-contract
run_id: run-42
scope: child
source:
  type: spawn_assignment
  evidence_ref: event:spawn-193
owner:
  kind: child_agent
  id: child-7
required_outputs:
  - artifact: api/schema.json
acceptance:
  - kind: exists
    artifact: api/schema.json
consumer_ids:
  - child-9
state: unresolved
evidence: []
```

### 4.3 Edge types

- `requires`: an obligation cannot begin or complete without another obligation.
- `produces`: an agent or obligation produces an artifact/state.
- `consumes`: an agent or obligation consumes an artifact/state.
- `blocks`: an unresolved obligation currently blocks another transition.
- `invalidates`: a change makes prior evidence stale.
- `supersedes`: a newer obligation or artifact version replaces an older one.

Graph identity is based on structured fields, not descriptive prose:

```text
run + source commitment + owner + output/subject + consumer
```

### 4.4 Dependency requirements and spawn readiness

Every incoming dependency edge declares the minimum state needed by its
consumer. The system must not assume that every edge requires full
verification:

- `requires_produced`: the required artifact or state exists at a current version.
- `requires_accepted`: the required artifact or contract has been explicitly accepted.
- `requires_verified`: the required acceptance check passed against the current version.
- `requires_complete`: the complete upstream obligation has finished successfully.

The backend computes a ready set from these exact requirements:

```text
ready_set(graph) =
  unresolved assignments or phases
  whose required incoming dependency edges are satisfied
  and whose owners are not already active or exhausted
```

Example sequential graph:

```text
A produces schema
        -> B implements against schema
        -> C verifies the integrated behavior

ready initially: A
ready after current schema is produced/accepted: B
ready after B's required output is verified: C
```

An upstream agent merely stopping does not release the next node:

```text
A ended
  + schema missing, stale, or invalid -> B remains blocked; recover A's obligation
  + schema satisfies the edge         -> B enters the ready set
```

Example parallel join:

```text
A -> artifact A --+
                   +-> C
B -> artifact B --+
```

`A` and `B` may spawn together. `C` enters the ready set only when both of its
required incoming edges are satisfied.

When an assignment contains useful work before a dependency is available, the
orchestrator may model phases instead of spawning an agent into an entirely
blocked assignment:

```text
B.prepare    requires nothing -> spawnable
B.integrate  requires A       -> blocked until A is ready
```

Phase splitting must come from an explicit assignment decomposition or an
accepted orchestration decision. It must not silently weaken a real dependency.

## 5. Lifecycle

```text
proposed
  -> accepted
  -> in_progress
  -> produced
  -> verified
  -> ready
  -> consumed
  -> complete
```

Exceptional states:

- `blocked`: a prerequisite or required output is missing or invalid.
- `failed`: attempted work or verification failed.
- `stale`: evidence refers to an older artifact version.
- `cancelled`: the authoritative task or assignment was explicitly withdrawn.
- `orphaned`: the owner terminated without satisfying or transferring the obligation.

Only deterministic observation or explicit authority can advance state. An agent saying “done” cannot advance a node by itself.

## 6. Graph construction

### 6.1 Initial graph from the starting request

Extract only explicit obligations:

- requested deliverables;
- explicit ordering constraints;
- explicit required checks;
- explicit acceptance conditions;
- explicitly assigned participants, if present.

Example request:

```text
Write the complete answer to solution.py.
```

Correct initial graph:

```text
solution.py exists -> root may complete
```

Incorrect initial graph:

```text
planner -> plan.md -> implementer -> implementation.md -> reviewer -> review.md
```

### 6.2 Runtime graph extension

When the root voluntarily spawns a child:

1. Capture the exact assignment.
2. Extract concrete promised outputs and acceptance conditions.
3. Ask for explicit declaration only if the assignment is ambiguous and the harness supports it.
4. Add the child obligation.
5. Link it to known consumers only when a real handoff exists.
6. Never rewrite the original starting request.

### 6.3 Semantic inference

Semantic inference may discover probable code/data dependencies. These enter as `proposed` edges with source citations. They become required only after:

- explicit agent agreement;
- deterministic evidence such as an import/API reference; or
- a failed integration check proving the dependency.

## 7. Observation and reconciliation

The observer consumes normalized harness events:

| Event | State effect |
|---|---|
| Root prompt accepted | Create explicit root obligations |
| Child spawned | Create assignment-scoped obligation |
| Child assignment updated | Version or supersede its obligation |
| File write/edit succeeds | Mark matching output `produced`; invalidate old verification |
| File missing/read error | Mark exact output `blocked` |
| Command succeeds | Attach versioned verification evidence |
| Command fails | Mark affected obligation `failed` or `blocked` |
| Child terminates | Reconcile outputs; mark unresolved commitment `orphaned` |
| Root attempts completion | Evaluate all authoritative root blockers |
| Model stops for length | Reconcile incomplete tool call and unresolved outputs; schedule continuation |
| Run cancelled | Mark unresolved obligations `cancelled`, not failed |

Reconciliation is idempotent and based on artifact versions and event IDs.

## 8. Private and shared projections

The store may contain shared observable state, while delivery remains sparse.

### Owner-private projection

- the owner's accepted obligations;
- its current blockers;
- exact evidence from its own work;
- the next smallest dependency-relevant action.

### Consumer projection

- required upstream artifact/state;
- observable readiness;
- verification status;
- recovery owner;
- no upstream private reasoning.

Example:

```text
DEPENDENCY CHECKPOINT
- Waiting for: api/schema.json from child-7
- State: produced, not verified
- Required check: python scripts/validate_schema.py
- Consumer action remains blocked
```

## 9. Control rules

### Spawn/readiness gate

Before spawning an assignment or releasing its next phase, query the backend's
ready set. Allow the spawn only when every required incoming edge for its first
executable phase is satisfied.

Block only when the proposed child action has a real unresolved prerequisite.
Do not block unrelated parallel work. Do not release a consumer merely because
its producer agent terminated; inspect the required artifact, contract, state,
or verification evidence instead.

When a prerequisite is unresolved, return a structured scheduling decision:

```text
decision: wait
consumer: child-9
blocked_by: run-42:child-7:api-contract
required_state: verified
observed_state: produced
recovery_owner: child-7
next_action: run the declared schema validation against the current artifact
```

When all prerequisites become ready, notify the orchestrator that the consumer
has entered the spawn-ready set. The backend recommends readiness; the root
orchestrator still performs the native harness spawn.

### Handoff gate

An agent cannot claim a promised handoff is ready until its declared acceptance conditions pass.

### Completion gate

Evaluate authoritative root obligations for every terminal path:

- normal final response;
- no-subagent runs;
- token-limit stop;
- timeout;
- cancellation;
- tool-call serialization failure;
- child failure followed by root fallback.

If the harness cannot revise a terminal turn, the adapter must return a non-success run state and expose a resumable continuation request. It must never silently report success.

### Recovery

Recovery must preserve the original obligation and attach:

- failure evidence;
- current recovery owner;
- bounded next action;
- retry count and changed strategy;
- same acceptance condition used for the original obligation.

## 10. Universal implementation surfaces

### Backend — required

The backend is the source of truth:

- graph and event ledger;
- state reconciler;
- artifact version/evidence store;
- ready-set scheduler/selector;
- gate decisions;
- recovery ownership.

It must be harness-neutral.

### Harness adapter — required

Each adapter maps native events into the common protocol:

```text
prompt.accepted
agent.spawned
agent.ended
tool.started
tool.ended
artifact.changed
model.ended
run.completion_attempted
```

The adapter also maps `allow`, `block`, `revise`, or `resume` decisions back into native behavior.

### Hooks — preferred enforcement seam

Use hooks to observe tools/spawns and gate handoffs/completion when supported. Hooks contain no mechanism-specific state logic; they call the backend.

### Tools — explicit declaration and inspection only

Optional tools may let agents:

- declare a promised output;
- declare a consumer;
- inspect their obligations;
- transfer ownership;
- request verification.

Agents cannot use tools to mark their own obligation verified without objective evidence.

### Skill — optional guidance fallback

A skill can teach agents how to make clean assignments and handoffs. It is not the source of truth and cannot provide enforcement.

## 11. Capability degradation

Adapters declare capabilities:

```yaml
observe_spawn: true
observe_tool_result: true
intercept_completion: false
resume_turn: true
```

If completion interception is unavailable, the system must expose `detected_unresolved` rather than claiming `enforced`. Evaluation reports must distinguish those modes.

## 12. Acceptance tests

1. A single-agent prompt requiring one file creates exactly one root obligation.
2. No planner/reviewer artifacts appear unless explicitly requested or delegated.
3. A voluntary child spawn adds only its promised outputs.
4. A child ending after acknowledgment becomes `orphaned` and triggers recovery.
5. A file modification invalidates old verification.
6. A token-limit stop with missing output cannot produce successful completion.
7. Independent parallel work is not blocked by unrelated dependencies.
8. Private reasoning never appears in another agent's projection.
9. Replaying the same events produces the same graph state.
10. The same normalized event trace behaves identically across harness adapters.
11. In `A -> B -> C`, only `A` is initially spawn-ready and each consumer is released only after its exact incoming requirement is satisfied.
12. In `A + B -> C`, `A` and `B` are concurrently spawn-ready and `C` waits for both.
13. A producer terminating without its required artifact does not release its consumer and creates a recovery decision.
14. A produced-only edge may release on current artifact production, while a verified edge remains blocked until current-version verification passes.
15. A phase with no prerequisites may start while a later phase of the same assignment remains blocked.

## 13. Boundary with the other memories

- Dependency Memory says whether work is ready and what blocks it.
- Co-Domain Memory says what two independently owned sides must mean together.
- Testing-Practice Memory says how claims should be verified and what evidence is acceptable.

Dependency Memory may reference a co-domain contract or testing obligation, but it must not duplicate their contents.
