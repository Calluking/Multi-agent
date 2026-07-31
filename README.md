# Multi-agent Dependency Memory

This repository contains the baseline runner, trace-to-MultiAgentBench score converter, and the private dependency-memory prototypes developed for MultiAgentBench coding tasks.

## What the memory system does

The current sparse design treats memory as an event-grounded recovery layer:

1. Run the normal planner, implementer, and reviewer workflow.
2. Observe persistent workspace evidence after an agent turn: required files, compilation, execution, and handoff reports.
3. If a dependency is unresolved, store **one current blocker** with its expected state, observed state, evidence, recipient role, priority, and recovery target.
4. Retrieve that private record for the responsible Agent and inject a bounded recovery instruction.
5. Re-run verification. If the memory layer fails, fail open and continue the baseline workflow.

This avoids the earlier v3 design's large task-wide dependency graphs, which added noise and caused regressions.

## Repository layout

- `baseline/`: clean OpenClaw baseline runner and MultiAgentBench trace scoring adapter.
- `dependency_memory/`: the generated-contract implementation retained for ablation.
- `dependency_memory/v4_sparse/`: sparse blocker observation, recovery prompting, matched-condition runner, evaluator, and tests.
- `examples/task19/`: worked task, workflow, contracts, and compiled memory.
- `docs/`: design notes, fault audit, case studies, and evaluation reports.

## Requirements

- Python 3.11+
- OpenClaw available as `openclaw`
- MultiAgentBench checked out locally
- `PyYAML` and `pytest`
- an OpenClaw-compatible model/API configuration

The v4 experiment runner's default dataset and model reflect the original WSL experiment. Override them for a different installation. The baseline runner exposes these values as CLI options.

## Run the baseline

```bash
python3 baseline/run_batch.py \
  --dataset /path/to/coding_main.jsonl \
  --root runs/baseline \
  --model deepseek/deepseek-v4-flash \
  --start 1 --end 20
```

## Run the sparse matched comparison

```bash
cd dependency_memory/v4_sparse
python3 run_sparse_panel.py \
  --tasks 1,2,5,15,17 \
  --repetitions 3 \
  --condition both \
  --root ./runs_panel_v4
```

## Run the dependency × cross-domain ablation

The feature runner exposes two independent switches through four named conditions:

- `baseline`: neither mechanism
- `dependency`: private sparse dependency recovery only
- `codomain`: shared boundary memory and post-hoc integration only
- `both`: both mechanisms

Run all four on Task 1:

```bash
cd dependency_memory/v4_sparse
python3 run_feature_ablation.py \
  --tasks 1 \
  --condition all \
  --root ./runs_feature_ablation_task1
```

## Quick checks

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=dependency_memory python3 -m pytest -q \
  tests/test_dependency_memory.py \
  tests/test_contract_extractor.py
python3 -m pytest -q dependency_memory/v4_sparse/test_sparse_memory.py
python3 dependency_memory/v4_sparse/run_sparse_panel.py --help
python3 dependency_memory/v4_sparse/evaluate_v4.py --help
```

## Evaluation status

The repository preserves both successful development observations and the held-out result. On the 15-task held-out comparison, M3 increased workflow completion from 73.3% to 86.7% and runnable artifacts from 86.7% to 93.3%, while mean Task Score changed from 85.00 to 84.33. The mechanism is therefore a useful dependency-recovery prototype, not yet a validated general performance improvement.

See `docs/M3_HOLDOUT_RESULTS.md` and `docs/M3_DEVELOPMENT_RESULTS.md` for the complete tables and limitations.

## Security

API keys are read from the local environment. No credentials, shell profiles, raw authentication files, or generated agent workspaces are included.
