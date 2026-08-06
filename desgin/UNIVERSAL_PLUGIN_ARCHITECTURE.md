# Universal Multi-Agent Memory Plugin Architecture

## Goal

Port the strongest behavior of the original MultiAgentBench `all_three` system into a benchmark-independent OpenClaw plugin that supports fixed workflows, arbitrary feature owners, peer collaboration, and dynamic multi-agent topologies.

The target is not only memory retrieval. It is a memory-mediated control loop:

```text
memory + observation + targeted delivery + recovery scheduling + verification gates
```

## Target system graph

```mermaid
flowchart TB
    Task["Task input<br/>requirements, repository, benchmark metadata"]
    Adapter["Universal task adapter<br/>assignments, artifacts, boundaries, verification"]
    Registry["Participant registry<br/>agent ID, assignment, capabilities, owned artifacts"]
    Orchestrator["Memory-mediated orchestration controller"]

    Task --> Adapter
    Adapter --> Registry
    Adapter --> Orchestrator
    Registry --> Orchestrator

    subgraph Memory["Structured memory plane"]
        Dep["Dependency state<br/>private projection + public readiness"]
        Contract["Interface contracts<br/>shared resolved agreements"]
        Verify["Verification ledger<br/>commands, failures, repairs, evidence"]
        Procedure["Procedural memory<br/>successful recovery strategies"]
        Episode["Episodes<br/>spawn, injection, tools, completion"]
    end

    subgraph Control["Universal control plane"]
        Observe["Deterministic observer"]
        Reconcile["State reconciler"]
        Select["Sparse relevance selector"]
        Gate["Readiness and completion gates"]
        Recover["Recovery scheduler"]
    end

    subgraph Agents["Arbitrary agent topology"]
        A["Producer or feature owner"]
        B["Peer or downstream consumer"]
        C["Reviewer, tester, or integrator"]
        N["Any benchmark-defined assignment"]
    end

    Orchestrator --> Select
    Select --> Dep
    Select --> Contract
    Select --> Verify
    Select --> Procedure

    Select -->|"targeted injection"| A
    Select -->|"targeted injection"| B
    Select -->|"targeted injection"| C
    Select -->|"targeted injection"| N

    A -->|"artifacts and tool results"| Observe
    B -->|"artifacts and tool results"| Observe
    C -->|"tests and review evidence"| Observe
    N -->|"artifacts and tool results"| Observe

    Observe --> Episode
    Observe --> Reconcile
    Reconcile --> Dep
    Reconcile --> Verify

    Dep --> Gate
    Contract --> Gate
    Verify --> Gate
    Gate -->|"ready"| Orchestrator
    Gate -->|"blocked"| Recover
    Verify -->|"failed"| Recover
    Recover --> Procedure
    Recover -->|"changed strategy and capable owner"| Orchestrator
    Recover -->|"rerun same verification"| Observe
    Gate -->|"all obligations resolved"| Complete["Verified task completion"]
```

## Required runtime loop

```mermaid
flowchart LR
    Spawn["Select and spawn"] --> Inject["Inject sparse memory"]
    Inject --> Act["Agent acts"]
    Act --> Observe["Observe objective result"]
    Observe --> Update["Reconcile memory state"]
    Update --> Ready{"Ready?"}
    Ready -->|"yes"| Handoff["Release dependency"]
    Handoff --> Spawn
    Ready -->|"no"| Blocker["Record blocker and owner"]
    Blocker --> Strategy["Choose changed strategy"]
    Strategy --> Repair["Bounded repair turn"]
    Repair --> Verify["Rerun same verification"]
    Verify --> Observe
    Ready -->|"all complete"| Done["Verified completion"]
```

## Universal relevance identity

Do not route primarily by fixed role names such as planner, implementer, or reviewer.

```text
relevance =
    project identity
  + assignment identity
  + owned or modified artifacts
  + producer/consumer participation
  + current stage
  + unresolved blocker
  + verification ownership
```

Canonical contract identity should be based on structured identity, not descriptive text:

```text
project + artifact + interface + memory kind + visibility owner
```

## Original reference implementation

- `dependency_memory/v4_sparse/run_feature_ablation.py`
- `dependency_memory/v4_sparse/sparse_memory.py`
- `dependency_memory/v4_sparse/coordination_memory.py`
- `dependency_memory/v4_sparse/interface_memory.py`
- `dependency_memory/v4_sparse/testing_practice_memory.py`
- `experiments/all_three_task1_20260803/`
- `experiments/all_three_remaining19_20260803/`
- `experiments/all_three_prework_v2_20tasks_20260803/`

Use `all_three` as the operational reliability reference and `all_three_prework_v2` as the contract-negotiation design reference.

## Architectural rule

```text
Universal memory identifies what matters.
Objective observation determines what is true.
Orchestration ensures an agent acts on it.
Verification determines when the system may proceed.
```

