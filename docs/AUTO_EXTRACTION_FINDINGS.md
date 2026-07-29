# Automatic Dependency-Contract Extraction

## Objective

Remove Task 19 artifact definitions from the memory engine. The extractor receives only:

1. arbitrary task text;
2. an external workflow description containing stages, roles, and stage instructions.

It must propose dependency contracts, pass structural validation, consolidate non-independent requirement facets, and compile complete memory YAML.

## Current architecture

```text
task text + workflow adapter
          |
          v
LLM semantic contract extractor
          |
          v
schema and graph validator
          |
          v
acceptance-facet consolidation
          |
          v
complete dependency-memory compiler
          |
          v
runtime event adapters update state
```

The engine no longer knows that a coding task should contain `solution.py`, `implementation.md`, or a reviewer. Those facts are inferred from the supplied workflow description.

## Generated Task 19 graph

The successful Task 19 extraction is stored in:

```text
auto_extraction_task19_v3/dependency_contracts.yaml
```

The model initially proposed 13 valid nodes. The consolidation stage folded seven same-boundary product facets into acceptance criteria on `solution_code`:

- role and permission system;
- upload interface;
- collaboration interface;
- performance metrics;
- security;
- test suite;
- scalability.

The resulting six-node graph is:

```text
environment: python_runtime

planner: plan_artifact
             |
             v
implementer: solution_code
             |
             v
implementer: implementation_log
             |
             v
reviewer: review_artifact
             |
             v
reviewer: workflow_completion_verification
```

`solution_code` retained 29 acceptance criteria, including the folded product requirements. The complete compiled store is:

```text
auto_extraction_task19_v3/compiled_dependency_memory.yaml
```

## Why feature nodes were folded

A product requirement is folded into its containing artifact when it:

- has no independent location;
- has exactly one containing artifact prerequisite;
- has the same producer as that artifact;
- has exactly the same workflow consumers.

A cross-agent interface is preserved. For example, a backend API produced by a backend agent and consumed by a frontend agent has a different consumer boundary and remains an independent dependency.

This prevents every task requirement from becoming a dependency node while retaining real ordering and handoff constraints.

## Validation behavior

The validator rejects:

- malformed or duplicate dependency IDs;
- unknown dependency, scope, state, or criterion types;
- producers that are neither workflow roles nor reserved external owners;
- product actors incorrectly used as workflow-agent consumers;
- file dependencies without locations;
- content predicates without literal values;
- missing retrieval actions or stages;
- unknown prerequisite references;
- dependency cycles;
- uncalibrated or missing confidence values.

Reserved non-agent producers include:

```text
environment
orchestrator
user
external_system
```

Invalid generations are not activated. The extractor can ask the same model session for up to two corrected proposals, including exact validation errors and the complete previous YAML.

## Output-channel generalization

OpenClaw agents sometimes return YAML in their response and sometimes write a YAML artifact. The adapter supports both:

1. parse YAML from a fenced or raw response;
2. otherwise inspect isolated-workspace YAML artifacts;
3. accept only a mapping containing a dependency list;
4. validate it before compilation.

No generated filename is required.

## Runtime-state separation

Contract generation is semantic and inferred. Runtime state remains evidence-driven.

File dependencies use:

- filesystem existence;
- content hashes and versions;
- modification times;
- deterministic content criteria;
- command results.

Non-file dependencies use typed observations from adapters:

- availability results;
- approval results;
- interface checks;
- service probes;
- semantic evaluations;
- decisions;
- capability checks;
- data validation.

The memory engine records these events but does not automatically execute LLM-inferred commands or contact external systems. An environment adapter must apply an execution/approval policy before submitting an observation.

## Remaining environment adapter

The generic engine still requires a workflow/environment adapter to describe:

- available roles and stages;
- stage instructions;
- tool and event sources;
- which commands may be executed automatically;
- how agent activation and finalization hooks are exposed.

This is configuration, not MultiAgentBench logic. For Task 19 it is represented by `task19_workflow.yaml`. A different system supplies a different workflow document.

## Test coverage

Nine tests currently pass. They cover:

- dependency-order-aware retrieval;
- artifact content and prerequisite validation;
- verification invalidation after edits;
- non-file typed observations;
- reserved environment producers;
- rejection of product actors as agent consumers;
- rejection of empty deterministic content checks;
- folding same-boundary product facets;
- preserving cross-agent interfaces.

## Current limitation

The automatic extractor has been evaluated on Task 19 only. Before claiming task independence empirically, it should be tested on tasks with materially different dependency types:

1. frontend agent consuming a backend API contract;
2. research agent consuming a generated dataset;
3. workflow waiting for explicit user approval;
4. agent consuming a deployed service;
5. task with no file artifacts.

The implementation is now structurally task-independent, but broader extraction accuracy remains an experimental question.

