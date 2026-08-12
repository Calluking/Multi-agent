# MultiAgentBench integration

This directory preserves the working OpenClaw adaptation used to evaluate the coding subset. It is intentionally separate from the production plugin.

## Requirements

- OpenClaw installed and configured with the selected model.
- The MARBLE `coding_main.jsonl` dataset.
- MACP installed as `multi-agent-contract-protocol`.

## Run

```bash
export MAB_DATASET=/path/to/MARBLE/multiagentbench/coding/coding_main.jsonl
export BENCHMARK_MODEL=deepseek/deepseek-v4-flash

python3 run.py without_plugin --tasks 1-5
python3 run.py with_plugin --tasks 1-5
python3 evaluate.py --tasks 1-5
```

The two conditions use the same task text, orchestration prompt, model and limits. The condition controls only whether MACP is enabled. Outputs are written below this directory and are ignored by Git.

This is a MultiAgentBench adaptation, not the upstream MARBLE execution environment. Report it with that qualification.
