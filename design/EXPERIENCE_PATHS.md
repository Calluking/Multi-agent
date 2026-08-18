# Prior Experience and Evidence Map

## 1. Purpose

This document maps the work that preceded the V2 redesign. It exists so a new implementation can recover useful mechanisms and experimental evidence without accidentally inheriting the failed universal-plugin architecture.

Paths are divided into:

- **tracked references** available in this clean redesign worktree;
- **local experimental evidence** retained in the original WSL workspace;
- **failed implementation evidence** that should be studied but not used as the new foundation.

The V2 specifications remain authoritative:

- `design/v2/DEPENDENCY_MEMORY.md`
- `design/v2/CODOMAIN_MEMORY.md`
- `design/v2/TESTING_PRACTICE_MEMORY.md`

## 2. Recommended reading order

1. Read the three V2 mechanism specifications.
2. Read the Task 19 dependency pilot and its limitations.
3. Read the original sparse `all_three` implementation as behavioral evidence.
4. Read the co-domain and testing ablations separately.
5. Inspect the OpenClaw plugin failure and the 20-task logs last.
6. Reuse schemas, observers, and evidence rules selectively; do not port the old control flow wholesale.

## 3. Initial dependency-memory pilot

### Findings

Tracked path:

```text
/home/luzh/Multi-agent-universal-redesign/docs/PILOT_FINDINGS.md
```

This is the isolated Task 19 reviewer-boundary replay. It demonstrated:

- deterministic missing-artifact observation;
- complete dependency records stored separately from compact projections;
- dependency-order-aware selection;
- current-version verification;
- production of the previously omitted `implementation.md` artifact.

Important limitation: it was a boundary replay with explicit recovery context and an additional turn, not a full matched benchmark result.

### Prototype components

Tracked paths:

```text
/home/luzh/Multi-agent-universal-redesign/dependency_memory/dependency_memory.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/contract_extractor.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/compile_contracts_file.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/extract_contracts.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/run_memory_batch.py
```

Use these for:

- schema ideas;
- deterministic observation;
- contract/state separation;
- compact projection logic.

Do not inherit fixed benchmark roles or precompiled artifact names.

### Dependency design and evaluation history

Tracked paths:

```text
/home/luzh/Multi-agent-universal-redesign/docs/private_dependency_memory.md
/home/luzh/Multi-agent-universal-redesign/docs/M3_DEVELOPMENT_RESULTS.md
/home/luzh/Multi-agent-universal-redesign/docs/M3_HOLDOUT_RESULTS.md
```

The M3 holdout is especially important. It improved workflow completion and runnable rate but did not improve held-out task score. It is evidence that artifact recovery and task quality must be measured separately.

## 4. Original ideal `all_three` system

### Core implementation

Tracked paths:

```text
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/sparse_memory.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/coordination_memory.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/interface_memory.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/testing_practice_memory.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/run_feature_ablation.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/evaluate_v4.py
```

This is the strongest reference for the intended combined behavior:

```text
memory + observation + sparse delivery + recovery scheduling + verification
```

Use it to understand mechanism behavior, not as a universal harness adapter. It was designed around a known benchmark workflow.

### Tests

Tracked paths:

```text
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/test_sparse_memory.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/test_coordination_memory.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/test_interface_memory.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/test_testing_practice_memory.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/test_feature_ablation.py
```

These tests contain useful invariants for storage, retrieval, versioning, and feature toggles.

### Raw local experiments

Local-only paths in the original workspace:

```text
/home/luzh/Multi-agent/experiments/all_three_task1_20260803/
/home/luzh/Multi-agent/experiments/all_three_remaining19_20260803/
/home/luzh/Multi-agent/experiments/all_three_prework_v2_20tasks_20260803/
```

These directories are not part of the clean Git worktree. They contain original run evidence and should remain read-only reference material.

Interpretation:

- `all_three_task1_20260803`: first combined-mechanism task evidence;
- `all_three_remaining19_20260803`: continuation across the remaining tasks;
- `all_three_prework_v2_20tasks_20260803`: richer contract-negotiation/prework design.

## 5. Co-domain memory experience

### Design

Tracked paths:

```text
/home/luzh/Multi-agent-universal-redesign/docs/CODOMAIN_TARGETED_MEMORY_DESIGN.md
/home/luzh/Multi-agent-universal-redesign/docs/INTERFACE_MEMORY_ITERATION_REPORT.md
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/interface_memory.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/coordination_memory.py
```

Useful ideas:

- producer/consumer contract schema;
- bounded records;
- role-specific projections;
- versioned proposal/challenge/revision/acceptance events;
- resolved projection separated from history;
- real-path boundary verification.

### Evaluation

Tracked paths:

```text
/home/luzh/Multi-agent-universal-redesign/docs/CODOMAIN_COORDINATION_20TASK_RESULTS_20260731.md
/home/luzh/Multi-agent-universal-redesign/docs/INTERFACE_X1_FIVE_TASK_RESULTS.md
/home/luzh/Multi-agent-universal-redesign/experiments/feature_ablation_task1_coordination_20260731/
/home/luzh/Multi-agent-universal-redesign/experiments/feature_ablation_task1_coordination_fix_20260731/
```

Do not reuse the later plugin's keyword-triggered hard-coded cultural contracts. V2 requires concrete producer/consumer evidence and task-specific semantics.

## 6. Testing-practice memory experience

### Implementation and bank

Tracked paths:

```text
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/testing_practice_memory.py
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/testing_practices.json
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/run_testing_occurrence_reaudit.sh
/home/luzh/Multi-agent-universal-redesign/dependency_memory/v4_sparse/run_full_reaudit_pipeline.sh
```

The original module was intentionally inject-only. That separation is useful: practice retrieval must remain distinct from run-specific verification state and hard gating.

