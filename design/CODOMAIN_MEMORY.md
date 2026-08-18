# Co-Domain Memory — Universal Architecture Specification

## 1. Purpose

Co-Domain Memory preserves agreements at boundaries where independently owned components, agents, domains, or services must interoperate.

It answers:

> What does the producer promise, what does the consumer assume, what invariant must hold across the boundary, and what evidence proves the integrated path?

It is a shared contract system with targeted delivery. It is not a generic task summary, a fixed library of domain templates, or a substitute for dependency readiness.

## 2. Non-negotiable invariants

1. A co-domain record requires a real producer and consumer.
2. Both sides must be grounded in the starting request, actual assignments, artifacts, code, or observed runtime events.
3. Keyword matches cannot instantiate domain-specific semantics.
4. Reusable patterns may suggest a contract shape, but task-specific fields and obligations require evidence.
5. Contracts are versioned; stale revisions cannot overwrite newer agreements.
6. Contract meaning and runtime verification state are separate.
7. Shared storage does not imply broadcast delivery.
8. Local implementation detail is excluded unless another owner depends on it.
9. Verification must exercise the real crossing, not two disconnected mocks.
10. No contract is created merely because several modules appear in one task.

## 3. When a co-domain contract exists

A boundary qualifies only when all conditions hold:

1. A producer emits data, behavior, state, or an interface.
2. A distinct consumer relies on it.
3. The two sides have independent ownership or independent change risk.
4. Each side can appear locally correct while integration is wrong.
5. The crossing has testable semantics.

Examples:

- frontend request to backend endpoint;
- authentication identity consumed by an authorization decision;
- event producer consumed by a subscriber;
- schema emitted by one agent and imported by another;
- model output consumed by an application feature;
- shared file/API modified by two independently delegated agents.

Non-examples:

- two sequential steps owned by the same agent;
- a generic “registration” and “review” keyword occurring in one prompt;
- a local helper used only inside one component;
- a guessed interface with no producer/consumer evidence.

## 4. Contract model

```yaml
contract_id: run-42:api-client:user-response
run_id: run-42
interface_id: user-response
source_evidence:
  - assignment:backend-agent
  - assignment:frontend-agent
  - artifact:openapi.yaml
producer:
  owner_id: backend-agent
  artifacts: [server/users.py, openapi.yaml]
consumer:
  owner_id: frontend-agent
  artifacts: [web/user-client.ts]
shared_semantics:
  fields:
    - name: user_id
      type: string
      meaning: stable registered-user identity
  producer_obligations:
    - return user_id after successful creation
  consumer_obligations:
    - treat a missing user_id as protocol failure
  invariants:
    - the same user_id identifies the entity on both sides
  error_semantics:
    - duplicate registration returns conflict without creating state
boundary_verification:
  command: python tests/test_user_boundary.py
  expected: exit 0
version: 1
agreement_state: proposed
verification_state: unverified
```

Contract identity is structural:

```text
run + producer identity + consumer identity + interface/artifact identity
```

It must never be based only on generated prose.

## 5. Lifecycle

Agreement lifecycle:

```text
candidate -> proposed -> challenged -> revised -> accepted -> superseded
```

Verification lifecycle:

```text
unverified -> verified
           -> failed -> repaired -> verified
           -> stale
```

An accepted contract can remain unverified. A passing test does not implicitly change contract semantics. Changing fields or invariants creates a new version and makes older verification stale.

## 6. Discovery

### 6.1 Explicit discovery

Preferred sources:

- the starting request explicitly names a producer/consumer boundary;
- two actual child assignments declare a handoff;
- an assignment declares a shared artifact or interface;
- an agent explicitly proposes a contract through a tool;
- repository evidence shows one owned component importing/calling another.

### 6.2 Observed discovery

The backend may propose a candidate when it observes:

- cross-owner import or function call;
- shared schema or generated artifact;
- endpoint/client pairing;
- event publication/subscription;
- integration failure naming both sides;
- concurrent edits to a declared shared API.

Candidates must cite exact evidence. No candidate becomes accepted automatically.

### 6.3 Pattern assistance

Reusable patterns describe shapes such as request/response, event/subscriber, identity/authorization, or shared state. A pattern can help ask the right questions, but it cannot supply task-specific nouns, fields, invariants, or tests.

