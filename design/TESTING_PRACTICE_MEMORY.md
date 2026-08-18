# Testing-Practice Memory — Universal Architecture Specification

## 1. Purpose

Testing-Practice Memory retrieves proven verification practices appropriate to the current obligation, risk, artifact, and agent assignment.

It answers:

> What kind of check is appropriate here, what evidence is required, what shortcuts are invalid, and what should happen after failure?

It is procedural memory, not a fixed test plan and not a claim that testing occurred.

## 2. Non-negotiable invariants

1. The starting request defines required verification; memory cannot weaken or replace it.
2. A practice is guidance until instantiated into a run-specific verification obligation.
3. “Tests passed” is not evidence without command, result, and relevant artifact version.
4. Tests written only to satisfy the current implementation are not independent evidence.
5. A changed artifact makes earlier verification stale.
6. Testing guidance is selected by task risk and action, not fixed role names.
7. The system does not invent irrelevant commands or frameworks.
8. Verification must evaluate observable behavior, not agent confidence.
9. Failed checks preserve exact evidence and drive a bounded repair-and-rerun loop.
10. Memory must remain sparse; excessive testing context can prevent implementation.

## 3. Two-layer model

### 3.1 Semantic practice bank

Cross-run reusable knowledge:

```yaml
practice_id: boundary-negative-atomicity
title: Reject invalid cross-boundary input atomically
applicability:
  boundary_types: [api, shared_state, identity]
  risks: [invalid_input, partial_mutation]
rule: Exercise one valid crossing and one invalid crossing; assert no state changes after rejection.
required_evidence:
  - exact command
  - exit status
  - assertions on pre/post state
invalid_substitutes:
  - file existence
  - producer-only unit test
  - agent statement of success
failure_action: repair the boundary, then rerun the same assertions
confidence: 0.9
provenance:
  successful_runs: []
```

### 3.2 Run-specific verification obligation

Concrete test required for current work:

```yaml
verification_id: run-42:user-response-boundary
run_id: run-42
source:
  type: accepted_contract
  ref: run-42:api-client:user-response@v2
subject:
  artifacts: [server/users.py, web/user-client.ts]
  artifact_versions: {}
owner_id: integration-agent
practice_refs: [boundary-negative-atomicity]
command: python tests/test_user_boundary.py
required_assertions:
  - valid response preserves user_id
  - duplicate registration leaves storage unchanged
state: pending
evidence: []
```

Practices are durable advice. Verification obligations are current-run state. They must not be conflated.

## 4. Practice lifecycle

```text
candidate -> validated -> active -> deprecated
```

A candidate practice becomes validated only after evidence shows it helped detect or prevent a real failure without excessive cost. Practices record provenance, confidence, applicability, and known counterexamples.

## 5. Verification lifecycle

```text
pending -> running -> passed
                  -> failed -> repair_pending -> running
passed -> stale   (when a covered artifact changes)
pending -> waived (only by explicit task authority with reason)
```

No agent may directly set `passed`. The observer derives it from objective execution evidence.

## 6. Obligation creation

Create run-specific verification obligations from:

1. explicit commands or acceptance criteria in the starting request;
2. acceptance criteria declared in an actual child assignment;
3. accepted co-domain boundary tests;
4. observed failure that requires regression coverage;
5. an agent explicitly adopting a retrieved practice for its work.

Do not automatically require every retrieved practice. Retrieval proposes guidance; obligation creation requires task relevance and an owner or authoritative acceptance condition.

## 7. Retrieval

Hard filters:

```text
compatible artifact/task type
+ compatible action/stage
+ compatible risk/failure mode
+ applicable verification surface
```

Ranking signals:

```text
exact risk/failure match
+ semantic task similarity
+ lexical identifier match
+ successful provenance
+ confidence
+ low execution/context cost
```

Selection should usually return one or two practices.

Examples:

- before implementing a parser: malformed-input and round-trip practices;
- after an import failure: clean-environment import/startup practice;
- at a shared API boundary: real-path contract and negative-case practice;
- after a race failure: deterministic concurrency and state-invariant practice;
- before final completion: explicit requested command plus stale-evidence scan.

## 8. Targeted delivery

Delivery is based on current responsibility rather than role labels.

### Builder projection

- relevant practice rule;
- required observable behavior;
- invalid testing shortcuts;
- smallest useful check after the next implementation slice.

### Boundary owner projection

- real producer-to-consumer test;
- negative/error path;
- invariant and atomicity assertions.

### Verifier projection

