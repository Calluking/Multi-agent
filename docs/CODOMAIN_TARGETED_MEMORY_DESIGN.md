# Co-Domain Targeted Memory Design

## 1. Purpose

Co-domain targeted memory reduces cross-domain integration faults by preserving the
contract at a producer/consumer boundary and injecting that contract only into the
Agent turns that need it.

The current implementation is deliberately narrower than a general shared-memory
pool. It is a bounded **Shared Interface Contract Bank**:

- the Planner extracts cross-domain boundaries from the task;
- the system stores one structured record per boundary;
- the Implementer receives the contracts as acceptance criteria;
- the Reviewer exercises the real producer-to-consumer path;
- reviewer evidence updates the runtime state of each record.

The mechanism targets semantic compatibility. It does not replace Private
Dependency Memory, which tracks whether an Agent has an unresolved blocker and
whether an artifact is ready to hand off.

## 2. Positioning

The two implemented memories answer different questions:

| Memory | Visibility | Question answered |
|---|---|---|
| Private Dependency Memory | Private to the recovering Agent | What is missing, and may this Agent hand off? |
| Co-Domain Targeted Memory | Shared but selectively injected | What must producer and consumer mean at this boundary? |

The co-domain memory is shared in storage, but not broadcast indiscriminately.
Every record identifies its producer, consumer, affected contract and verification
procedure. Retrieval is targeted by role and boundary relevance.

## 3. Current execution flow

```text
Task and workflow text
        |
        v
Planner extracts producer/consumer boundaries
        |
        v
Normalize and bound interface records
        |
        v
interface_memory.json
        |
        +--------------------------+
        |                          |
        v                          v
Implementer projection       Reviewer projection
implement both sides         test real crossing
and boundary tests           and record evidence
        |                          |
        +------------+-------------+
                     v
            interface_audit.json
                     |
                     v
       runtime.state = verified | failed
```

The original prototype stopped after contract generation and validation. The
current implementation adds `coordination_memory.json` and an append-only
`coordination_memory_events.jsonl`, allowing Agents to submit typed proposal,
challenge, revision, acceptance and verification events while preserving a
compact resolved projection.

The Agent writes `coordination_contributions.json`; the runner validates and
consumes it after the turn. A stale revision whose `base_version` does not match
the current resolved version is rejected.

## 4. Record schema

The persistent bank is `interface_memory.json` and has `memory_type` set to
`shared_interface`.

```yaml
schema_version: "0.1"
task_id: 1
run_id: example-run
memory_type: shared_interface

interfaces:
  - interface_id: reg_to_workshop_auth
    producer: Registration and Profile module
    consumer: Cultural Workshop module
    purpose: Require a registered identity before workshop creation
    task_evidence: Registration must precede integrated features
    risk: 5

    fields:
      - name: user_id
        type: int
        meaning: Registered identity of the workshop producer

    producer_obligations:
      - Assign and retain a unique user_id
      - Expose a lookup that rejects unknown identities

    consumer_obligations:
      - Validate user_id before allocating a workshop
      - Leave storage and counters unchanged on rejection

    invariants:
      - No workshop exists for an unknown producer
      - Rejected creation is atomic

    boundary_test:
      setup: Create one registered user and one unknown identity
      action: Attempt workshop creation with both identities
      expected: Unknown identity is rejected without side effects

    runtime:
      state: agreed
      evidence: []
      blocker: null
```

The current bounds are intentional:

- at most 5 interface records;
- at most 8 fields per interface;
- at most 6 obligations or invariants in each list;
- long values are truncated during normalization;
- malformed memory fails open to an empty bank.

These limits keep the injected context sparse and prevent interface memory from
becoming a duplicate of the task prompt or chat history.

## 5. Generation

### 5.1 Planner extraction

The Planner identifies boundaries that satisfy all of the following:

1. One component, domain or role produces data or behavior.
2. Another component, domain or role consumes it.
3. Integration can fail even when each side is locally reasonable.
4. The crossing can be expressed as fields, obligations, invariants and a test.

Typical examples include:

- frontend to backend requests and responses;
- authentication identity passed into a protected feature;
- an external-data adapter passed into application logic;
- model or NLP output consumed by a web/mobile feature;
- producer events consumed by real-time subscribers;
- shared multi-party state used by non-owner participants.

### 5.2 Pattern retrieval

Before or alongside task-specific extraction, the implementation can retrieve
compact public patterns from task wording. Current patterns cover:

- browser/backend integration;
- real-time events;
- external data;
- interactive media;
- ML/NLP application paths;
- authorization;
- multi-party state propagation.

Pattern memory supplies a reusable rule and a verification example. The Planner
still has to instantiate it into a task-specific producer/consumer contract.

### 5.3 Normalization

`normalize_bank` validates the Planner output, assigns unique interface IDs,
bounds record size, sorts by risk, and initializes every runtime state to
`agreed`. Invalid or incomplete records are discarded rather than injected.