### Evaluation

Tracked paths:

```text
/home/luzh/Multi-agent-universal-redesign/docs/TESTING_PRACTICE_MEMORY_TASK11_20260731.md
/home/luzh/Multi-agent-universal-redesign/docs/TESTING_PRACTICE_MEMORY_5TASK_RESULTS_20260803.md
/home/luzh/Multi-agent-universal-redesign/docs/TESTING_PRACTICE_MEMORY_20TASK_RESULTS_20260803.md
```

Use these to distinguish:

- practice retrieved;
- practice injected;
- command actually executed;
- evidence validated;
- behavior or score changed.

## 7. Universal prompt-only scenarios

Tracked path:

```text
/home/luzh/Multi-agent-universal-redesign/design/universal_prompt_only_5.md
```

This five-scenario set is useful for adapter-independent validation:

- sequential handoff;
- parallel producers;
- diamond dependency;
- shared-root ownership;
- contract repair and negative testing.

The old scenarios contain explicit roles and handoffs, so they test dynamic observation after real assignments. They must not become initialization templates for unrelated prompts.

## 8. Failed universal OpenClaw plugin implementation

### Source under diagnosis

Tracked paths:

```text
/home/luzh/Multi-agent-universal-redesign/openclaw_plugin/src/index.ts
/home/luzh/Multi-agent-universal-redesign/openclaw_plugin/src/memory-engine.ts
/home/luzh/Multi-agent-universal-redesign/openclaw_plugin/seed/
/home/luzh/Multi-agent-universal-redesign/openclaw_plugin/test/
```

Study this implementation for adapter mechanics and failure evidence only.

Known architectural failures:

1. It initialized a fixed planner/implementer/reviewer artifact graph rather than deriving obligations from the starting request.
2. It injected instructions that encouraged a workflow instead of merely observing native spawning.
3. Root enforcement depended on a child having spawned.
4. Token-limit termination could bypass completion recovery.
5. Generic tasks received hard-coded CulturalExchangeHub co-domain contracts after broad keyword matches.
6. Generic testing practices were recorded but usually not instantiated as enforceable verification obligations.

### Benchmark adapters and instructions

Tracked paths:

```text
/home/luzh/Multi-agent-universal-redesign/openclaw_plugin/benchmarks/multiagentbench/run.py
/home/luzh/Multi-agent-universal-redesign/openclaw_plugin/benchmarks/multiagentbench/evaluate.py
/home/luzh/Multi-agent-universal-redesign/openclaw_plugin/benchmarks/multiagentbench/RUNBOOK.md
/home/luzh/Multi-agent-universal-redesign/openclaw_plugin/benchmarks/cooperbench/run_openclaw_macp.py
/home/luzh/Multi-agent-universal-redesign/openclaw_plugin/benchmarks/cooperbench/run_matrix_20.sh
/home/luzh/Multi-agent-universal-redesign/openclaw_plugin/benchmarks/cooperbench/RUNBOOK.md
```

These are useful for reproducing harness behavior. They are not part of the V2 memory-core design.

### Published aggregate evidence

Tracked path:

```text
/home/luzh/Multi-agent-universal-redesign/openclaw_plugin/benchmarks/results/matrix_20_20260814.md
```

This earlier matrix showed a split outcome:

- strong improvement on explicit CooperBench peer integration;
- substantial regression on autonomous MultiAgentBench tasks.

It is evidence that a workflow-specific control plane can appear successful on compatible task topology while failing to generalize.

### Latest matched 20-task MultiAgentBench evidence

Local-only path:

```text
/home/luzh/mab-restored-5x2-20260815/
```

Key files:

```text
/home/luzh/mab-restored-5x2-20260815/scores.jsonl
/home/luzh/mab-restored-5x2-20260815/score_comparison.json
/home/luzh/mab-restored-5x2-20260815/with_plugin/task_XX/run_manifest.json
/home/luzh/mab-restored-5x2-20260815/with_plugin/task_XX/root.stdout.json
/home/luzh/mab-restored-5x2-20260815/with_plugin/task_XX/memory_snapshot/
```

Important observed failure:

- every plugin-on run missing `solution.py` ended at exactly 8,192 output tokens with `stopReason=length`;
- dependency records existed but did not universally enforce continuation;
- plugin-on produced fewer deliverables over the full 20 tasks.

This is the main negative-control dataset for V2 completion and truncation tests.

### CooperBench local evidence

Local-only root:

```text
/home/luzh/cooperbench-run/CooperBench/logs/
```

The frozen 20-pair runs use names beginning with:

```text
matrix20-f94661d-without_plugin-
matrix20-f94661d-with_plugin-
```

These logs are useful for studying real peer ownership, integration artifacts, and native evaluator behavior where the older plugin performed better.

## 9. What may be reused

Good candidates for selective reuse:

- event-ledger and versioning concepts;
- deterministic artifact observation;
- stale-verification invalidation;
- compact recipient projections;
- optimistic contract-version checks;
- evidence schemas;
- benchmark runbooks and frozen case selection;
- tests that assert storage and reconciliation invariants.

## 10. What must not be copied into V2

- fixed planner/implementer/reviewer initialization;
- assumed `plan.md`, `implementation.md`, or `review.md` artifacts;
- plugin-driven spawning;
- keyword-only co-domain instantiation;
- domain-specific contract text in the universal core;
- treating process exit zero as task completion;
- completion enforcement that activates only after spawning;
- treating retrieved testing guidance as executed evidence;
- benchmark-specific state inside the harness-neutral backend.

## 11. Preservation rule

The original workspace and local experiment directories are evidence archives. Do not edit them during the V2 redesign.

New architecture and implementation work belongs only in:

```text
/home/luzh/Multi-agent-universal-redesign/
```

