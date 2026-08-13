# CooperBench runbook

This integration keeps CooperBench itself unmodified. Run commands from WSL.

## 1. Prerequisites

```bash
cd ~/cooperbench-run/CooperBench
source .venv/bin/activate
uv pip install 'httpx[socks]'
docker info
docker ps | grep redis
test -n "$DEEPSEEK_API_KEY"
test -n "$DEEPSEEK_BASE_URL"
```

The CooperBench task ID is numeric: use `17070`, not `task17070`.

## 2. Verify the official solo baseline

From this plugin repository:

```bash
RUN_NAME=deepseek-solo-17070 TASK_ID=17070 \
  bash benchmarks/cooperbench/run_deepseek_solo.sh
```

The script runs CooperBench's official `mini_swe_agent_v2` with the Docker
backend and then invokes the native evaluator. Results are stored in:

```text
~/cooperbench-run/CooperBench/logs/deepseek-solo-17070/solo/
```

## 3. Run an OpenClaw cooperative feature pair

Plugin disabled:

```bash
python3 benchmarks/cooperbench/run_openclaw_macp.py without_plugin \
  --name openclaw-off-17070-f12 \
  --repo llama_index_task --task 17070 --features 1,2
```

Plugin enabled:

```bash
python3 benchmarks/cooperbench/run_openclaw_macp.py with_plugin \
  --name openclaw-macp-17070-f12 \
  --repo llama_index_task --task 17070 --features 1,2
```

Evaluate each run with CooperBench, not a custom scorer:

```bash
cd ~/cooperbench-run/CooperBench
source .venv/bin/activate
cooperbench eval -n openclaw-off-17070-f12 \
  -r llama_index_task -t 17070 -f 1,2 --backend docker
cooperbench eval -n openclaw-macp-17070-f12 \
  -r llama_index_task -t 17070 -f 1,2 --backend docker
```

## 4. Valid comparison rules

Keep the CooperBench revision, task, feature pair, model, prompt, topology,
timeouts, retries, Docker backend, and evaluator identical. Only plugin
enablement may differ. Do not score missing/partial patches as an agent-quality
result when the trace contains a gateway lock, provider timeout, or interrupted
coordinator. Preserve the run directory and stderr for diagnosis.

## 5. Known verified results

- Official solo task `17070`, all three pairs: 2/3 (66.7%).
- Plugin-enabled OpenClaw pair `[1,2]`: passed the native evaluator twice.
- A clean matched plugin-off/plugin-on aggregate remains pending; gateway-lock
  interrupted attempts are not valid baseline scores.
