# MultiAgentBench runbook

This runbook covers the original lightweight OpenClaw adaptation used for the
historical clean baseline. Multi-agent use is optional and `solution.py` is the
only required deliverable. It is not the upstream MARBLE execution environment.

## Prerequisites

```bash
cd /home/luzh/Multi-agent/openclaw_plugin

export OPENCLAW_BIN="$HOME/.local/bin/openclaw"
export MAB_DATASET="$HOME/multi-agent/multiagentbench-marble/multiagentbench/coding/coding_main.jsonl"
export BENCHMARK_MODEL=deepseek/deepseek-v4-flash
export BENCHMARK_JUDGE_MODEL=deepseek/deepseek-v4-flash

test -x "$OPENCLAW_BIN"
test -f "$MAB_DATASET"
test -n "$DEEPSEEK_API_KEY"
test -n "$DEEPSEEK_BASE_URL"
timeout 20s "$OPENCLAW_BIN" config get \
  plugins.entries.multi-agent-contract-protocol.enabled
```

Do not continue if the last command times out. Restart OpenClaw or WSL first;
that condition is an infrastructure failure.

## Smoke test: one matched task

```bash
python3 benchmarks/multiagentbench/run.py without_plugin --tasks 5
python3 benchmarks/multiagentbench/run.py with_plugin --tasks 5
rm -f benchmarks/multiagentbench/scores.jsonl \
      benchmarks/multiagentbench/score_comparison.json
python3 benchmarks/multiagentbench/evaluate.py --tasks 5
cat benchmarks/multiagentbench/score_comparison.json
```

The starting prompt is intentionally minimal:

```text
You are solving a MultiAgentBench coding task using OpenClaw.

Use OpenClaw multi-agent mode if helpful. Spawn subagents for planning, coding,
and review when useful.

Task:
[complete benchmark task text]

Final deliverable:
Write the complete answer to solution.py in the current workspace.
```

There are no forced roles, child count, ordering constraints, intermediate
artifacts, or verification gates in the harness. MACP must add coordination
through its hooks when the model elects to use multiple agents.

This restored-prompt smoke completed end-to-end on 2026-08-13. Task 5 scored
4.25/5 without MACP and 4.75/5 with MACP. This validates the matched harness;
one task is not a performance conclusion.

OpenClaw may seed standard workspace files such as `AGENTS.md`, `SOUL.md`, and
`TOOLS.md` when registering an agent. The benchmark runner does not author
forced orchestration instructions in those files.

## Five-task comparison

After the smoke test works:

```bash
python3 benchmarks/multiagentbench/run.py without_plugin --tasks 1-5
python3 benchmarks/multiagentbench/run.py with_plugin --tasks 1-5
rm -f benchmarks/multiagentbench/scores.jsonl \
      benchmarks/multiagentbench/score_comparison.json
python3 benchmarks/multiagentbench/evaluate.py --tasks 1-5
cat benchmarks/multiagentbench/score_comparison.json
```

Runs are resumable. A cached task is reused only when `root_exit` is zero,
`solution.py` exists, and the stored prompt hash matches the current original
prompt. Outputs from the former forced-orchestration prompt are automatically
archived and rerun. Generated outputs are ignored by Git.

## Output and validity checks

Per-task data:

```text
benchmarks/multiagentbench/without_plugin/task_XX/
benchmarks/multiagentbench/with_plugin/task_XX/
```

Aggregate scores:

```text
benchmarks/multiagentbench/scores.jsonl
benchmarks/multiagentbench/score_comparison.json
```

For runs split across isolated batch roots, assemble a consolidated directory
of task symlinks and select it without copying artifacts:

```bash
export MAB_RUN_ROOT=/absolute/path/to/consolidated-run-root
export MAB_JUDGE_AGENT=stable-dedicated-judge-agent
python3 benchmarks/multiagentbench/evaluate.py --tasks 1-20
```

`MAB_JUDGE_AGENT` avoids coupling evaluation to run-scoped coordinator agents
whose original workspaces may have been archived. It changes only the agent
that submits the unchanged judge prompt.

For every requested task, confirm `run_manifest.json` has `root_exit: 0`, the
`solution.py` artifact flag is true, and both conditions have the same
`prompt_sha256`. Provider timeouts, gateway/session locks, WSL hangs, and
interrupted runs are infrastructure failures and must not be reported as model
or plugin scores.
