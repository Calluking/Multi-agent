# Multi-agent Dependency Memory

This repository contains the reproducible milestone from a 20-task MultiAgentBench coding study:

- a clean OpenClaw baseline runner;
- a private dependency-memory implementation;
- automatic dependency-contract extraction and validation;
- a memory-enabled batch runner with read/observe/update/readiness checkpoints;
- unit tests, a worked Task 19 example, and compact evaluation summaries.

The adapted workflow is intended for mechanism research. Its scores are descriptive and are not directly comparable with the official MultiAgentBench leaderboard.

## Repository layout

```text
baseline/             Portable baseline coding-task runner
dependency_memory/    Contract extraction, YAML memory store, and memory runner
tests/                Unit tests for extraction and state management
examples/task19/      Example task, workflow, contracts, and compiled memory
docs/                 Design decisions, fault tables, and evaluation notes
results/              Compact baseline and memory-run summaries
```

## Requirements

- Python 3.11+
- OpenClaw CLI available as `openclaw`
- MultiAgentBench coding dataset (`coding_main.jsonl`)
- An OpenClaw model/provider configured in the environment

Install the Python dependency:

```bash
python3 -m pip install -r requirements.txt
```

## Run the baseline

```bash
python3 baseline/run_batch.py \
  --dataset /path/to/coding_main.jsonl \
  --root runs/baseline \
  --model deepseek/deepseek-v4-flash \
  --start 1 --end 20
```

The runner executes planner, implementer, reviewer, and adapted scoring stages and writes one workspace per task.

## Run with private dependency memory

```bash
PYTHONPATH=dependency_memory python3 dependency_memory/run_memory_batch.py \
  --dataset /path/to/coding_main.jsonl \
  --root runs/dependency-memory \
  --model deepseek/deepseek-v4-flash \
  --start 1 --end 20
```

For each task the memory-enabled runner:

1. extracts dependency contracts from the task and workflow;
2. compiles complete private YAML records;
3. retrieves unresolved dependencies before an agent turn;
4. injects the current target or blocker into the agent prompt;
5. observes files, commands, and verification evidence after the turn;
6. updates memory and gates handoff readiness;
7. retries unresolved work before releasing the next agent.

## Compile the included example

```bash
PYTHONPATH=dependency_memory python3 dependency_memory/compile_contracts_file.py \
  --contracts examples/task19/dependency_contracts.yaml \
  --workflow examples/task19/workflow_input.yaml \
  --workspace examples/task19 \
  --output /tmp/task19-memory.yaml \
  --task-id 19 \
  --run-id example-task19
```

## Tests

```bash
PYTHONPATH=dependency_memory python3 -m unittest discover -s tests -v
```

## Main result

Across the 20-task descriptive comparison, dependency faults fell from 8 to 2. Mean task score increased from 82.75 to 85.50, workflow completion from 70% to 90%, and runnable artifacts from 80% to 90%. See `docs/MEMORY_BATCH_V3_EVALUATION.md` and `docs/FAULT_TABLE.md` for the evaluation context and per-task analysis.

## Security

Do not commit provider keys, GitHub tokens, `.env` files, OpenClaw credentials, or raw agent workspaces. The included `.gitignore` excludes common generated and secret-bearing files.
