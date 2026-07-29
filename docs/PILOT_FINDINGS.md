# Task 19 Private Dependency-Memory Pilot

## Outcome

The prototype successfully replayed the reviewer boundary of Task 19 after the known failed implementer handoff.

| Measure | Original baseline | Memory pilot |
|---|---:|---:|
| `solution.py` | Present and runnable | Present and runnable |
| `test_solution.py` | Present; 50 tests passed | Present; 35 tests passed |
| `review.md` | Present | Present |
| `implementation.md` | **Missing** | **Present** |
| Workflow dependency completion | Failed | Passed |
| Bare `python3 solution.py` | Exit 0 | Exit 0 |

The pilot's first reviewer pass produced all four artifacts. Consequently, the finalization selector correctly returned no unresolved dependencies and the second reviewer call only confirmed completion.

## Experimental boundary

This was an isolated reviewer-boundary replay, not a new full benchmark run.

The workspace began with:

- `TASK.md`;
- `AGENTS.md`;
- the original `plan.md`;
- explicit replay context saying the implementer handoff failed;
- no copied implementation, tests, implementation report, or review report.

The original baseline is the no-memory comparison. The pilot additionally divided review into two calls, so memory and extra-turn effects are not yet experimentally separated. The first pass completed the dependency contract before the extra turn, which is encouraging but not causal proof.

## What was generated

The memory compiler created three complete YAML records:

1. `executable_implementation` for `solution.py`;
2. `implementation_report` for `implementation.md`;
3. `review_report` for `review.md`.

Each record stored:

- identity and version;
- task/run/workflow scope;
- privacy and recipient policy;
- producer and consumer roles;
- prerequisite relationships;
- acceptance and verification contracts;
- mutable artifact and verification state;
- ownership and recovery action;
- retrieval text, keywords, entities, stage, and priority;
- lifecycle and provenance.

The complete store was 17,646 bytes after the run. The startup projection injected into the agent was 1,377 bytes. This supports the design decision to store complete YAML while injecting only an actionable projection.

## Extraction behavior

At reviewer startup, deterministic filesystem observation produced:

```yaml
solution.py: missing
implementation.md: missing
review.md: missing
```

After the first reviewer pass, the system:

1. observed created artifacts;
2. ran `python3 solution.py` independently;
3. stored exit code, output, error output, and timestamp;
4. updated `solution.py` to `verified`;
5. reconciled report prerequisites and acceptance criteria;
6. selected unresolved dependencies for finalization.

The final selection was empty because all contracts were satisfied.

## Evidence that the checkpoint reached the agent

The first reviewer response explicitly organized its result around the selected dependencies:

- `solution.py` built and verified;
- `test_solution.py` created and passing;
- `implementation.md` recording exact verification;
- `review.md` recording audit and results.

The first pass used 14 tool calls and completed the missing report that was omitted in the original baseline.

## Design problems exposed by the pilot

### 1. Dependency ordering must affect selection

The initial selector ranked `implementation_report` and `review_report` above `executable_implementation`. All were critical blockers, but the executable is their prerequisite.

Adjustment:

- add dependency-depth awareness to ranking;
- prefer currently actionable root prerequisites;
- retain all critical blockers, but present them in dependency order.

### 2. File existence is insufficient acceptance evidence

The first implementation treated the existence of a report as completion. A blank or inaccurate report would have passed.

Adjustment:

- support deterministic `content_contains_all` and `content_contains_any` criteria;
- verify that `implementation.md` contains the required command and an observed result;
- verify that `review.md` contains final verification evidence;
- later add semantic validation for requirements not expressible as deterministic predicates.

### 3. Artifact versions must invalidate verification

If a verified artifact is edited, an old successful command result must no longer establish readiness.

Adjustment:

- hash each file version;
- change verification to `stale` when the content hash changes;
- require verification against the current artifact version.

### 4. Prerequisites must affect readiness

A report can physically exist before its implementation has been verified. It should be `present_prerequisites_unresolved`, not ready.

Adjustment:

- evaluate prerequisite records during reconciliation;
- keep the dependent node blocking until its required upstream state is met.

### 5. Hybrid retrieval has two distinct jobs

Current-run critical state should be selected through exact scope and status constraints. Semantic retrieval is appropriate for ranking details and retrieving cross-task recovery strategies.

The current prototype implements:

- exact task/run/recipient/stage/status filtering;
- exact action matching;
- lexical matching over semantic text, entities, errors, and next actions;
- priority, recency, and dependency-depth reranking.

It does **not** yet use embeddings or Mem0. The `mem0` Python package was not installed in the WSL environment. The schema deliberately exposes `semantic_text`, `keywords`, and `entities` so an embedding-backed adapter can be added without changing dependency state representation.

## Revised lifecycle

```text
task/plan
   |
   v
compile complete dependency contracts
   |
   v
observe exact runtime and artifact events
   |
   v
update versioned dependency state
   |
   v
hard-filter current unresolved obligations
   |
   v
rank by action, dependency order, lexical/semantic relevance
   |
   v
inject compact recipient-private projection
   |
   v
agent acts
   |
   v
verify current artifact version and reconcile state
```

## What this pilot supports

The pilot supports these limited claims:

1. A complete generic YAML dependency schema can be compiled and maintained during a real agent workflow.
2. Deterministic state extraction can identify missing artifacts and later verify their current state.
3. A compact private projection can be injected without sending the full store.
4. In this replay, the reviewer completed the exact artifact omitted by the baseline.
5. The agent's response explicitly reflected the dependency checkpoint.

It does not yet prove that memory caused the improvement. Model sampling, explicit replay context, and the availability of another turn remain confounds.

## Next controlled experiment

Run repeated Task 19 reviewer-boundary trials with identical two-call orchestration:

| Condition | First call | Second call |
|---|---|---|
| Control | Normal recovery prompt | Generic “check and finish” prompt |
| Memory | Same recovery prompt plus selected checkpoint | Selected unresolved dependency projection |

Use multiple seeds or repetitions and compare:

- probability that `implementation.md` is produced in the first pass;
- probability that all dependency contracts are satisfied after two passes;
- redundant discovery calls;
- tokens before first persistent artifact;
- runtime and token overhead;
- false or irrelevant memory injections;
- artifact correctness, not only existence.

Only after this control should the experiment add a hard completion gate. That separates the effect of remembered information from the effect of enforced orchestration.

