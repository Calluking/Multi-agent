# MultiAgentBench integration

For prerequisites, one-command A/B execution, resume behavior, and result
validation, see [`RUNBOOK.md`](RUNBOOK.md).

This directory preserves the working OpenClaw adaptation used to evaluate the coding subset. It is intentionally separate from the production plugin.

## Requirements

- OpenClaw installed and configured with the selected model.
- The MARBLE `coding_main.jsonl` dataset.
- MACP installed as `multi-agent-contract-protocol`.

## Run a matched comparison

```bash
export MAB_DATASET=/path/to/MARBLE/multiagentbench/coding/coding_main.jsonl
export BENCHMARK_MODEL=deepseek/deepseek-v4-flash

python3 run.py without_plugin --tasks 1-5
python3 run.py with_plugin --tasks 1-5
python3 evaluate.py --tasks 1-5
```

The runner uses the original lightweight OpenClaw wrapper prompt: multi-agent
work is optional and `solution.py` is the only required deliverable. Re-running
a condition resumes outputs only when their prompt hash matches the current
prompt. Both conditions use the same task, prompt, model, and limits; only MACP
enablement differs.

This is a MultiAgentBench adaptation, not the upstream MARBLE execution environment. Report it with that qualification.