## 6. Targeted retrieval and injection

The bank is public at the task level, but detailed records are injected sparsely.

### Implementer view

The Implementer receives the highest-risk relevant contracts with the instruction
to implement both sides against the exact semantics and add executable boundary
tests.

The projection contains:

- producer and consumer;
- task evidence and purpose;
- shared fields;
- producer obligations;
- consumer obligations;
- invariants;
- the boundary test.

### Reviewer view

The Reviewer receives the same contract plus a stronger instruction:

- exercise the real producer-to-consumer path;
- repair mismatches rather than accepting disconnected simulations;
- write exact pass/fail evidence to `interface_audit.json`.

### Coverage inventory

When the full bank is larger than the detailed injection limit, all required
boundaries remain visible through a short coverage inventory while only the
highest-risk contracts are expanded.

### Future generalized targeting

For multi-Agent systems without fixed Planner/Implementer/Reviewer roles,
selection should use record metadata rather than role names:

```text
current Agent assignment
+ owned or modified artifacts
+ producer/consumer participation
+ task stage
+ interface risk
+ unresolved or failed runtime state
```

The storage remains shared; proactive delivery remains selective.

## 7. Verification and update

The Reviewer writes `interface_audit.json`, keyed by `interface_id`. The system
then attaches the result to each persistent record:

```yaml
runtime:
  state: verified
  evidence:
    - Unknown user raised ValueError
    - Storage remained unchanged
    - ID counter remained unchanged
  blocker: null
```

or:

```yaml
runtime:
  state: failed
  evidence:
    - Consumer accepted an unknown identity
  blocker: Registration guard is not called before allocation
```

Runtime evidence is not a new contract. It reports whether the implementation
satisfies the existing contract. Contract semantics and runtime status must remain
separate.

## 8. What is shared and what is not

Promote information into co-domain memory when another Agent needs it to build,
review or continue the crossing correctly.

Store:

- resolved interface semantics;
- producer and consumer obligations;
- shared fields and error behavior;
- cross-component invariants;
- executable boundary tests;
- verification evidence and blockers.

Do not store:

- generic task summaries;
- private chain-of-thought or tentative reasoning;
- every chat message;
- local implementation details with no consumer;
- superseded drafts in the active projection;
- private recovery steps already covered by Dependency Memory.

## 9. Current limitations

1. The Planner or Integration Agent still authors the initial task-specific
   contract.
2. The event model supports multi-Agent negotiation, but the benchmark has only
   Planner/Implementer/Reviewer-style roles rather than one Agent per domain.
3. Targeting is still partly organized around benchmark role names; artifact and
   participant-based selection is the next generalization.
4. A revision addresses all currently open challenges on a record; challenge-by-
   challenge resolution can be made more precise later.
5. The runner rejects stale versions but does not yet implement a distributed lock
   or merge algorithm for simultaneous writes.
6. Full history is persisted, but retention is bounded to 50 events per record.

## 10. Evolution toward a Shared Coordination Memory Pool

The current bank is now represented as one record type inside a Shared
Coordination Memory Pool:

```text
Shared Coordination Memory Pool
  |- interface_contract
  |- shared_invariant
  |- decision
  |- challenge
  |- verification_evidence
  `- domain_fact
```

Implemented foundations include:

- append-only contributions with author and timestamp;
- proposal, challenge, revision and acceptance events;
- explicit record versions;
- record ownership and affected Agents/artifacts;
- a resolved projection separate from full history;
- optimistic version checks for revisions;
- targeted retrieval of current state and relevant open issues.

Future extensions should add richer artifact routing, per-challenge resolution,
and a merge policy for genuinely concurrent writers.

The default Agent view should contain the latest resolved specification, relevant
open challenges and recent verification evidence—not the entire contribution
history.

## 11. Implementation references

- `dependency_memory/v4_sparse/interface_memory.py`
  - pattern retrieval;
  - bank normalization;
  - compact role projections;
  - coverage inventory;
  - reviewer audit summarization.
- `dependency_memory/v4_sparse/coordination_memory.py`
  - versioned shared pool;
  - typed Agent contributions;
  - challenge and revision lifecycle;
  - targeted resolved projections;
  - audit-to-verification event conversion.
- `dependency_memory/v4_sparse/run_interface_panel.py`
  - experimental execution and injection hooks.
- `dependency_memory/v4_sparse/run_feature_ablation.py`
  - baseline/dependency/co-domain/both feature switches.
- `dependency_memory/v4_sparse/test_interface_memory.py`
  - schema, bounding, rendering and update tests.
- `docs/INTERFACE_MEMORY_ITERATION_REPORT.md`
  - X1-X8 iteration history and observed behavior.
- `docs/TASK1_FEATURE_ABLATION_20260731.md`
  - four-condition Task 1 comparison.

## 12. Design principle

> Keep the contract public and durable; keep retrieval sparse and relevant; keep
> runtime evidence attached to the contract; do not turn shared memory into a copy
> of the conversation.