- original acceptance criteria;
- exact artifact versions;
- independence requirements;
- existing failures and required rerun.

Example:

```text
VERIFICATION PRACTICE
- Risk: stale verification after repair
- Required evidence: rerun the original command against the current artifact hash
- Invalid substitute: citing an earlier passing result
```

## 9. Observation and evidence

Normalized evidence record:

```yaml
evidence_id: event:tool-991
verification_id: run-42:user-response-boundary
command: python tests/test_user_boundary.py
cwd: /workspace
exit_code: 0
started_at: ...
ended_at: ...
artifact_versions:
  server/users.py: sha256:...
  web/user-client.ts: sha256:...
assertion_summary:
  passed: 8
  failed: 0
stdout_ref: blob:...
stderr_ref: blob:...
```

Evidence validity checks:

- command actually executed;
- exit status is available;
- command covers the declared subject;
- required artifacts existed at recorded versions;
- output is not fabricated prompt text;
- required assertions were observed;
- no covered artifact changed afterward.

## 10. Repair-and-rerun loop

```text
failed evidence
  -> identify exact failed obligation
  -> assign recovery owner
  -> retrieve one relevant recovery/testing practice
  -> make bounded repair
  -> rerun the same verification
  -> pass or preserve new failure evidence
```

Changing the command to avoid the failing behavior does not satisfy the original obligation unless authoritative acceptance criteria also change.

Retries are bounded and must record a materially changed strategy.

## 11. Control rules

Testing-Practice Memory itself does not force agent spawning.

Hard gates apply only to instantiated verification obligations that are authoritative for the transition:

- a child promised a test as part of its assignment;
- an accepted handoff requires a specific check;
- a co-domain contract requires a boundary test;
- the starting request explicitly requires verification;
- a previous failure remains unresolved.

A generic retrieved practice remains advisory until adopted or required by one of these sources.

Completion is blocked when a required verification is pending, failed, or stale. A model token-limit stop does not waive verification.

## 12. Universal implementation surfaces

### Backend — required

- semantic practice bank;
- run-specific verification ledger;
- artifact-version index;
- evidence validator;
- retrieval/ranking;
- stale-evidence reconciler;
- repair episode/provenance store.

### Harness adapter — required

Normalize:

- task acceptance criteria;
- actual assignment promises;
- tool/command starts and results;
- artifact changes;
- test output and exit status;
- model/run termination;
- completion attempts.

### Hooks — observation and enforcement

Use hooks around tool execution, artifact changes, handoff, and completion when available. Hooks forward events to the backend and apply returned decisions.

### Tools — explicit verification surface

Optional tools:

- `practice.search`
- `verification.declare`
- `verification.inspect`
- `verification.run`
- `verification.attach_evidence`
- `verification.waive` (authority restricted)

Agents can request verification or attach a command result, but the backend validates evidence independently.

### Skill — practice application guidance

A skill helps agents select meaningful tests and avoid invalid substitutes. It cannot mark a verification passed or block completion.

## 13. Learning across runs

After a run, record a compact episode:

```yaml
practice_refs: [...]
task_shape: ...
failure_mode: ...
injection_point: ...
verification_result: ...
detected_fault: true
repair_succeeded: true
token_cost: ...
false_positive: false
```

Promote or raise confidence only when repeated evidence supports effectiveness. Record counterexamples and cost. Do not learn from agent self-reports alone.

## 14. Capability degradation

If command results cannot be observed, the adapter may provide guidance but must report verification as `unobserved`.

If completion cannot be intercepted, unresolved required tests are reported as `detected_not_enforced`.

Evaluation must distinguish:

- practice retrieved;
- practice injected;
- verification declared;
- command observed;
- evidence validated;
- gate enforced.

## 15. Acceptance tests

1. Retrieval returns no irrelevant practice for an unmatched task.
2. A retrieved practice does not automatically create a required test.
3. An explicit task command creates a required verification obligation.
4. A passing command records exact artifact versions.
5. Editing a covered artifact makes evidence stale.
6. An agent's success statement cannot set `passed`.
7. A disconnected mock cannot verify a co-domain boundary.
8. Failed verification preserves evidence and requires the same acceptance condition after repair.
9. Token-limit termination cannot bypass pending required verification.
10. The same normalized evidence produces the same state across harness adapters.

## 16. Boundary with the other memories

- Dependency Memory determines when a required verification blocks a handoff or completion.
- Co-Domain Memory defines boundary semantics and the required real-path test.
- Testing-Practice Memory supplies reusable verification procedures and validates evidence quality.