This rule prevents domain contamination such as injecting cultural-tour contracts into an unrelated budgeting or game task.

## 7. Negotiation

Agents may contribute typed events:

```yaml
event_type: propose | challenge | revise | accept | verify | fail
contract_id: run-42:api-client:user-response
base_version: 1
author_id: frontend-agent
changes: {}
evidence_refs: []
timestamp: ...
```

Rules:

- revisions require the current `base_version`;
- challenges identify a precise field, obligation, invariant, or test;
- acceptance is participant-specific;
- the resolved projection contains the latest accepted version plus open challenges;
- full history remains append-only and bounded by retention policy.

## 8. Targeted projection

Records are selected by:

```text
current run
+ current assignment
+ producer/consumer participation
+ owned or modified artifacts
+ interface identity
+ open challenge or failed verification
+ risk
```

### Producer view

- fields and output semantics;
- producer obligations;
- consumer assumptions;
- relevant open challenges;
- boundary test acceptance criteria.

### Consumer view

- fields and input semantics;
- consumer obligations;
- producer guarantees;
- error behavior;
- boundary test acceptance criteria.

### Integrator/reviewer view

- both sides;
- invariants;
- current version and acceptance state;
- exact real-path verification;
- existing failure evidence.

Normally inject at most one or two relevant contracts. Provide a compact inventory when more exist.

## 9. Verification

Valid verification must:

1. use artifacts from both actual owners;
2. exercise the real producer-to-consumer path;
3. assert shared fields and invariants;
4. check declared error behavior;
5. cite command, exit status, artifact versions, and observed result.

Invalid substitutes include:

- testing only the producer;
- testing only the consumer with a handwritten fake;
- checking that files exist;
- accepting matching names without matching semantics;
- an agent declaring “integrated successfully” without executable evidence.

## 10. Control rules

Co-Domain Memory does not force agent spawning.

It may gate only real boundary transitions:

- consumer handoff when the required contract remains challenged;
- integration completion when an accepted high-risk contract is unverified;
- final completion when the starting request explicitly requires integrated behavior and real-path verification failed.

It must not block unrelated local work.

If a contract was merely inferred and never accepted, the system reports risk but does not silently promote it to a hard blocker.

## 11. Universal implementation surfaces

### Backend — required

- append-only contract event ledger;
- versioned resolved projection;
- evidence index;
- participant/artifact index;
- conflict and stale-write detection;
- targeted selector;
- verification-state reconciler.

### Harness adapter — required

Normalize:

- starting request;
- actual spawn assignments;
- child identity and ownership;
- artifact/tool events;
- messages containing explicit contract proposals;
- integration test results;
- completion attempts.

### Hooks — observation and gates

Use hooks for spawn capture, tool results, artifact changes, and pre-handoff/pre-completion checks when supported.

### Tools — primary explicit collaboration surface

Optional tools:

- `contract.propose`
- `contract.challenge`
- `contract.revise`
- `contract.accept`
- `contract.inspect`
- `contract.verify`

Verification tools accept evidence but independently validate command/artifact facts through the observer.

### Skill — negotiation guidance

A skill teaches agents how to express fields, obligations, invariants, and boundary tests. It cannot instantiate or accept contracts on its own.

## 12. Capability degradation

If a harness cannot intercept completion, the adapter records unresolved contract risk and returns `detected`, not `enforced`.

If a harness cannot observe child ownership, explicit contract tools can supply participants. If neither native observation nor explicit declaration exists, co-domain enforcement is unavailable and must be reported as such.

## 13. Acceptance tests

1. No contract is produced from keywords alone.
2. Two actual assignments with a declared handoff produce one candidate contract.
3. A pattern never inserts task-specific semantics absent from evidence.
4. Producer and consumer receive different sparse projections of the same contract.
5. A stale revision is rejected.
6. Changing the contract invalidates older verification.
7. Disconnected unit tests cannot verify a boundary.
8. A real-path passing test verifies the exact contract version.
9. Unrelated agents receive no contract content.
10. Replaying normalized events yields the same resolved contract state.

## 14. Boundary with the other memories

- Dependency Memory tracks whether a contract artifact or verification prerequisite is ready.
- Co-Domain Memory owns the shared meaning and negotiation history.
- Testing-Practice Memory supplies reusable guidance about how to test the boundary and reject invalid evidence.
